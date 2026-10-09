import io
import json
from pathlib import Path
from urllib.error import URLError

import pytest

import apps.content_workflow as workflow
from apps import llm as llm_module


@pytest.fixture(autouse=True)
def _clean_llm_state():
    llm_module._COOLDOWNS.clear()
    llm_module._SKIPPED.clear()
    yield
    llm_module._COOLDOWNS.clear()
    llm_module._SKIPPED.clear()


@pytest.fixture(autouse=True)
def _pin_local_provider(monkeypatch):
    """Hermetic provider config: the real .env must not leak into tests."""
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "qwen3.5:2b")
    monkeypatch.setenv("LLM_MODELS", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_BUDGET_USD_PER_RUN", "0.25")
from apps.web_ui.server import _list_runs


ROOT = Path(__file__).resolve().parent.parent


class FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args):
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

    monkeypatch.setattr("apps.llm.urlopen", fake_urlopen)
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
    assert recovered["generation"]["mode"] == "local_ollama"
    assert recovered["generation"]["attempts"] == 2
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
    assert failed["generation"]["error"] in {"transport_or_provider_error", "invalid_segment_reply"}
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


def test_run_publishes_progress_before_draft_completes(monkeypatch, tmp_path):
    root = tmp_path / "p"
    (root / "runtime/runs").mkdir(parents=True)
    seen = {}

    def fake_draft(*args, **kwargs):
        files = list((root / "runtime/runs").glob("*.json"))
        assert len(files) == 1
        seen.update(json.loads(files[0].read_text(encoding="utf-8")))
        return {
            "topic": "Chủ đề kiểm thử",
            "status": "NEEDS_EVIDENCE",
            "generation_mode": "outline_fallback",
            "asset_needs": [],
        }

    monkeypatch.setattr(workflow, "create_script_draft", fake_draft)
    run = workflow.run_content_agent(
        root, root / "runtime/engine.db",
        "Chủ đề kiểm thử", "one-moment-one-read",
    )

    assert seen["status"] == "DRAFTING_SCRIPT"
    assert seen["draft"] is None
    assert seen["run_id"] == run["run_id"]
    assert run["status"] == "WAITING_FOR_OWNER_REVIEW"
    assert run["draft"]["topic"] == "Chủ đề kiểm thử"
    saved = json.loads((root / "runtime/runs" / f"{run['run_id']}.json").read_text(encoding="utf-8"))
    assert saved["status"] == "WAITING_FOR_OWNER_REVIEW"


def test_run_records_draft_failure(monkeypatch, tmp_path):
    root = tmp_path / "p"
    (root / "runtime/runs").mkdir(parents=True)

    def boom(*args, **kwargs):
        raise ValueError("Chủ đề cần dài từ 4 đến 500 ký tự.")

    monkeypatch.setattr(workflow, "create_script_draft", boom)
    with pytest.raises(ValueError):
        workflow.run_content_agent(
            root, root / "runtime/engine.db",
            "Chủ đề kiểm thử", "one-moment-one-read",
        )
    files = list((root / "runtime/runs").glob("*.json"))
    assert len(files) == 1
    saved = json.loads(files[0].read_text(encoding="utf-8"))
    assert saved["status"] == "DRAFT_FAILED"
    assert "500 ký tự" in saved["error"]


def test_progress_records_listed_with_zero_counts(tmp_path):
    root = tmp_path / "p"
    (root / "runtime/runs").mkdir(parents=True)
    (root / "runtime/runs" / "abcdef123456.json").write_text(
        json.dumps({
            "run_id": "abcdef123456",
            "created_at": "2026-10-09T00:00:00+00:00",
            "status": "DRAFTING_SCRIPT",
            "draft": None,
        }),
        encoding="utf-8",
    )
    runs = _list_runs(root)
    assert len(runs) == 1
    assert runs[0]["status"] == "DRAFTING_SCRIPT"
    assert runs[0]["segment_count"] == 0
    assert runs[0]["media_count"] == 0


def test_asset_needs_failure_degrades_to_empty(monkeypatch):
    beats = [_chat_content(_beat_payload("Good beat.", 7)) for _ in range(6)]
    _install(monkeypatch, beats + [URLError("timeout")])

    result = workflow.create_script_draft(ROOT, **_draft_kwargs())

    assert result["generation_mode"] == "local_ollama"
    assert result["asset_needs"] == []
    assert "no variable library media was requested" in result["asset_need_reason"]


def test_zero_budget_skips_model_calls_entirely(monkeypatch):
    calls = _install(monkeypatch, [URLError("must not be called")])

    result = workflow.create_script_draft(
        ROOT, **{**_draft_kwargs(), "budget_seconds": 0}
    )

    assert result["generation_mode"] == "outline_fallback"
    assert len(result["segments"]) == 6
    assert calls == []


def test_on_beat_reports_progress_sequence(monkeypatch):
    beats = [_chat_content(_beat_payload("Good beat.", 7)) for _ in range(6)]
    _install(monkeypatch, beats + [_chat_content({"asset_needs": []})])
    seen = []

    workflow.create_script_draft(
        ROOT, **{**_draft_kwargs(), "on_beat": lambda *args: seen.append(args)}
    )

    assert [(i, total, mode, attempts) for i, total, mode, attempts, _ in seen] == [
        (i, 6, "local_ollama", 1) for i in range(6)
    ]
    assert all(elapsed >= 0 for _, _, _, _, elapsed in seen)


def test_agent_run_records_beat_progress(monkeypatch, tmp_path):
    root = tmp_path / "p"
    (root / "runtime/runs").mkdir(parents=True)

    def fake_draft(*args, **kwargs):
        kwargs["on_beat"](2, 6, "local_ollama", 1, 12.5)
        return {
            "topic": "Chủ đề kiểm thử",
            "status": "NEEDS_EVIDENCE",
            "generation_mode": "local_ollama",
            "asset_needs": [],
        }

    monkeypatch.setattr(workflow, "create_script_draft", fake_draft)
    run = workflow.run_content_agent(
        root, root / "runtime/engine.db",
        "Chủ đề kiểm thử", "one-moment-one-read",
    )

    assert run["current_beat"] == 3
    assert run["total_beats"] == 6
    assert run["last_beat_mode"] == "local_ollama"
    listed = _list_runs(root)
    assert listed[0]["current_beat"] == 3
    assert listed[0]["total_beats"] == 6
