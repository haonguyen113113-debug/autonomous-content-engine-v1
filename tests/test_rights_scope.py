"""Rights scope: per-upload-intent grant is separate from image suitability.

Locks: verified != usable everywhere; unknown/YouTube sources deny by
default; copyright exceptions always need a human (LLM must not conclude);
migration is idempotent and never overwrites explicit scopes.
"""

import json
import sqlite3

import pytest

from apps.asset_library.rights_scope import (
    RIGHTS_SCOPE_SCHEMA_VERSION,
    build_rights_scope,
    crest_entry_to_scope,
    default_deny_scope,
    ensure_rights_scope_schema,
    is_usable_for,
    scope_from_asset,
    scope_from_legacy,
    validate_scope,
)


def _granted_asset(**overrides):
    scope = build_rights_scope(
        platforms=["youtube"],
        territories=["VN"],
        commercial=True,
        monetization=True,
        edit_allowed=True,
        credit_required=True,
        credit_text="Etihad Airways / CC BY 4.0",
        license="CC BY 4.0",
        source="wikimedia_commons",
        reviewed_by="owner",
    )
    asset = {
        "asset_id": "a-1",
        "rights_state": "verified",
        "lifecycle_state": "active",
        "license_type": "CC BY 4.0",
        "source_type": "wikimedia_commons",
        "source_url": "https://commons.wikimedia.org/wiki/File:Etihad.jpg",
        "creator": "Etihad Airways",
        "metadata": {},
        "rights_scope": scope,
    }
    asset.update(overrides)
    return asset


def _purpose(**overrides):
    purpose = {
        "platform": "youtube",
        "territory": "VN",
        "commercial": True,
        "monetization": True,
        "edit": True,
        "credit_planned": True,
        "use_count": 0,
    }
    purpose.update(overrides)
    return purpose


def test_verified_without_scope_is_not_usable():
    asset = {
        "asset_id": "legacy",
        "rights_state": "verified",
        "lifecycle_state": "active",
        "license_type": "unknown",
        "source_type": "unknown",
        "metadata": {},
    }
    out = is_usable_for(asset, _purpose())
    assert out["allowed"] is False
    assert out["required_action"] == "human_review"
    assert "unknown-source-or-license" in out["reasons"]


def test_matching_grant_allows():
    out = is_usable_for(_granted_asset(), _purpose())
    assert out["allowed"] is True
    assert out["required_action"] == "none"
    assert "ok" in out["reasons"]
    assert out["scope"]["platforms"] == ["youtube"]
    assert out["scope"]["credit"] == {
        "required": True, "text": "Etihad Airways / CC BY 4.0",
    }


def test_platform_mismatch_denies_without_human():
    out = is_usable_for(_granted_asset(), _purpose(platform="tiktok"))
    assert out["allowed"] is False
    assert out["required_action"] == "none"
    assert "platform-not-granted:tiktok" in out["reasons"]


def test_territory_mismatch_and_wildcard():
    out = is_usable_for(_granted_asset(), _purpose(territory="US"))
    assert out["allowed"] is False
    assert "territory-not-granted:US" in out["reasons"]
    worldwide = _granted_asset()
    worldwide["rights_scope"]["territories"] = ["*"]
    assert is_usable_for(worldwide, _purpose(territory="US"))["allowed"] is True


def test_commercial_and_monetization_gates():
    noncommercial = _granted_asset()
    noncommercial["rights_scope"]["commercial"] = False
    noncommercial["rights_scope"]["monetization"] = False
    out = is_usable_for(noncommercial, _purpose())
    assert out["allowed"] is False
    assert "commercial-not-granted" in out["reasons"]
    assert "monetization-not-granted" in out["reasons"]
    assert out["required_action"] == "none"


def test_expired_grant_needs_human():
    asset = _granted_asset()
    asset["rights_scope"]["expires_at"] = "2020-01-31"
    out = is_usable_for(asset, _purpose(now="2026-10-16"))
    assert out["allowed"] is False
    assert "rights-expired" in out["reasons"]
    assert out["required_action"] == "human_review"


