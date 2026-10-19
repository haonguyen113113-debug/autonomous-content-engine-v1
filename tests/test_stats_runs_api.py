import json
from pathlib import Path

from apps.asset_library.registry import connect
from apps.web_ui.server import _list_runs, _stats


COLUMNS = (
    "(asset_id, original_name, stored_path, asset_type, mime_type, size_bytes,"
    " sha256, source_type, source_url, creator, license_type, rights_state,"
    " lifecycle_state, market_code, category_code, subject_type, subject_id,"
    " competition_code, purpose_code, metadata_json, source_id,"
    " source_revision_id, created_at)"
)


def _insert(conn, asset_id, *, created, license="CC BY 4.0",
            rights="verified", lifecycle="active"):
    conn.execute(
        f"INSERT INTO assets {COLUMNS} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            asset_id, f"{asset_id}.png",
            f"runtime/assets/library/{asset_id}.png", "image", "image/png",
            10, f"sha-{asset_id}", "openverse", "https://example.invalid/x",
            "Creator", license, rights, lifecycle, "vn", "soccer", None, None,
            None, None, "{}", None, None, created,
        ),
    )


def _write_run(root: Path, run_id, *, created, status="WAITING_FOR_OWNER_REVIEW",
               segments=None, extra=None):
    run = {
        "run_id": run_id,
        "created_at": created,
        "status": status,
        "draft": {
            "topic": f"Topic {run_id}",
            "content_type": "long",
            "generation_mode": "outline_fallback",
            "segments": segments if segments is not None else [],
        },
    }
    if extra:
        run.update(extra)
    (root / "runtime/runs" / f"{run_id}.json").write_text(
        json.dumps(run), encoding="utf-8"
    )


def _make_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "runtime/runs").mkdir(parents=True)
    (root / "runtime/assets/library").mkdir(parents=True)
    return root


def test_list_runs_summarizes_sorts_and_skips_bad_files(tmp_path):
    root = _make_root(tmp_path)
    _write_run(root, "aaaaaaaaaaaa", created="2026-10-01T10:00:00+00:00")
    _write_run(
        root, "bbbbbbbbbbbb", created="2026-10-03T10:00:00+00:00",
        status="SCRIPT_APPROVED",
        segments=[{"id": "beat-1", "media_asset_id": "img_1"},
                  {"id": "beat-2"}],
        extra={"script_owner_approved": True, "voice_preview": {"path": "x.wav"}},
    )
    _write_run(root, "cccccccccccc", created="2026-10-02T10:00:00+00:00",
               status="WAITING_FOR_RENDER_AUDIT")
    render_dir = root / "runtime/renders/bbbbbbbbbbbb"
    render_dir.mkdir(parents=True)
    (render_dir / "template-preview.mp4").write_bytes(b"fake")
    (render_dir / "render-report.json").write_text("{}", encoding="utf-8")
    (root / "runtime/runs" / "not-a-run.json").write_text("{}", encoding="utf-8")
    (root / "runtime/runs" / "dddddddddddd.json").write_text("not json", encoding="utf-8")

    runs = _list_runs(root)
    assert [r["run_id"] for r in runs] == ["bbbbbbbbbbbb", "cccccccccccc", "aaaaaaaaaaaa"]

    approved = runs[0]
    assert approved["status"] == "SCRIPT_APPROVED"
    assert approved["segment_count"] == 2
    assert approved["media_count"] == 1
    assert approved["script_owner_approved"] is True
    assert approved["voice_preview"] is True
    assert approved["voice_preview_audited"] is False
    assert approved["videos"] == {
        "template-preview.mp4": "/api/render/bbbbbbbbbbbb/template-preview.mp4"
    }
    assert approved["has_report"] is True
    assert runs[2]["videos"] == {}
    assert runs[2]["has_report"] is False


def test_stats_buckets_assets_and_runs(tmp_path):
    root = _make_root(tmp_path)
    db_path = root / "runtime/engine.db"
    conn = connect(db_path)
    try:
        _insert(conn, "img_1", created="2026-10-01 10:00:00", license="CC BY 4.0")
        _insert(conn, "img_2", created="2026-10-01 11:00:00", license="CC BY 4.0",
                rights="unverified", lifecycle="inactive")
        _insert(conn, "img_3", created="2026-10-02 10:00:00", license=None)
        _insert(conn, "img_4", created="2026-10-02 11:00:00", license="")
        conn.commit()
    finally:
        conn.close()
    _write_run(root, "aaaaaaaaaaaa", created="2026-10-01T10:00:00+00:00")
    _write_run(root, "bbbbbbbbbbbb", created="2026-10-02T10:00:00+00:00",
               status="SCRIPT_APPROVED")

    stats = _stats(root, db_path)
    assert stats["asset_count"] == 4
    assert stats["verified_rights_count"] == 3
    assert stats["active_count"] == 3
    assert stats["run_count"] == 2
    assert stats["assets_by_day"] == [
        {"day": "2026-10-01", "count": 2},
        {"day": "2026-10-02", "count": 2},
    ]
    assert stats["verified_by_day"] == [
        {"day": "2026-10-01", "count": 1},
        {"day": "2026-10-02", "count": 2},
    ]
    assert stats["active_by_day"] == [
        {"day": "2026-10-01", "count": 1},
        {"day": "2026-10-02", "count": 2},
    ]
    assert sorted(stats["assets_by_license"], key=lambda d: d["license"]) == [
        {"license": "CC BY 4.0", "count": 2},
        {"license": "Unknown", "count": 2},
    ]
    assert stats["runs_by_status"] == {
        "WAITING_FOR_OWNER_REVIEW": 1,
        "SCRIPT_APPROVED": 1,
    }


def test_empty_workspace_returns_empty_stats(tmp_path):
    root = tmp_path / "empty"
    assert _list_runs(root) == []
    stats = _stats(root, root / "runtime/engine.db")
    assert stats["asset_count"] == 0
    assert stats["run_count"] == 0
    assert stats["assets_by_day"] == []
    assert stats["assets_by_license"] == []
    assert stats["runs_by_status"] == {}
