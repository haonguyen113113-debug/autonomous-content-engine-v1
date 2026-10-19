"""Owner drop importer: provenance-gated intake, no downloads."""

import shutil
from pathlib import Path

import pytest

from apps.soundpack import intake
from apps.soundpack.intake import import_pack

REPO = Path(__file__).resolve().parent.parent


def _drop(tmp_path, rows):
    drop = tmp_path / "drop"
    drop.mkdir(parents=True, exist_ok=True)
    header = ("slot,file,title,creator,license,license_url,page_url,source_url,"
              "commercial_ok,content_id_risk,platforms,credit_text,catalog_id\n")
    (drop / "register.csv").write_text(header + "".join(rows), encoding="utf-8")
    (drop / "hook-hit.mp3").write_bytes(b"fake-audio-bytes")
    return drop


def _pack(tmp_path):
    pack = tmp_path / "soundpacks" / "v1"
    (pack / "tracks").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / "soundpacks/v1/manifest.json", pack / "manifest.json")
    return tmp_path


def test_import_installs_clean_row(monkeypatch, tmp_path):
    _pack(tmp_path)
    drop = _drop(tmp_path, ["hook-hit,hook-hit.mp3,Impact Hit,Universfield,Pixabay Content License,,"
                            "https://pixabay.com/sound-effects/x/,,yes,,YouTube,,AKB-C05\n"])
    monkeypatch.setattr(intake, "_probe_duration", lambda path: 3.0)
    report = import_pack(tmp_path, drop)
    assert len(report["imported"]) == 1 and not report["failed"]
    assert report["imported"][0]["activated"] is True
    assert (tmp_path / "soundpacks/v1/tracks/hook-hit.mp3").is_file()
    assert (tmp_path / "soundpacks/v1/tracks/hook-hit.json").is_file()


def test_import_rejects_provenance_gaps(monkeypatch, tmp_path):
    _pack(tmp_path)
    drop = _drop(tmp_path, [
        "hook-hit,wrong-name.mp3,Impact Hit,Universfield,Pixabay Content License,,"
        "https://pixabay.com/sound-effects/x/,,yes,,YouTube,,AKB-C05\n",
        "transition-whoosh,transition-whoosh.mp3,Whoosh,DS,Pixabay Content License,,,,yes,,YouTube,,AKB-C02\n",
        "build-riser,build-riser.mp3,Riser,DS,CC BY-NC,,https://x.invalid/,,yes,,YouTube,,AKB-C07\n",
        "end-jingle,end-jingle.mp3,Jingle,S,CC0,,https://x.invalid/,,yes,HOLD,YouTube,,\n",
    ])
    for name in ("wrong-name.mp3", "transition-whoosh.mp3", "build-riser.mp3", "end-jingle.mp3"):
        (drop / name).write_bytes(b"fake-audio-bytes")
    monkeypatch.setattr(intake, "_probe_duration", lambda path: 3.0)
    report = import_pack(tmp_path, drop)
    assert not report["imported"] and len(report["failed"]) == 4
    reasons = " ".join(item["reason"] for item in report["failed"])
    assert "exactly" in reasons and "page URL" in reasons
    assert "allowlisted" in reasons and "HOLD" in reasons


def test_import_requires_credit_for_by_and_caps_duration(monkeypatch, tmp_path):
    _pack(tmp_path)
    drop = _drop(tmp_path, ["tension-pad,tension-pad.mp3,Bed,X,BY 4.0,,"
                            "https://x.invalid/,,yes,,YouTube,,TA-L01\n"])
    (drop / "tension-pad.mp3").write_bytes(b"fake-audio-bytes")
    monkeypatch.setattr(intake, "_probe_duration", lambda path: 999.0)
    report = import_pack(tmp_path, drop)
    assert "credit" in report["failed"][0]["reason"]
    drop2 = _drop(tmp_path, ["tension-pad,tension-pad.mp3,Bed,X,CC0,,"
                             "https://x.invalid/,,yes,,YouTube,,\n"])
    (drop2 / "tension-pad.mp3").write_bytes(b"fake-audio-bytes")
    report2 = import_pack(tmp_path, drop2)
    assert "exceeds" in report2["failed"][0]["reason"]


def test_import_needs_register_and_known_slots(monkeypatch, tmp_path):
    _pack(tmp_path)
    with pytest.raises(ValueError, match="register.csv"):
        import_pack(tmp_path, tmp_path / "empty-drop")
    drop = _drop(tmp_path, ["nope-song,nope-song.mp3,X,Y,CC0,,https://x.invalid/,,yes,,YouTube,,\n"])
    (drop / "nope-song.mp3").write_bytes(b"x")
    monkeypatch.setattr(intake, "_probe_duration", lambda path: 3.0)
    report = import_pack(tmp_path, drop)
    assert "Unknown slot" in report["failed"][0]["reason"]
