import json
from pathlib import Path

import pytest

from apps.asset_library.registry import connect
from apps.web_ui.server import _attach_segment_media
from apps.video_renderer import render_visual_only_run


RUN_ID = "abcdef123456"


def _make_root(tmp_path: Path, *, content_type="long"):
    root = tmp_path / "project"
    (root / "runtime/runs").mkdir(parents=True)
    (root / "runtime/assets/library").mkdir(parents=True)
    run = {
        "run_id": RUN_ID,
        "status": "WAITING_FOR_OWNER_REVIEW",
        "draft": {
            "content_type": content_type,
            "duration_target_seconds": 600 if content_type == "long" else 45,
            "segments": [
                {"id": "beat-1", "narration": "Mo dau", "visual": "Host analysis"},
                {"id": "beat-2", "narration": "Phan tich", "visual": "Tactical board"},
            ],
        },
    }
    (root / "runtime/runs" / f"{RUN_ID}.json").write_text(
        json.dumps(run, ensure_ascii=False), encoding="utf-8"
    )
    return root


def _insert_image(root: Path, db_path: Path, *, asset_id="img_test_1", rights="verified", lifecycle="active"):
    image_path = root / "runtime/assets/library" / f"{asset_id}.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake-bytes")
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO assets (
                asset_id, original_name, stored_path, asset_type, mime_type,
                size_bytes, sha256, source_type, source_url, creator, license_type,
                rights_state, lifecycle_state, market_code, category_code,
                subject_type, subject_id, competition_code, purpose_code,
                metadata_json, source_id, source_revision_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                asset_id, f"{asset_id}.png", f"runtime/assets/library/{asset_id}.png",
                "image", "image/png", 12, f"sha-{asset_id}", "openverse",
                "https://example.invalid/photo", "Test Creator", "CC BY 4.0",
                rights, lifecycle, "vn", "soccer", None, None, None, None,
                json.dumps({"visual_context_note": "contextual photo"}), None, None,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return asset_id


def test_attach_media_success_and_detach(tmp_path):
    root = _make_root(tmp_path)
    db_path = root / "runtime/engine.db"
    asset_id = _insert_image(root, db_path)

    result = _attach_segment_media(root, db_path, {
        "run_id": RUN_ID, "segment_id": "beat-1",
        "asset_id": asset_id, "media_caption": "Boi canh san dau",
    })
    assert result["status"] == "MEDIA_ATTACHED"
    run = json.loads((root / "runtime/runs" / f"{RUN_ID}.json").read_text(encoding="utf-8"))
    beat = next(item for item in run["draft"]["segments"] if item["id"] == "beat-1")
    assert beat["media_asset_id"] == asset_id
    assert beat["media_caption"] == "Boi canh san dau"

    detached = _attach_segment_media(root, db_path, {
        "run_id": RUN_ID, "segment_id": "beat-1", "asset_id": "",
    })
    assert detached["status"] == "MEDIA_DETACHED"
    run = json.loads((root / "runtime/runs" / f"{RUN_ID}.json").read_text(encoding="utf-8"))
    beat = next(item for item in run["draft"]["segments"] if item["id"] == "beat-1")
    assert "media_asset_id" not in beat


def test_attach_media_rejects_unverified_rights(tmp_path):
    root = _make_root(tmp_path)
    db_path = root / "runtime/engine.db"
    asset_id = _insert_image(root, db_path, asset_id="img_unverified", rights="unverified")
    with pytest.raises(ValueError, match="rights must be verified"):
        _attach_segment_media(root, db_path, {
            "run_id": RUN_ID, "segment_id": "beat-1", "asset_id": asset_id,
        })


def test_attach_media_rejects_unknown_asset_and_segment(tmp_path):
    root = _make_root(tmp_path)
    db_path = root / "runtime/engine.db"
    _insert_image(root, db_path)
    with pytest.raises(ValueError, match="not found in the library"):
        _attach_segment_media(root, db_path, {
            "run_id": RUN_ID, "segment_id": "beat-1", "asset_id": "img_missing",
        })
    with pytest.raises(ValueError, match="not found in this run"):
        _attach_segment_media(root, db_path, {
            "run_id": RUN_ID, "segment_id": "beat-99", "asset_id": "img_test_1",
        })
    with pytest.raises(ValueError, match="run ID is invalid"):
        _attach_segment_media(root, db_path, {
            "run_id": "bad-id", "segment_id": "beat-1", "asset_id": "img_test_1",
        })


def test_visual_benchmark_requires_longform_with_media(tmp_path):
    short_root = _make_root(tmp_path / "short", content_type="short")
    with pytest.raises(ValueError, match="long-form"):
        render_visual_only_run(short_root, RUN_ID)

    long_root = _make_root(tmp_path / "long", content_type="long")
    with pytest.raises(ValueError, match="Attach at least one"):
        render_visual_only_run(long_root, RUN_ID)


def test_server_serves_visual_benchmark_video_filename():
    server_source = (Path(__file__).resolve().parent.parent / "apps/web_ui/server.py").read_text(encoding="utf-8")
    assert "visual-benchmark-silent\\.mp4" in server_source
    assert "render_visual_only_run" in server_source
    assert "/api/content/attach-media" in server_source
    assert "/api/content/render-visual-benchmark" in server_source
