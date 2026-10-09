import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps import voice_tts


def _make_run(root: Path, run_id="abcdef123456"):
    runs = root / "runtime/runs"
    runs.mkdir(parents=True)
    run = {
        "run_id": run_id,
        "status": "x",
        "script_owner_approved": True,
        "draft": {"segments": [
            {"narration": "Carlos Espi ghi bàn quyết định trận ra mắt."},
            {"narration": "Cao 1,94m và mới 21 tuổi."},
        ]},
    }
    (runs / f"{run_id}.json").write_text(
        json.dumps(run, ensure_ascii=False), encoding="utf-8")


def _make_profile(root: Path):
    voice = root / "runtime/voice"
    voice.mkdir(parents=True)
    (voice / "allen-reference.wav").write_bytes(b"RIFF" + b"\x00" * 100)
    (voice / "profile.json").write_text(
        json.dumps({"reference_file": "allen-reference.wav"}), encoding="utf-8")


def test_voice_preview_pipes_utf8_to_worker(monkeypatch, tmp_path):
    _make_run(tmp_path)
    _make_profile(tmp_path)
    monkeypatch.setattr(voice_tts, "_runtime_python", lambda root: Path("tts-python"))
    seen = {}

    def fake_run(*args, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(voice_tts.subprocess, "run", fake_run)
    result = voice_tts.synthesize_voice_preview(tmp_path, "abcdef123456")
    assert seen["encoding"] == "utf-8"
    assert seen["text"] is True
    assert "ậ" in seen["input"]  # Vietnamese survives the pipe
    assert result["audio_url"] == "/api/voice-preview/abcdef123456-voice-preview.wav"
    saved = json.loads((tmp_path / "runtime/runs/abcdef123456.json").read_text(encoding="utf-8"))
    assert saved["status"] == "WAITING_FOR_VOICE_AUDIT"
    assert saved["voice_preview"]["path"] == "abcdef123456-voice-preview.wav"


def test_voice_preview_blocks_unresolved_markers(tmp_path):
    _make_run(tmp_path)
    _make_profile(tmp_path)
    run_path = tmp_path / "runtime/runs/abcdef123456.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["draft"]["segments"].append({"narration": "[CẦN NGUỒN] thiếu số liệu."})
    run_path.write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="research placeholders"):
        voice_tts.synthesize_voice_preview(tmp_path, "abcdef123456")


def test_clean_for_tts_removes_surrogates_and_controls():
    dirty = "Espi ghi bàn.\udc81\udfff\x00\x07 legitimate — text"
    clean = voice_tts._clean_for_tts(dirty)
    assert "\udc81" not in clean and "\udfff" not in clean
    assert "\x00" not in clean and "\x07" not in clean
    assert "Espi ghi bàn." in clean
    clean.encode("utf-8")  # must not raise


def test_voice_worker_gets_utf8_environment(monkeypatch, tmp_path):
    _make_run(tmp_path)
    _make_profile(tmp_path)
    monkeypatch.setattr(voice_tts, "_runtime_python", lambda root: Path("tts-python"))
    seen = {}

    def fake_run(*args, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(voice_tts.subprocess, "run", fake_run)
    voice_tts.synthesize_voice_preview(tmp_path, "abcdef123456")
    assert seen["env"]["PYTHONUTF8"] == "1"
    assert seen["env"]["PYTHONIOENCODING"] == "utf-8"
