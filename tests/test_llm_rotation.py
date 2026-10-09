import io
import json
from urllib.error import HTTPError

import pytest

from apps import llm
from apps.llm import (
    available_models,
    chat_json,
    note_limited,
    parse_models,
)


@pytest.fixture(autouse=True)
def _clean_llm_state():
    llm._COOLDOWNS.clear()
    llm._SKIPPED.clear()
    yield
    llm._COOLDOWNS.clear()
    llm._SKIPPED.clear()


class FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args):
        return self._payload


def _oa_reply(inner: dict, prompt=50, completion=25):
    return json.dumps({
        "choices": [{"message": {"content": json.dumps(inner)}}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion},
    }).encode("utf-8")


def _install_router(monkeypatch, handler):
    seen = []

    def fake_urlopen(request, timeout=None):
        seen.append(json.loads(request.data.decode("utf-8"))["model"])
        return FakeResponse(handler(request))

    monkeypatch.setattr("apps.llm.urlopen", fake_urlopen)
    return seen


def _raise(code):
    def boom(request):
        raise HTTPError(request.full_url, code, f"http {code}", {}, io.BytesIO(b""))
    return boom


def _config(**overrides):
    config = {"LLM_PROVIDER": "openai_compatible",
              "LLM_BASE_URL": "https://api.example.com/v1",
              "LLM_API_KEY": "k",
              "LLM_MODELS": "test-m1, test-m2",
              "LLM_COOLDOWN_SECONDS": "300"}
    config.update(overrides)
    return config


def test_parse_models_prefers_chain_then_single():
    assert parse_models({"LLM_MODELS": "a, b ,,c", "LLM_MODEL": "z"}) == ["a", "b", "c"]
    assert parse_models({"LLM_MODEL": "solo"}) == ["solo"]
    assert parse_models({}) == []


def test_rate_limit_rotates_and_cools_down(monkeypatch):
    calls = {"test-m1": 0}

    def handler(request):
        model = json.loads(request.data.decode("utf-8"))["model"]
        calls[model] = calls.get(model, 0) + 1
        if model == "test-m1":
            raise HTTPError(request.full_url, 429, "limited", {}, io.BytesIO(b""))
        return _oa_reply({"ok": True})

    seen = _install_router(monkeypatch, handler)
    body, usage = chat_json(_config(), "s", {}, num_predict=8, timeout=5)
    assert body == {"ok": True}
    assert usage["model"] == "test-m2"
    assert seen == ["test-m1", "test-m2"]
    assert "test-m1" in llm._COOLDOWNS

    # A second call skips the cooling model without touching it.
    seen.clear()
    body, usage = chat_json(_config(), "s", {}, num_predict=8, timeout=5)
    assert body == {"ok": True}
    assert seen == ["test-m2"]
    assert calls["test-m1"] == 1


def test_auth_failure_fails_fast_without_rotation(monkeypatch):
    seen = _install_router(monkeypatch, _raise(401))
    body, usage = chat_json(_config(), "s", {}, num_predict=8, timeout=5)
    assert body is None
    assert usage["model"] == ""
    assert seen == ["test-m1"]
    assert llm._COOLDOWNS == {}


def test_unknown_model_id_is_skipped_permanently(monkeypatch):
    seen = _install_router(
        monkeypatch,
        lambda request: (_raise(404)(request)
                         if json.loads(request.data.decode("utf-8"))["model"] == "test-m1"
                         else _oa_reply({"ok": True})),
    )
    body, _ = chat_json(_config(), "s", {}, num_predict=8, timeout=5)
    assert body == {"ok": True}
    assert "test-m1" in llm._SKIPPED
    seen.clear()
    body, _ = chat_json(_config(), "s", {}, num_predict=8, timeout=5)
    assert seen == ["test-m2"]


def test_all_models_failing_returns_none(monkeypatch):
    _install_router(monkeypatch, _raise(503))
    body, usage = chat_json(_config(), "s", {}, num_predict=8, timeout=5)
    assert body is None
    assert usage["model"] == ""


def test_malformed_reply_rotates(monkeypatch):
    def handler(request):
        model = json.loads(request.data.decode("utf-8"))["model"]
        if model == "test-m1":
            return _oa_reply({"ok": True})[:10]  # truncated JSON
        return _oa_reply({"ok": True})

    _install_router(monkeypatch, handler)
    body, usage = chat_json(_config(), "s", {}, num_predict=8, timeout=5)
    assert body == {"ok": True}
    assert usage["model"] == "test-m2"


def test_cooldown_expiry_makes_model_available_again(monkeypatch):
    note_limited("test-m1", {"LLM_COOLDOWN_SECONDS": "300"})
    assert available_models(_config()) == ["test-m2"]
    llm._COOLDOWNS["test-m1"] = 0.0  # expired in the past
    assert available_models(_config()) == ["test-m1", "test-m2"]


def test_retry_after_header_extends_cooldown(monkeypatch):
    def handler(request, timeout=None):
        raise HTTPError(request.full_url, 429, "limited",
                        {"Retry-After": "900"}, io.BytesIO(b""))

    monkeypatch.setattr("apps.llm.urlopen", handler)
    body, _ = chat_json(_config(), "s", {}, num_predict=8, timeout=5)
    assert body is None  # both models limited
    import time
    remaining = llm._COOLDOWNS["test-m1"] - time.monotonic()
    assert 800 < remaining <= 900
    # Configured 300s cooldown is overridden by the longer header value.
    assert llm._COOLDOWNS["test-m2"] > llm._COOLDOWNS["test-m1"] - 5
