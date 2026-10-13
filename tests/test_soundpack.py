"""Locked soundpack: fixed mapping, no discovery."""

import json

import pytest

from apps.soundpack import pack

REPO = __import__("pathlib").Path(__file__).resolve().parent.parent


def test_manifest_valid_and_locked():
    manifest = pack.load_manifest(REPO)
    assert manifest["version"] == "1.0.0"
    beds = {bed["bed_id"]: bed for bed in manifest["beds"]}
    assert len(beds) == 4
    for bed in beds.values():
        assert (REPO / "soundpacks/v1" / bed["file"]).is_file()
        assert bed["license"] in {"CC0", "BY 4.0"}
    for form in ("one-moment-one-read", "explain-the-pattern", "player-role-read",
                 "longform-tactical-deep-dive", "longform-player-role-study"):
        assert manifest["mapping"][form] in beds
    assert len(manifest["stingers"]) == 3


def test_resolve_default_override_and_none():
    resolved = pack.resolve_sound(REPO, "one-moment-one-read", "short")
    assert resolved["enabled"] is True and resolved["bed_id"] == "tension-pad"
    assert resolved["bed_file"].endswith("tension-pad.mp3")
    uplifting = pack.resolve_sound(REPO, "player-role-read", "short")
    assert uplifting["bed_id"] == "uplift-pad"
    forced = pack.resolve_sound(REPO, "one-moment-one-read", "short",
                                override="dramatic-pad")
    assert forced["bed_id"] == "dramatic-pad"
    off = pack.resolve_sound(REPO, "one-moment-one-read", "short", override="none")
    assert off == {"enabled": False, "reason": "disabled by owner override"}
    with pytest.raises(ValueError, match="Unknown soundpack bed"):
        pack.resolve_sound(REPO, "one-moment-one-read", "short", override="rock-anthem")


def test_plan_stingers_hook_chapters_endcard(tmp_path):
    tracks = REPO / "soundpacks/v1/tracks"
    stingers = pack.load_manifest(REPO)["stingers"]
    planned = pack.plan_stingers(stingers, [0.0, 12.5, 25.0], 40.0, tracks)
    by_id = {}
    for item in planned:
        by_id.setdefault(item["sting_id"], []).append(item["at"])
    assert by_id["hook-hit"] == [0.0]
    assert by_id["transition-whoosh"] == [12.5, 25.0]
    assert by_id["end-jingle"] == [38.0]
    for item in planned:
        assert item["volume"] > 0


def test_plan_stingers_skips_missing_files(tmp_path):
    planned = pack.plan_stingers(
        [{"sting_id": "ghost", "file": "tracks/ghost.mp3", "place": "hook",
          "at_seconds": 0.0, "mix_volume": 0.5}], [0.0], 40.0,
        REPO / "soundpacks/v1/tracks")
    assert planned == []


def test_audio_filter_ducks_voice_first():
    filt, out = pack.audio_filter(1, 2, [3, 4], [
        {"sting_id": "a", "file": "a.mp3", "at": 0.0, "volume": 0.5},
        {"sting_id": "b", "file": "b.mp3", "at": 12.5, "volume": 0.4},
    ], 40.0, 0.1, {"threshold": 0.02, "ratio": 8, "attack_ms": 20, "release_ms": 400})
    assert out == "[aout]"
    assert "[2:a]" in filt and "[1:a]" in filt
    assert "asplit=2[vox][voxsc]" in filt
    assert "sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400" in filt
    assert "amix=inputs=2:duration=first" in filt
    assert "loudnorm=I=-14:TP=-1.5:LRA=11" in filt
    assert "adelay=0|0" in filt and "adelay=12500|12500" in filt


def test_sound_enabled_defaults_on(monkeypatch, tmp_path):
    monkeypatch.delenv("SOUNDPACK_ENABLED", raising=False)
    assert pack.sound_enabled(tmp_path) is True
    monkeypatch.setenv("SOUNDPACK_ENABLED", "false")
    assert pack.sound_enabled(tmp_path) is False


def test_bed_ids_lists_locked_choices():
    assert pack.bed_ids(REPO) == ["tension-pad", "neutral-pad", "uplift-pad", "dramatic-pad"]
    assert pack.bed_ids("/nonexistent-root-xyz") == []
