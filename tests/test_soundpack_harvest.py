"""Freesound harvester: machine-picked locked sounds, mocked network."""

import json
import shutil
from pathlib import Path

import pytest

from apps.soundpack import harvest
from apps.soundpack.harvest import _pick, harvest as run_harvest

REPO = Path(__file__).resolve().parent.parent


def _item(sound_id, name, downloads, rating, duration, tags):
    return {"id": sound_id, "name": name, "license": "CC0", "duration": duration,
            "num_downloads": downloads, "avg_rating": rating, "tags": tags,
            "previews": {"preview-hq-mp3": f"https://cdn.invalid/{sound_id}.mp3"},
            "url": f"https://freesound.org/sounds/{sound_id}/"}


def test_pick_prefers_loop_and_skips_voice():
    items = [
        _item(1, "Vocal pad", 50000, 5.0, 120.0, ["ambient", "voice"]),
        _item(2, "Plain drone", 100, 3.0, 120.0, ["ambient"]),
        _item(3, "Loop drone", 5000, 4.0, 120.0, ["ambient", "loop"]),
    ]
    pick = _pick(items, 45.0, None, avoid_voice=True)
    assert pick and pick["id"] == 3
    assert _pick(items, 200.0, None, avoid_voice=True) is None
    assert _pick([], 45.0, None, avoid_voice=True) is None


def _stage(tmp_path):
    pack = tmp_path / "soundpacks" / "v1"
    (pack / "tracks").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / "soundpacks/v1/manifest.json", pack / "manifest.json")
    return tmp_path


def test_harvest_installs_and_updates_manifest(monkeypatch, tmp_path):
    _stage(tmp_path)
    monkeypatch.setenv("FREESOUND_API_KEY", "test-key")
    monkeypatch.setattr(harvest, "_api_search", lambda *a, **k: [
        _item(11, "Vocal bed", 99999, 5.0, 120.0, ["voice"]),
        _item(12, "Good bed", 1000, 4.5, 90.0, ["ambient", "loop"]),
    ])
    monkeypatch.setattr(harvest, "_download",
                        lambda url, dest: dest.write_bytes(b"fake-mp3-bytes") or dest)
    monkeypatch.setattr(harvest, "_probe_duration", lambda path: 90.0)
    report = run_harvest(tmp_path, ["neutral-pad"])
    slot = report["slots"]["neutral-pad"]
    assert slot["status"] == "INSTALLED" and slot["freesound_id"] == 12
    assert (tmp_path / "soundpacks/v1/tracks/neutral-pad.mp3").is_file()
    sidecar = json.loads((tmp_path / "soundpacks/v1/tracks/neutral-pad.json").read_text())
    assert sidecar["license"] == "CC0" and sidecar["commercial_use"].startswith("allowed")
    manifest = json.loads((tmp_path / "soundpacks/v1/manifest.json").read_text())
    bed = next(b for b in manifest["beds"] if b["bed_id"] == "neutral-pad")
    assert bed["file"] == "tracks/neutral-pad.mp3" and "provisional" not in bed
    assert (tmp_path / "soundpacks" / f"harvest-report-{report['date']}.json").is_file()


def test_harvest_skips_without_eligible(monkeypatch, tmp_path):
    _stage(tmp_path)
    monkeypatch.setenv("FREESOUND_API_KEY", "test-key")
    monkeypatch.setattr(harvest, "_api_search", lambda *a, **k: [])
    report = run_harvest(tmp_path, ["tension-pad"])
    assert report["slots"]["tension-pad"]["status"] == "SKIPPED"


def test_harvest_needs_key_and_known_slots(monkeypatch, tmp_path):
    _stage(tmp_path)
    monkeypatch.delenv("FREESOUND_API_KEY", raising=False)
    with pytest.raises(ValueError, match="FREESOUND_API_KEY"):
        run_harvest(tmp_path, ["neutral-pad"])
    monkeypatch.setenv("FREESOUND_API_KEY", "test-key")
    with pytest.raises(ValueError, match="Unknown soundpack slots"):
        run_harvest(tmp_path, ["rock-anthem"])