def test_edit_and_credit_gates():
    asset = _granted_asset()
    asset["rights_scope"]["edit_allowed"] = False
    out = is_usable_for(asset, _purpose())
    assert out["allowed"] is False
    assert "edit-not-allowed" in out["reasons"]
    asset = _granted_asset()
    out = is_usable_for(asset, _purpose(credit_planned=False))
    assert out["allowed"] is False
    assert "credit-required-unplanned" in out["reasons"]
    assert out["required_action"] == "none"


def test_clip_limit():
    asset = _granted_asset()
    asset["rights_scope"]["clip_limit"] = 2
    assert is_usable_for(asset, _purpose(use_count=1))["allowed"] is True
    out = is_usable_for(asset, _purpose(use_count=2))
    assert out["allowed"] is False
    assert "clip-limit-reached:2/2" in out["reasons"]


def test_youtube_and_unclear_sources_deny_by_default():
    for source in (
        {"source_type": "youtube", "source_url": "https://www.youtube.com/watch?v=x"},
        {"source_type": "unknown", "source_url": None},
        {"source_type": "wikimedia_commons", "source_url": None, "license_type": "pending owner grant"},
    ):
        asset = {
            "asset_id": "risky",
            "rights_state": "verified",
            "lifecycle_state": "active",
            "license_type": source.pop("license_type", "unknown"),
            "metadata": {},
            **source,
        }
        out = is_usable_for(asset, _purpose())
        assert out["allowed"] is False, source
        assert out["required_action"] == "human_review", source


def test_copyright_exception_always_needs_human():
    asset = _granted_asset()
    asset["rights_scope"]["copyright_exception"] = True
    out = is_usable_for(asset, _purpose())
    assert out["allowed"] is False
    assert "copyright-exception-requires-human" in out["reasons"]
    assert out["required_action"] == "human_review"
    # Asset-level flag (e.g. disputed ownership in metadata) behaves the same.
    asset = _granted_asset()
    asset["metadata"] = {"copyright_exception": True}
    out = is_usable_for(asset, _purpose())
    assert out["allowed"] is False
    assert out["required_action"] == "human_review"


def test_unverified_asset_denies_even_with_scope():
    asset = _granted_asset(rights_state="unverified")
    out = is_usable_for(asset, _purpose())
    assert out["allowed"] is False
    assert "rights-not-verified" in out["reasons"]
    assert out["required_action"] == "human_review"


def test_crest_pending_denies_and_reviewed_parses():
    pending = {
        "club_slug": "manchester-city",
        "file": None,
        "source": "owner-supplied (pending)",
        "license": "pending owner grant",
        "acquired_at": "",
        "rights_reviewed": False,
        "allowed_use": "pending",
    }
    out = is_usable_for(pending, _purpose())
    assert out["allowed"] is False
    assert out["required_action"] == "human_review"
    cleared = dict(
        pending,
        rights_reviewed=True,
        file="manchester-city.png",
        license="club media licence 2026-27",
        acquired_at="2026-10-01",
        allowed_use="broadcast+social 2026-27",
    )
    scope = crest_entry_to_scope(cleared)
    assert scope["platforms"] != []
    assert scope["expires_at"] == "2027-12-31"
    assert scope["edit_allowed"] is True  # placement fit only, see module notes
    out = is_usable_for(cleared, _purpose())
    assert out["allowed"] is True


