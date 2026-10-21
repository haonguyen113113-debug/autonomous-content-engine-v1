"""Owner review records: scoped, versioned, provenance-carrying review data.

Review records live under ``docs/coordinator/review_records/`` as JSON files.
Each record scopes a single owner decision to exactly one
``(card_id, mode, template_version)`` plus a ``review_type`` and ``result``.

Planner/QA consult a record **only when card, mode AND pack version all
match**. A record never approves claims, source/date, asset rights, motion,
other cards/modes, other pack versions, or production readiness by itself.
The temporary preview artifact referenced by a record may no longer exist on
disk; the record itself is the owner decision and is consumed regardless.

No network, no clock, no randomness. Read-only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REVIEW_DIR = Path(__file__).resolve().parents[2] / "docs" / "coordinator" / "review_records"

SCHEMA_VERSION = "ace-review-record/1.0"


def load_review_records(records_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load every review record JSON under the review records directory.

    Unreadable/invalid files are skipped so a single bad record never breaks
    planning or QA.
    """
    directory = records_dir or REVIEW_DIR
    records: list[dict[str, Any]] = []
    if not directory.is_dir():
        return records
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            records.append(data)
    return records


def find_review_record(
    card_id: str,
    mode: str,
    template_version: str,
    *,
    review_type: str = "visual_static_png",
    records_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Return the review record that exactly scopes (card, mode, version).

    Match requires card_id, mode, template_version and review_type to all be
    equal. No wildcard matching: a record for one pack version never approves
    another, and a missing record means "not reviewed".
    """
    for record in load_review_records(records_dir):
        if (
            str(record.get("card_id")) == card_id
            and str(record.get("mode")) == mode
            and str(record.get("template_version")) == template_version
            and str(record.get("review_type")) == review_type
        ):
            return record
    return None


def source_card_visual_approved(
    card_id: str,
    mode: str,
    template_version: str,
    *,
    records_dir: Path | None = None,
) -> bool:
    """True only when an owner-approved static visual review exactly scopes
    this card/mode/pack version."""
    record = find_review_record(
        card_id, mode, template_version, records_dir=records_dir
    )
    if record is None:
        return False
    return str(record.get("result")) == "approved"


def review_readiness_fields(
    card_id: str,
    mode: str,
    template_version: str,
    *,
    records_dir: Path | None = None,
) -> dict[str, Any]:
    """Return the rendered_inspection / owner_approved fields QA/planner report.

    Shaped like the legacy global status so callers can drop it in, but the
    values come from the scoped review record. Approved only when the record
    exactly matches card, mode and pack version.
    """
    approved = source_card_visual_approved(
        card_id, mode, template_version, records_dir=records_dir
    )
    return {
        "rendered_inspection": "approved" if approved else "pending",
        "owner_approved": bool(approved),
    }
