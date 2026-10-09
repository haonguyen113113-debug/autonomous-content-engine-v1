import io
import json
from urllib.error import HTTPError

import pytest

from apps import llm
from apps.llm import (
    budget_usd_per_run,
    chat_json,
    cost_usd,
    load_config,
)


class FakeResponse:
    def __init__(self, payload: bytes, headers=None):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args):
        return self._payload


def _install(monkeypatch, handler):
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(request)
        return FakeResponse(handler(request))

    monkeypatch.setattr("apps.llm.urlopen", fake_urlopen)
    return calls


def _ollama_reply(content, prompt_eval=100, eval_count=50):
    return json.dumps({
        "message": {"content": content},
        "prompt_eval_count": prompt_eval,
        "eval_count": eval_count,
    }).encode("utf-8")


def test_ollama_request_shape_and_usage(monkeypatch):
    inner = json.dumps({"narration": "X"})
    calls = _install(monkeypatch, lambda request: _ollama_reply(inner))
    config = {"LLM_PROVIDER": "ollama", "LLM_MODEL": "qwen3.5:2b",
              "OLLAMA_BASE_URL": "http://localhost:11434"}
    from apps.content_workflow import _new_ledger
    ledger = _new_ledger(config)
    from apps.content_workflow import _ollama_call
    body, record = _ollama_call(
        config, "sys", {"a": 1}, num_predict=64, timeout=10, ledger=ledger)
    assert body == {"narration": "X"}
    assert usage_unused(record) == {"prompt_tokens": 100, "completion_tokens": 50}
    sent = json.loads(calls[0].data.decode("utf-8"))
    assert calls[0].full_url.endswith("/api/chat")
    assert sent["format"] == "json"
    assert sent["options"]["num_predict"] == 64
    assert sent["messages"][0] == {"role": "system", "content": "sys"}
    assert ledger["spent"] == 0.0  # local inference is free
    assert ledger["calls"][0]["cost_usd"] == 0.0


def usage_unused(record):
    return {k: record[k] for k in ("prompt_tokens", "completion_tokens")}


def test_openai_compatible_request_shape_and_usage(monkeypatch):
    inner = json.dumps({"narration": "Y"})
    payload = json.dumps({
        "choices": [{"message": {"content": "```json\n" + inner + "\n```"}}],
        "usage": {"prompt_tokens": 200, "completion_tokens": 80},
    }).encode("utf-8")
    calls = _install(monkeypatch, lambda request: payload)
    config = {"LLM_PROVIDER": "openai_compatible", "LLM_MODEL": "gpt-4.1-mini",
              "LLM_BASE_URL": "https://api.example.com/v1",
              "LLM_API_KEY": "sk-test-secret",
              "LLM_PRICE_PER_M_IN": 0.4, "LLM_PRICE_PER_M_OUT": 1.6}
    from apps.content_workflow import _new_ledger, _ollama_call
    ledger = _new_ledger(config)
    body, record = _ollama_call(
        config, "sys", {"a": 1}, num_predict=64, timeout=10, ledger=ledger)
    assert body == {"narration": "Y"}  # fences tolerated
    assert calls[0].full_url == "https://api.example.com/v1/chat/completions"
    sent = json.loads(calls[0].data.decode("utf-8"))
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["max_tokens"] == 64
    assert calls[0].get_header("Authorization") == "Bearer sk-test-secret"
    assert record["prompt_tokens"] == 200
    assert record["completion_tokens"] == 80
    assert record["cost_usd"] == pytest.approx((200 * 0.4 + 80 * 1.6) / 1_000_000)
    assert ledger["spent"] == record["cost_usd"]


def test_openai_compatible_missing_key_fails_closed(monkeypatch):
    calls = _install(monkeypatch, lambda request: b"{}")
    config = {"LLM_PROVIDER": "openai_compatible", "LLM_MODEL": "x",
              "LLM_BASE_URL": "https://api.example.com/v1", "LLM_API_KEY": ""}
    body, usage = chat_json(config, "s", {}, num_predict=8, timeout=5)
    assert body is None
    assert usage == {"prompt_tokens": 0, "completion_tokens": 0, "model": ""}
    assert calls == []


