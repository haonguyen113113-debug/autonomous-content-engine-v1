import io
import json
from pathlib import Path
from urllib.error import URLError

import pytest

import apps.content_workflow as workflow


ROOT = Path(__file__).resolve().parent.parent


class FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


def _chat_content(inner: dict) -> bytes:
    return json.dumps({"message": {"content": json.dumps(inner)}}).encode("utf-8")


def _beat_payload(narration="Nhịp phân tích.", duration=8):
    return {
        "id": "beat-x",
        "narration": narration,
        "visual": "Bảng chiến thuật",
        "evidence_refs": [],
        "visual_mode": "tactical_explainer",
        "graphic_data": {},
        "duration_seconds": duration,
        "timeline_events": [],
    }


def _install(monkeypatch, script):
    """script: list of payload bytes or exceptions, consumed per urlopen call."""
    calls = []
    state = {"index": 0}

    def fake_urlopen(request, timeout=None):
        calls.append({"data": request.data, "timeout": timeout})
        item = script[min(state["index"], len(script) - 1)]
        state["index"] += 1
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    monkeypatch.setattr(workflow, "urlopen", fake_urlopen)
    return calls


def _draft_kwargs():
    return {
        "topic": "Vì sao pressing tầm cao hiệu quả?",
        "story_form_id": "one-moment-one-read",
        "evidence_text": "",
        "content_type": "short",
        "colorway": "match-night",
    }


def test_beats_assemble_with_per_segment_provenance(monkeypatch):
    beats = [_chat_content(_beat_payload(f"Narration {i}.", 7)) for i in range(6)]
    assets = _chat_content({"asset_needs": []})
    calls = _install(monkeypatch, beats + [assets])

    result = workflow.create_script_draft(ROOT, **_draft_kwargs())

    assert result["generation_mode"] == "local_ollama"
    assert len(result["segments"]) == 6
    assert [s["id"] for s in result["segments"]] == [f"beat-{i + 1}" for i in range(6)]
    assert all(s["generation"]["mode"] == "local_ollama" for s in result["segments"])
    assert all(s["generation"]["attempts"] == 1 for s in result["segments"])
    assert result["fallback_beats"] == []
    assert result["asset_needs"] == []
    # 6 beat calls + 1 asset-needs call, each bounded well below the old
    # monolithic timeouts.
    assert len(calls) == 7
    assert all(c["timeout"] <= 300 for c in calls)
    # Coherence: beat 2+ receives the previous narration as context.
    second_user = json.loads(json.loads(calls[1]["data"].decode("utf-8"))["messages"][1]["content"])
    assert "Narration 0." in second_user["previous_beat_summary"]


def test_failed_beat_retries_then_falls_back_per_beat(monkeypatch):
    good = [_chat_content(_beat_payload("Good beat.", 7)) for _ in range(5)]
    script = [good[0], b"{invalid", _chat_content(_beat_payload("Recovered.", 7))] + good[1:]
    calls = _install(monkeypatch, script + [_chat_content({"asset_needs": []})])

    result = workflow.create_script_draft(ROOT, **_draft_kwargs())

    assert result["generation_mode"] == "local_ollama"
    assert len(result["segments"]) == 6
    recovered = next(s for s in result["segments"] if s["id"] == "beat-2")
    assert recovered["narration"] == "Recovered."
    assert recovered["generation"] == {"mode": "local_ollama", "attempts": 2}
    assert result["fallback_beats"] == []
    assert len(calls) == 8  # one retry for beat-2


def test_twice_failed_beat_uses_outline_placeholder(monkeypatch):
    beats = [_chat_content(_beat_payload("Good beat.", 7)) for _ in range(5)]
    script = beats[:1] + [b"{bad-1", b"{bad-2"] + beats[1:]
    _install(monkeypatch, script + [_chat_content({"asset_needs": []})])

    result = workflow.create_script_draft(ROOT, **_draft_kwargs())

    assert result["generation_mode"] == "local_ollama_partial"
    assert result["fallback_beats"] == ["beat-2"]
    failed = next(s for s in result["segments"] if s["id"] == "beat-2")
    assert "[CẦN NGUỒN]" in failed["narration"]
    assert failed["generation"]["mode"] == "outline_fallback"
    # Successful beats are kept, not discarded.
    assert sum(1 for s in result["segments"] if s["generation"]["mode"] == "local_ollama") == 5


def test_model_down_keeps_deterministic_outline_fallback(monkeypatch):
    _install(monkeypatch, [URLError("connection refused")])

    result = workflow.create_script_draft(ROOT, **_draft_kwargs())

    assert result["generation_mode"] == "outline_fallback"
    assert len(result["segments"]) == 6
    assert result["status"] == "NEEDS_EVIDENCE"


def test_asset_needs_validated_and_capped(monkeypatch):
    beats = [_chat_content(_beat_payload("Good beat.", 7)) for _ in range(6)]
    needs = _chat_content({"asset_needs": [
        {"resource_type": "image", "purpose": "player_context", "quantity": 9,
         "query": "striker pressing", "exact_context": "trận derby",
         "reason": "minh họa vai trò"},
        {"resource_type": "audio", "purpose": "player_context", "quantity": 1,
         "query": "noise", "reason": "invalid type dropped"},
        {"resource_type": "image", "purpose": "player_context", "quantity": 1,
         "query": "", "reason": "empty query dropped"},
    ]})
    _install(monkeypatch, beats + [needs])

    result = workflow.create_script_draft(ROOT, **_draft_kwargs())

    assert len(result["asset_needs"]) == 1
    assert result["asset_needs"][0]["quantity"] == 3  # clamped to 1-3
    assert result["asset_needs"][0]["requirement_id"] == "variable-media-1"


def test_asset_needs_failure_degrades_to_empty(monkeypatch):
    beats = [_chat_content(_beat_payload("Good beat.", 7)) for _ in range(6)]
    _install(monkeypatch, beats + [URLError("timeout")])

    result = workflow.create_script_draft(ROOT, **_draft_kwargs())

    assert result["generation_mode"] == "local_ollama"
    assert result["asset_needs"] == []
    assert "no variable library media was requested" in result["asset_need_reason"]
