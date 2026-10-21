"""Tests for the scoped owner review record loader.

These tests exercise ``apps.measurement.review_records`` directly with
temporary record directories so the real review record under
``docs/coordinator/review_records/`` is never modified.
"""

from __future__ import annotations

import json
from pathlib import Path

from apps.measurement.review_records import (
    find_review_record,
    load_review_records,
    review_readiness_fields,
    source_card_visual_approved,
)

RECORD = {
    "schema_version": "ace-review-record/1.0",
    "record_id": "c09-source-card-12-1-0-2026-10-21",
    "card_id": "C-09",
    "mode": "source_card",
    "template_version": "12.1.0",
    "review_type": "visual_static_png",
    "reviewed_at": "2026-10-21",
    "reviewer": "owner",
    "result": "approved",
    "notes": "font đủng, bố cục hợp lý, không tràn chữ",
}


def _write_record(tmp_path: Path, record: dict) -> Path:
    directory = tmp_path / "review_records"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "c09-source-card-12-1-0-2026-10-21.json"
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return directory


def test_record_matching_scope_is_approved() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_record(Path(tmp), dict(RECORD))
        assert source_card_visual_approved(
            "C-09", "source_card", "12.1.0", records_dir=records_dir
        ) is True
        fields = review_readiness_fields(
            "C-09", "source_card", "12.1.0", records_dir=records_dir
        )
        assert fields == {
            "rendered_inspection": "approved",
            "owner_approved": True,
        }
        found = find_review_record(
            "C-09", "source_card", "12.1.0", records_dir=records_dir
        )
        assert found is not None
        assert found["result"] == "approved"


def test_wrong_card_is_not_approved() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_record(Path(tmp), dict(RECORD))
        assert source_card_visual_approved(
            "C-04", "source_card", "12.1.0", records_dir=records_dir
        ) is False
        assert source_card_visual_approved(
            "C-09", "player_card", "12.1.0", records_dir=records_dir
        ) is False
        fields = review_readiness_fields(
            "C-04", "source_card", "12.1.0", records_dir=records_dir
        )
        assert fields == {
            "rendered_inspection": "pending",
            "owner_approved": False,
        }


def test_wrong_pack_version_is_not_approved() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_record(Path(tmp), dict(RECORD))
        # C-09 source_card is contract-executable only in 12.1.0; the review
        # record must not extend to 12.0.0.
        assert source_card_visual_approved(
            "C-09", "source_card", "12.0.0", records_dir=records_dir
        ) is False
        assert find_review_record(
            "C-09", "source_card", "12.0.0", records_dir=records_dir
        ) is None


def test_missing_record_means_not_reviewed() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        records_dir = Path(tmp) / "review_records"
        records_dir.mkdir(parents=True, exist_ok=True)
        # No record file at all.
        assert source_card_visual_approved(
            "C-09", "source_card", "12.1.0", records_dir=records_dir
        ) is False
        assert find_review_record(
            "C-09", "source_card", "12.1.0", records_dir=records_dir
        ) is None
        assert load_review_records(records_dir) == []


def test_result_must_be_approved() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        not_approved = dict(RECORD)
        not_approved["result"] = "needs_review"
        records_dir = _write_record(Path(tmp), not_approved)
        assert source_card_visual_approved(
            "C-09", "source_card", "12.1.0", records_dir=records_dir
        ) is False
