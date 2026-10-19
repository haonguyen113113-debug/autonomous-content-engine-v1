"""Licensed crest store: only owner-supplied, rights-reviewed files resolve.

Locks the no-web-crest policy: nothing may be downloaded or copied from the
network; an unreviewed or file-less entry must never yield a usable path.
"""

import json
from pathlib import Path

from apps.sportskit.crests import (
    CRESTS_DIR,
    crest_status,
    normalize_club_key,
    resolve_crest,
)

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = CRESTS_DIR / "manifest.json"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
CLIP_CLUBS = ["manchester-city", "paris-saint-germain"]


def test_resolve_miss_returns_none():
    # Clip 1 clubs have no licensed file yet; every spelling must miss.
    for query in ("manchester-city", "Manchester City", "Man City", "MC",
                  "paris-saint-germain", "Paris Saint-Germain", "Paris", "PSG",
                  "no-such-club", "", "   "):
        assert resolve_crest(query) is None, query
    assert resolve_crest(None) is None


def test_normalize_strips_accents_and_case():
    assert normalize_club_key("Công an Hà Nội") == normalize_club_key("cong an ha noi")
    assert normalize_club_key("Atlético de Madrid") == normalize_club_key("atletico de madrid")
    assert normalize_club_key("PSG") == normalize_club_key("psg")


def test_manifest_schema_valid():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(data.get("crests"), list)
    seen = set()
    for entry in data["crests"]:
        assert set(entry) >= {"club_slug", "file", "source", "license",
                              "acquired_at", "rights_reviewed", "allowed_use"}, entry
        assert isinstance(entry["club_slug"], str) and entry["club_slug"].strip()
        assert entry["file"] is None or isinstance(entry["file"], str)
        if isinstance(entry["file"], str):
            assert ".." not in entry["file"] and "/" not in entry["file"].replace("\\", "/")
            assert Path(entry["file"]).suffix.lower() in IMAGE_SUFFIXES or not entry["file"].strip()
        assert isinstance(entry["source"], str) and entry["source"].strip()
        assert isinstance(entry["license"], str) and entry["license"].strip()
        assert isinstance(entry["acquired_at"], str)
        assert isinstance(entry["rights_reviewed"], bool)
        assert isinstance(entry["allowed_use"], str) and entry["allowed_use"].strip()
        assert entry["club_slug"] not in seen, entry["club_slug"]
        seen.add(entry["club_slug"])


def test_no_unlicensed_crest_usable():
    """Every on-disk image needs a rights_reviewed manifest entry; clip clubs wait."""
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    licensed_files = {str(e["file"]).strip().lower() for e in data["crests"]
                      if e.get("rights_reviewed") is True and isinstance(e.get("file"), str)}
    for path in CRESTS_DIR.iterdir():
        if path.suffix.lower() in IMAGE_SUFFIXES:
            assert path.name.lower() in licensed_files, path.name
    status = crest_status(CLIP_CLUBS)
    for slug in CLIP_CLUBS:
        assert status[slug]["licensed"] is False, slug
        assert resolve_crest(slug) is None, slug
