import shutil
from pathlib import Path

import pytest

from apps.asset_library.discovery import ExternalAssetCandidate
from apps.asset_library.entity_seed import seed_entity_catalog
from apps.asset_library.identity import (
    apply_identity_filter,
    load_identity_profile,
    screen_candidates,
)
from apps.asset_library.registry import connect


REPO_ROOT = Path(__file__).resolve().parent.parent


def _seeded_db(tmp_path: Path) -> Path:
    root = tmp_path / "identity"
    data = root / "data/entities"
    data.mkdir(parents=True)
    for name in ("competitions.json", "clubs.json", "national_teams.json",
                 "players.json", "relationships.json", "README.md"):
        src = REPO_ROOT / "data/entities" / name
        if src.exists():
            shutil.copy(src, data / name)
    seed_entity_catalog(root)
    return root / "runtime/engine.db"


def _candidate(candidate_id, title, provider="Wikimedia Commons"):
    return ExternalAssetCandidate(
        candidate_id=candidate_id, provider=provider, title=title,
        source_url=f"https://example.invalid/{candidate_id}",
        thumbnail_url="", media_type="IMAGE", mime_type="image/jpeg",
        width=1600, height=900, size_bytes=1000,
        license_name="CC BY-SA 4.0", license_url=None,
        creator=None, credit=None,
    )


def test_profile_loads_from_seed(tmp_path):
    db_path = _seeded_db(tmp_path)
    conn = connect(db_path)
    try:
        profile = load_identity_profile(conn, "player:bruno-fernandes")
    finally:
        conn.close()
    assert profile is not None
    assert profile.display_name == "Bruno Miguel Borges Fernandes"
    assert "manchester united" in profile.include_terms
    assert "de souza" in profile.exclude_terms
    assert "goalkeeper" in profile.exclude_terms
    assert any(name == "Bruno Fernandes das Dores de Souza" for _, name in profile.other_names)


def test_unknown_entity_returns_none(tmp_path):
    db_path = _seeded_db(tmp_path)
    conn = connect(db_path)
    try:
        assert load_identity_profile(conn, "player:nobody") is None
        assert load_identity_profile(conn, "club:arsenal") is None
    finally:
        conn.close()


def test_screening_drops_wrong_person_and_flags_uncertain(tmp_path):
    db_path = _seeded_db(tmp_path)
    conn = connect(db_path)
    try:
        profile = load_identity_profile(conn, "player:bruno-fernandes")
    finally:
        conn.close()
    candidates = [
        _candidate("1", "Bruno Fernandes de Souza 04.jpg"),
        _candidate("2", "Bruno Fernandes goalkeeper training"),
        _candidate("3", "Manchester United v Newcastle United (17).jpg"),
        _candidate("4", "Bruno Fernandes Portugal, 2018.jpg"),
        _candidate("5", "Old Trafford at night"),
    ]
    kept, removed = screen_candidates(candidates, profile)
    assert [c.candidate_id for c in kept] == ["3", "4", "5"]
    assert {c.identity for c in kept} == {"match", "uncertain"}
    by_id = {c.candidate_id: c.identity for c in kept}
    assert by_id["3"] == "match"
    assert by_id["4"] == "match"
    assert by_id["5"] == "uncertain"
    assert [(r["candidate_id"], r["reason"]) for r in removed] == [
        ("1", "names a different person: Bruno Fernandes de Souza"),
        ("2", "matches exclude term: goalkeeper"),
    ]


def test_apply_filter_fails_open_on_unknown_entity(tmp_path):
    db_path = _seeded_db(tmp_path)
    candidates = [_candidate("1", "Anything at all")]
    kept, summary = apply_identity_filter(candidates, "player:nobody", db_path)
    assert kept == candidates
    assert summary["status"] == "unknown_entity"
    assert summary["removed"] == []


def test_apply_filter_end_to_end(tmp_path):
    db_path = _seeded_db(tmp_path)
    candidates = [
        _candidate("1", "Bruno Fernandes de Souza 02.jpg"),
        _candidate("2", "Manchester United celebrate"),
    ]
    kept, summary = apply_identity_filter(
        candidates, "player:bruno-fernandes", db_path
    )
    assert [c.candidate_id for c in kept] == ["2"]
    assert summary["status"] == "screened"
    assert summary["display_name"] == "Bruno Miguel Borges Fernandes"
    assert summary["kept"] == 1
    assert len(summary["removed"]) == 1
