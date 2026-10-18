"""Tests for /api/assets/approve-candidate route in apps/web_ui/server.py.

Verifies post-merge audit gap #3: the verified-asset review endpoint must
apply supplied grant_fields to rights_scope_json instead of returning before
persisting them.
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest

from apps.asset_library.discovery import ExternalAssetCandidate
from apps.web_ui.server import make_handler


def _make_handler(db_path: Path):
    Handler = make_handler(db_path)
    handler = Handler.__new__(Handler)
    handler.rfile = BytesIO(b"")
    handler.wfile = BytesIO()
    handler.headers = {}
    handler.path = ""
    handler.command = "POST"
    handler.client_address = ("127.0.0.1", 12345)
    handler.requestline = "POST /api/assets/approve-candidate HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    return handler


def _post(handler, payload: dict) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8")
    handler.rfile = BytesIO(body)
    handler.wfile = BytesIO()
    handler.headers = {"Content-Length": str(len(body))}
    handler.path = "/api/assets/approve-candidate"
    handler.command = "POST"
    handler.do_POST()
    raw = handler.wfile.getvalue()
    first_line = raw.split(b"\r\n", 1)[0]
    status_code = int(first_line.split(b" ", 2)[1])
    body_part = raw.split(b"\r\n\r\n", 1)[1]
    data = json.loads(body_part)
    return status_code, data


_BASE_PAYLOAD = {
    "candidate_id": "commons:12345",
    "rights_reviewed": True,
    "requirement": {
        "requirement_id": "req-1",
        "resource_type": "image",
        "entity_id": "entity-1",
        "purpose": "background",
        "context": "match highlight",
        "content_objective": "shortform analysis",
    },
}

_VALID_GRANT = {
    "platforms": ["youtube"],
    "territories": ["VN"],
    "commercial": True,
    "monetization": False,
    "expires_at": "2027-12-31",
    "edit_allowed": True,
    "credit_required": True,
    "credit_text": "Test Creator",
    "clip_limit": 5,
    "license": "CC BY 4.0",
    "source": "Wikimedia Commons",
    "reviewed_by": "test_user",
    "notes": "test grant",
}


def _candidate() -> ExternalAssetCandidate:
    return ExternalAssetCandidate(
        candidate_id="commons:12345",
        provider="Wikimedia Commons",
        title="Test image",
        source_url="https://commons.wikimedia.org/wiki/File:Test.jpg",
        thumbnail_url="https://thumb.wikimedia.org/thumb.jpg",
        media_type="IMAGE",
        mime_type="image/jpeg",
        width=1000,
        height=800,
        size_bytes=50000,
        license_name="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        creator="Test Creator",
        credit="Test Creator / CC BY 4.0",
    )


def _install_monkeys(monkeypatch):
    monkeypatch.setattr(
        "apps.asset_library.discovery._candidate_by_id",
        lambda candidate_id, api_keys=None: _candidate(),
    )
    monkeypatch.setattr(
        "apps.asset_library.discovery._download_candidate",
        lambda candidate, api_keys=None: (b"\xff\xd8\xff\x00fake-jpeg", "image/jpeg"),
    )


def test_approve_candidate_with_valid_grant_persists_scope(tmp_path, monkeypatch):
    _install_monkeys(monkeypatch)
    db_path = tmp_path / "runtime" / "engine.db"
    handler = _make_handler(db_path)
    payload = {**_BASE_PAYLOAD, **_VALID_GRANT}
    status, data = _post(handler, payload)
    assert status == 201, data
    assert data["status"] == "SAVED"
    assert data["rights_state"] == "verified"
    assert data["rights_scope_persisted"] is True

    from apps.asset_library.registry import connect

    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT rights_state, rights_scope_json FROM assets WHERE asset_id = ?",
            (data["asset_id"],),
        ).fetchone()
    finally:
        conn.close()

    assert row["rights_state"] == "verified"
    scope = json.loads(row["rights_scope_json"])
    assert scope["platforms"] == ["youtube"]
    assert scope["territories"] == ["VN"]
    assert scope["commercial"] is True
    assert scope["monetization"] is False
    assert scope["expires_at"] == "2027-12-31"
    assert scope["edit_allowed"] is True
    assert scope["credit"] == {"required": True, "text": "Test Creator"}
    assert scope["clip_limit"] == 5
    assert scope["license"] == "CC BY 4.0"
    assert scope["source"] == "Wikimedia Commons"
    assert scope["granted_by"] == "human"


def test_approve_candidate_with_invalid_grant_returns_400(tmp_path, monkeypatch):
    _install_monkeys(monkeypatch)
    db_path = tmp_path / "runtime" / "engine.db"
    handler = _make_handler(db_path)
    payload = {**_BASE_PAYLOAD, "expires_at": "not-a-date"}
    status, data = _post(handler, payload)
    assert status == 400, data
    assert "error" in data


def test_approve_candidate_without_grant_saves_asset_deny_default(tmp_path, monkeypatch):
    _install_monkeys(monkeypatch)
    db_path = tmp_path / "runtime" / "engine.db"
    handler = _make_handler(db_path)
    status, data = _post(handler, _BASE_PAYLOAD)
    assert status == 201, data
    assert data["status"] == "SAVED"
    assert data["rights_state"] == "verified"
    assert data["rights_scope_persisted"] is True

    from apps.asset_library.registry import connect

    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT rights_state, rights_scope_json FROM assets WHERE asset_id = ?",
            (data["asset_id"],),
        ).fetchone()
    finally:
        conn.close()

    assert row["rights_state"] == "verified"
    scope = json.loads(row["rights_scope_json"])
    assert scope["platforms"] == []
    assert scope["territories"] == []
    assert scope["commercial"] is False
    assert scope["monetization"] is False
    assert scope["granted_by"] == "deny-default"
