from pathlib import Path

import apps.orchestrator.fallback as fallback


def _usage(model, prompt=10, completion=20):
    return {"prompt_tokens": prompt, "completion_tokens": completion, "model": model}


def test_cloud_first_returns_cloud_without_touching_ollama(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("LLM_PROVIDER=openai_compatible\n", encoding="utf-8")
    calls = []

    def fake_chat(config, system, payload, *, num_predict, timeout):
        calls.append(config.get("LLM_PROVIDER"))
        return {"ok": True}, _usage("qwen/qwen3.8-27b")

    monkeypatch.setattr(fallback, "chat_json", fake_chat)
    body, usage, ledger = fallback.cloud_first_chat(
        tmp_path, "sys", {"a": 1}, num_predict=64, timeout=5
    )
    assert body == {"ok": True}
    assert ledger["tier"] == "cloud"
    assert calls == ["openai_compatible"]


def test_falls_back_to_ollama_when_cloud_fails(monkeypatch, tmp_path: Path):
    (tmp_path / ".env").write_text("LLM_PROVIDER=openai_compatible\n", encoding="utf-8")
    calls = []

    def fake_chat(config, system, payload, *, num_predict, timeout):
        provider = config.get("LLM_PROVIDER")
        calls.append((provider, config.get("LLM_MODEL") or config.get("LLM_MODELS")))
        if provider == "openai_compatible":
            return None, {"prompt_tokens": 0, "completion_tokens": 0, "model": ""}
        return {"beat": 1}, _usage(config.get("LLM_MODEL"))

    monkeypatch.setattr(fallback, "chat_json", fake_chat)
    body, usage, ledger = fallback.cloud_first_chat(
        tmp_path, "sys", {"a": 1}, num_predict=64, timeout=5
    )
    assert body == {"beat": 1}
    assert ledger["tier"] == "ollama_fallback"
    assert calls[0][0] == "openai_compatible"
    assert calls[1][0] == "ollama"


def test_both_tiers_failing_returns_none(monkeypatch, tmp_path: Path):
    (tmp_path / ".env").write_text("LLM_PROVIDER=openai_compatible\n", encoding="utf-8")

    def fake_chat(config, system, payload, *, num_predict, timeout):
        return None, {"prompt_tokens": 0, "completion_tokens": 0, "model": ""}

    monkeypatch.setattr(fallback, "chat_json", fake_chat)
    body, usage, ledger = fallback.cloud_first_chat(
        tmp_path, "sys", {"a": 1}, num_predict=64, timeout=5
    )
    assert body is None
    assert ledger["tier"] == "none"
    assert ledger["reason"] == "cloud_and_ollama_failed"