def test_unknown_provider_fails_closed():
    body, usage = chat_json({"LLM_PROVIDER": "nope"}, "s", {}, num_predict=8, timeout=5)
    assert body is None
    assert usage == {"prompt_tokens": 0, "completion_tokens": 0, "model": ""}


def test_http_error_never_leaks_key(monkeypatch):
    def boom(request, timeout=None):
        raise HTTPError(request.full_url, 401, "bad key sk-test-secret", {}, io.BytesIO(b""))
    monkeypatch.setattr("apps.llm.urlopen", boom)
    config = {"LLM_PROVIDER": "openai_compatible", "LLM_MODEL": "x",
              "LLM_BASE_URL": "https://api.example.com/v1", "LLM_API_KEY": "sk-test-secret"}
    body, _ = chat_json(config, "s", {}, num_predict=8, timeout=5)
    assert body is None
    try:
        llm._post_json("https://x", {}, {}, 5)
    except llm.LLMError as error:
        assert "sk-test-secret" not in str(error)


def test_budget_skips_calls_without_transport(monkeypatch):
    calls = _install(monkeypatch, lambda request: _ollama_reply("{}"))
    config = {"LLM_PROVIDER": "openai_compatible", "LLM_MODEL": "gpt-4.1-mini",
              "LLM_BASE_URL": "https://api.example.com/v1", "LLM_API_KEY": "k",
              "LLM_PRICE_PER_M_IN": 1000.0, "LLM_PRICE_PER_M_OUT": 1000.0,
              "LLM_BUDGET_USD_PER_RUN": 0.000001}
    from apps.content_workflow import _new_ledger, _ollama_call
    ledger = _new_ledger(config)
    ledger["spent"] = 1.0  # already over budget
    body, record = _ollama_call(config, "s", {}, num_predict=8, timeout=5, ledger=ledger)
    assert body is None
    assert record["cost_usd"] == 0.0
    assert ledger["budget_stops"] == 1
    assert calls == []


def test_pricing_sources():
    assert cost_usd({"LLM_PROVIDER": "ollama", "LLM_MODEL": "qwen3.5:2b"},
                    {"prompt_tokens": 10**6, "completion_tokens": 10**6}) == (0.0, True)
    cost, priced = cost_usd({"LLM_PROVIDER": "openai_compatible", "LLM_MODEL": "gpt-4.1-mini"},
                            {"prompt_tokens": 10**6, "completion_tokens": 0})
    assert (cost, priced) == (0.4, True)
    cost, priced = cost_usd({"LLM_PROVIDER": "openai_compatible", "LLM_MODEL": "mystery-9b"},
                            {"prompt_tokens": 10**6, "completion_tokens": 0})
    assert (cost, priced) == (0.0, False)
    cost, priced = cost_usd({"LLM_PROVIDER": "openai_compatible", "LLM_MODEL": "mystery-9b",
                             "LLM_PRICE_PER_M_IN": 2.0, "LLM_PRICE_PER_M_OUT": 3.0},
                            {"prompt_tokens": 10**6, "completion_tokens": 10**6})
    assert (cost, priced) == (5.0, True)


def test_budget_defaults_and_config_merge(tmp_path):
    assert budget_usd_per_run({}) == 0.25
    assert budget_usd_per_run({"LLM_BUDGET_USD_PER_RUN": "abc"}) == 0.25
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_MODEL=test-model\nLLM_PROVIDER=ollama\n", encoding="utf-8")
    config = load_config(tmp_path, env={})
    assert config["LLM_MODEL"] == "test-model"
    assert config["LLM_PROVIDER"] == "ollama"
    assert config["OLLAMA_BASE_URL"] == "http://localhost:11434"
