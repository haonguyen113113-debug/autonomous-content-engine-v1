"""Preset-voice path: Southern built-ins work without a reference file."""

import json
from pathlib import Path

from apps.voice_tts import synthesize_voice_preview


def _approved_run(root: Path, run_id="abcdef123456"):
    (root / "runtime/runs").mkdir(parents=True)
    run = {
        "run_id": run_id,
        "status": "NEEDS_OWNER_REVIEW",
        "script_owner_approved": True,
        "draft": {"segments": [
            {"id": "beat-1", "narration": "Xin chào, đây là bản thử giọng miền Nam."},
        ]},
    }
    (root / "runtime/runs" / f"{run_id}.json").write_text(
        json.dumps(run, ensure_ascii=False), encoding="utf-8")


def test_preset_voice_skips_reference_and_records_voice(monkeypatch, tmp_path):
    root = tmp_path / "project"
    _approved_run(root)
    (root / ".env").write_text("TTS_VOICE=Adam\n", encoding="utf-8")
    fake_python = root / "runtime/tts-venv/Scripts/python.exe"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_bytes(b"fake")

    seen = {}

    class Done:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, **kwargs):
        seen["env_voice"] = kwargs["env"].get("TTS_VOICE")
        return Done()

    import apps.voice_tts as voice_tts
    monkeypatch.setattr(voice_tts.subprocess, "run", fake_run)
    result = synthesize_voice_preview(root, "abcdef123456")
    assert result["voice"] == "Adam"
    assert seen["env_voice"] == "Adam"
    run = json.loads((root / "runtime/runs/abcdef123456.json").read_text(encoding="utf-8"))
    assert run["voice_preview"]["voice"] == "Adam"
    assert run["status"] == "WAITING_FOR_VOICE_AUDIT"


def test_reference_still_required_without_preset(tmp_path):
    import pytest
    root = tmp_path / "project"
    _approved_run(root)
    with pytest.raises(ValueError, match="voice reference"):
        synthesize_voice_preview(root, "abcdef123456")