def test_legacy_backfill_open_license_keeps_grant_unknown_denies():
    open_asset = {
        "asset_id": "open",
        "rights_state": "verified",
        "lifecycle_state": "active",
        "license_type": "CC BY 4.0",
        "source_type": "wikimedia_commons",
        "source_url": "https://commons.wikimedia.org/wiki/File:X.jpg",
        "creator": "Some Author",
        "metadata": {"license_credit": "Some Author / CC BY 4.0"},
    }
    scope = scope_from_legacy(open_asset)
    assert scope["commercial"] is True and scope["monetization"] is True
    assert scope["credit"] == {"required": True, "text": "Some Author / CC BY 4.0"}
    out = is_usable_for(open_asset, _purpose(credit_planned=True, edit=True))
    assert out["allowed"] is True
    owned = dict(open_asset, license_type="owned", source_type="self_created")
    assert scope_from_legacy(owned)["commercial"] is True
    murky = dict(open_asset, license_type="unknown", source_type="unknown")
    assert is_usable_for(murky, _purpose())["allowed"] is False


def test_scope_schema_versioned_and_validated():
    assert RIGHTS_SCOPE_SCHEMA_VERSION == 1
    scope = build_rights_scope(platforms=["youtube"], territories=["VN"])
    assert scope["schema_version"] == 1
    assert validate_scope(scope) == []
    bad = dict(scope, schema_version=99)
    assert validate_scope(bad) != []
    with pytest.raises(ValueError):
        build_rights_scope(clip_limit=-1)
    tampered = dict(scope, schema_version=99)
    out = is_usable_for(_granted_asset(rights_scope=tampered), _purpose())
    assert out["allowed"] is False
    assert out["required_action"] == "human_review"


def _legacy_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE assets (asset_id TEXT PRIMARY KEY, license_type TEXT,"
        " source_type TEXT, source_url TEXT, creator TEXT, rights_state TEXT,"
        " lifecycle_state TEXT, metadata_json TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO assets VALUES ('open-1','CC BY-SA 4.0','wikimedia_commons',"
        " 'https://commons.wikimedia.org/wiki/File:Y.jpg','Author','verified',"
        " 'active','{}')"
    )
    conn.execute(
        "INSERT INTO assets VALUES ('murky-1','unknown','unknown',NULL,NULL,"
        " 'unverified','ingested','{}')"
    )
    conn.commit()


def test_migration_idempotent_and_preserves_explicit_scopes(tmp_path=None):
    conn = sqlite3.connect(":memory:")
    try:
        _legacy_table(conn)
        first = ensure_rights_scope_schema(conn)
        assert first["added_column"] is True
        assert first["backfilled"] == 2
        row = conn.execute(
            "SELECT rights_scope_json FROM assets WHERE asset_id='open-1'"
        ).fetchone()[0]
        stored = json.loads(row)
        assert stored["schema_version"] == RIGHTS_SCOPE_SCHEMA_VERSION
        assert stored["commercial"] is True
        murky = json.loads(
            conn.execute(
                "SELECT rights_scope_json FROM assets WHERE asset_id='murky-1'"
            ).fetchone()[0]
        )
        assert murky["platforms"] == [] and murky["clip_limit"] == 0
        # Human narrows the open grant; reruns must preserve it verbatim.
        narrowed = build_rights_scope(
            platforms=["youtube"], territories=["VN"], license="CC BY-SA 4.0",
        )
        conn.execute(
            "UPDATE assets SET rights_scope_json=? WHERE asset_id='open-1'",
            (json.dumps(narrowed),),
        )
        conn.commit()
        second = ensure_rights_scope_schema(conn)
        assert second == {
            "schema_version": RIGHTS_SCOPE_SCHEMA_VERSION,
            "added_column": False,
            "backfilled": 0,
            "preserved": 2,
        }
        kept = json.loads(
            conn.execute(
                "SELECT rights_scope_json FROM assets WHERE asset_id='open-1'"
            ).fetchone()[0]
        )
        assert kept["territories"] == ["VN"]
    finally:
        conn.close()


def test_scope_from_asset_prefers_explicit_over_legacy():
    explicit = build_rights_scope(platforms=["tiktok"], territories=["*"])
    asset = _granted_asset(rights_scope_json=json.dumps(explicit))
    scope, derivation = scope_from_asset(asset)
    assert scope["platforms"] == ["tiktok"]
    assert derivation["errors"] == []
    assert default_deny_scope()["clip_limit"] == 0
