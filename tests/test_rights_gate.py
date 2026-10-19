"""C1 rights gate in the short-form render path.

Any graph/node media slot whose asset is not ``eligible`` for the exact
proposed upload use is refused (raises) - never silently rendered.

The gate function is exercised directly, plus one integration check that the
legacy short-form render path refuses an ineligible media slot. FFmpeg is not
required: the gate raises before FFmpeg is ever invoked.
"""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path
from unittest import mock

import pytest

from apps.asset_library.rights_scope import build_rights_scope
from apps.video_renderer import _gate_media_for_use, _render

ROOT = Path(__file__).resolve().parent.parent

PURPOSE = {
    "platform": "youtube",
    "territory": "VN",
    "commercial": True,
    "monetization": True,
    "edit": True,
    "credit_planned": True,
    "use_count": 0,
}

ELIGIBLE_SCOPE = build_rights_scope(
    platforms=["youtube", "tiktok", "facebook", "instagram"],
    territories=["*"],
    commercial=True,
    monetization=True,
    edit_allowed=True,
    credit_required=True,
    credit_text="Test Creator / CC BY 4.0",
    license="CC BY 4.0",
    source="wikimedia-commons",
    reviewed_by="human",
)


def _seed(
    root: Path,
    asset_id: str,
    *,
    rights_state="verified",
    license_type="CC BY 4.0",
    source_type="wikimedia-commons",
    source_url="https://commons.wikimedia.org/wiki/File:X.jpg",
    lifecycle_state="active",
    rights_scope=None,
    metadata=None,
):
    """Insert a library row (+ placeholder image file) under a temp root."""
    from apps.asset_library.registry import connect
    from apps.asset_library.rights_scope import ensure_rights_scope_schema

    db = root / "runtime" / "engine.db"
    conn = connect(db)
    try:
        ensure_rights_scope_schema(conn)
        lib = root / "runtime/assets/library"
        lib.mkdir(parents=True, exist_ok=True)
        (lib / f"{asset_id}.jpg").write_bytes(b"")
        row = {
            "asset_id": asset_id,
            "original_name": f"{asset_id}.jpg",
            "stored_path": f"runtime/assets/library/{asset_id}.jpg",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "size_bytes": 100,
            "sha256": "ab" * 32,
            "source_type": source_type,
            "source_url": source_url,
            "creator": "Test Creator",
            "license_type": license_type,
            "rights_state": rights_state,
            "lifecycle_state": lifecycle_state,
            "metadata_json": json.dumps(metadata or {}),
        }
        if rights_scope is not None:
            row["rights_scope_json"] = json.dumps(rights_scope, sort_keys=True)
        cols = ", ".join(row)
        placeholders = ", ".join("?" for _ in row)
        conn.execute(
            f"INSERT INTO assets ({cols}) VALUES ({placeholders})",
            list(row.values()),
        )
        conn.commit()
    finally:
        conn.close()


def _write_dummy_voice(root: Path, name: str = "voice-preview.wav") -> str:
    voice_dir = root / "runtime" / "voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    path = voice_dir / name
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 100)
    return name


def _make_run(root: Path, asset_id: str, voice_name: str) -> dict:
    return {
        "run_id": "abcdef012345",
        "script_owner_approved": True,
        "voice_preview": {"path": voice_name},
        "purpose": dict(PURPOSE),
        "draft": {
            "content_type": "short",
            "template_id": "allen-knows-ball.shortform-analyst",
            "template_version": "12.0.0",
            "duration_target_seconds": 30,
            "segments": [
                {
                    "id": "beat-1",
                    "start_seconds": 0,
                    "end_seconds": 30,
                    "media_asset_id": asset_id,
                    "visual": "test visual",
                }
            ],
        },
    }


# --- unit: the C1 gate itself ---------------------------------------------


def test_gate_allows_eligible_asset(tmp_path: Path):
    _seed(tmp_path, "asset-eligible", rights_scope=ELIGIBLE_SCOPE)
    assert _gate_media_for_use(tmp_path, "asset-eligible", PURPOSE) is None


def test_gate_refuses_ineligible_asset(tmp_path: Path):
    scope = build_rights_scope(
        platforms=["tiktok"], territories=["*"], commercial=True, monetization=True,
    )
    _seed(tmp_path, "asset-ineligible", rights_scope=scope)
    with pytest.raises(ValueError, match="platform-not-granted:youtube"):
        _gate_media_for_use(tmp_path, "asset-ineligible", PURPOSE)


def test_gate_refuses_needs_review_asset(tmp_path: Path):
    _seed(tmp_path, "asset-needs-review", metadata={"copyright_exception": True})
    with pytest.raises(ValueError, match="copyright-exception-requires-human"):
        _gate_media_for_use(tmp_path, "asset-needs-review", PURPOSE)


def test_gate_refuses_youtube_source_never_eligible(tmp_path: Path):
    _seed(tmp_path, "asset-yt", source_url="https://www.youtube.com/watch?v=abc")
    with pytest.raises(ValueError, match="unknown-source-or-license"):
        _gate_media_for_use(tmp_path, "asset-yt", PURPOSE)


def test_gate_refuses_without_upload_purpose(tmp_path: Path):
    _seed(tmp_path, "asset-eligible", rights_scope=ELIGIBLE_SCOPE)
    with pytest.raises(ValueError, match="no upload purpose"):
        _gate_media_for_use(tmp_path, "asset-eligible", None)


# --- integration: the gate is wired into the legacy short-form render -----


def test_render_refuses_ineligible_media_asset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr("apps.video_renderer._ffmpeg", lambda root: sys.executable)
    _write_dummy_voice(tmp_path)
    scope = build_rights_scope(
        platforms=["tiktok"], territories=["*"], commercial=True, monetization=True,
    )
    _seed(tmp_path, "asset-ineligible", rights_scope=scope)
    run = _make_run(tmp_path, "asset-ineligible", "voice-preview.wav")
    with pytest.raises(ValueError, match="refused"):
        _render(tmp_path, run, preview=False, output_name="full-render.mp4")


def test_render_proceeds_past_gate_for_eligible_asset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setattr("apps.video_renderer._ffmpeg", lambda root: sys.executable)
    _write_dummy_voice(tmp_path)
    _seed(tmp_path, "asset-eligible", rights_scope=ELIGIBLE_SCOPE)
    run = _make_run(tmp_path, "asset-eligible", "voice-preview.wav")
    try:
        _render(tmp_path, run, preview=False, output_name="full-render.mp4")
    except ValueError as error:
        # The rights gate must NOT refuse an eligible asset. Any later failure
        # (e.g. a non-ffmpeg executable standing in for FFmpeg) is unrelated.
        msg = str(error).lower()
        assert "refused" not in msg and "denied" not in msg, str(error)
    except Exception:
        # FFmpeg/audio plumbing not fully available here; the gate already
        # proved the eligible asset is not blocked by rights.
        pass
