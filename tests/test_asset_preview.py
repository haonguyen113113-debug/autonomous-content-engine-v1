from pathlib import Path

import pytest

from apps.asset_library.registry import connect
from apps.web_ui.server import _asset_file_info


def _insert(conn, asset_id, stored_path, mime="image/jpeg"):
    conn.execute(
        "INSERT INTO assets (asset_id, original_name, stored_path, asset_type,"
        " size_bytes, sha256, source_type, rights_state, lifecycle_state,"
        " metadata_json, mime_type)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (asset_id, "photo.jpg", stored_path, "image", 10, f"sha-{asset_id}",
         "wikimedia_commons", "unverified", "ingested", "{}", mime),
    )


def test_preview_resolves_inside_library(tmp_path):
    root = tmp_path / "p"
    library = root / "runtime/assets/library"
    library.mkdir(parents=True)
    (library / "a.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 20)
    db_path = root / "runtime/engine.db"
    conn = connect(db_path)
    try:
        _insert(conn, "asset-1", "runtime/assets/library/a.jpg")
        conn.commit()
    finally:
        conn.close()
    path, mime = _asset_file_info(root, db_path, "asset-1")
    assert path == (library / "a.jpg").resolve()
    assert mime == "image/jpeg"


def test_preview_rejects_unknown_missing_and_outside(tmp_path):
    root = tmp_path / "p"
    library = root / "runtime/assets/library"
    library.mkdir(parents=True)
    (root / "outside.jpg").write_bytes(b"nope")
    db_path = root / "runtime/engine.db"
    conn = connect(db_path)
    try:
        _insert(conn, "asset-out", "runtime/../outside.jpg")
        _insert(conn, "asset-gone", "runtime/assets/library/gone.jpg")
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(ValueError):
        _asset_file_info(root, db_path, "asset-missing")
    with pytest.raises(ValueError):
        _asset_file_info(root, db_path, "asset-out")
    with pytest.raises(ValueError):
        _asset_file_info(root, db_path, "asset-gone")
    with pytest.raises(ValueError):
        _asset_file_info(root, db_path, "  ")


def test_preview_falls_back_to_suffix_mime(tmp_path):
    root = tmp_path / "p"
    library = root / "runtime/assets/library"
    library.mkdir(parents=True)
    (library / "clip.mp4").write_bytes(b"\x00" * 16)
    db_path = root / "runtime/engine.db"
    conn = connect(db_path)
    try:
        _insert(conn, "asset-v", "runtime/assets/library/clip.mp4", mime="")
        conn.commit()
    finally:
        conn.close()
    _, mime = _asset_file_info(root, db_path, "asset-v")
    assert mime == "video/mp4"
