"""Tests for the shared content-review contract (ace-content-review/1.0).

Content review is claim-scoped, not card-scoped: a record approves the
factual claim with its evidence, independently of which card/visual grammar
displays it. These tests use a temporary records directory so the real
``docs/coordinator/content_reviews/`` is never touched.

Trust boundary: the repo currently wires NO trusted human-approval mechanism
(``TRUSTED_REVIEW_MECHANISMS`` is empty). A record that merely says
reviewer="owner" and review_status="approved" is a self-assertion and is NOT
trusted as approved; it stays at needs_review until a real human-approval
path is plugged in.
"""

from __future__ import annotations

import json
from pathlib import Path

from apps.measurement.content_review import (
    SEMANTICS_ATTRIBUTION,
    SEMANTICS_CLAIM,
    SEMANTICS_CORRECTION,
    SEMANTICS_FACT_CHECK,
    SEMANTICS_MATCH_SOURCE,
    SOURCE_ROLE_CORRECTED,
    SOURCE_ROLE_ORIGINAL,
    SOURCE_ROLE_SUPPORTING,
    TRUSTED_REVIEW_MECHANISMS,
    content_review_readiness_fields,
    content_review_status,
    find_content_review,
    load_content_reviews,
)
from apps.card_selector import _extract_evidence_sources
from apps.content_workflow import _clean_segment

CLAIM = "Hà Nội thắng 2-0 trước TP.HCM."
BEAT_ID = "beat-source-1"


def _write_records(tmp_path: Path, records: list[dict]) -> Path:
    directory = Path(tmp_path) / "content_reviews"
    directory.mkdir(parents=True, exist_ok=True)
    for index, record in enumerate(records):
        path = directory / f"record-{index}.json"
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return directory


def _source(
    url: str,
    document_id: str,
    publisher: str,
    quote: str,
    supports_claim: bool = True,
    role: str = SOURCE_ROLE_SUPPORTING,
) -> dict:
    return {
        "url": url,
        "document_id": document_id,
        "publisher": publisher,
        "published_at": "2026-10-20T20:00:00+07:00",
        "accessed_at": "2026-10-21T08:00:00+07:00",
        "quote_or_location": quote,
        "supports_claim": supports_claim,
        "role": role,
        "notes": "Example source note.",
    }


def _valid_record(
    claim: str = CLAIM,
    beat_id: str = BEAT_ID,
    semantics: str = SEMANTICS_CLAIM,
    review_status: str = "approved",
    review_mechanism: str = "agent_auto",
    supports_claim: bool = True,
    sources: list[dict] | None = None,
) -> dict:
    """Build a record. Defaults to agent_auto (self-asserted, NOT trusted)."""
    if sources is None:
        sources = [
            _source(
                "https://example.com/match-report",
                "doc-1",
                "Example Sports",
                "Hà Nội 2 - 0 TP.HCM",
                supports_claim=supports_claim,
                role=SOURCE_ROLE_SUPPORTING,
            )
        ]
    return {
        "schema_version": "ace-content-review/1.0",
        "record_id": "review-claim-001",
        "beat_id": beat_id,
        "claim": claim,
        "semantics": semantics,
        "sources": sources,
        "evidence_link": "source doc-1 quote matches claim",
        "review_status": review_status,
        "review_mechanism": review_mechanism,
        "reviewer": "owner",
        "reviewed_at": "2026-10-21",
        "reason": "Claim verified against cited source.",
        "scope": {
            "covers": ["claim verification"],
            "does_not_cover": ["rights", "visual"],
        },
    }


def test_trusted_mechanisms_is_empty_by_default() -> None:
    """No human-approval mechanism is wired yet; nothing is trusted by default."""
    assert TRUSTED_REVIEW_MECHANISMS == frozenset()


def test_self_asserted_owner_approval_is_not_trusted() -> None:
    """reviewer="owner" + review_status="approved" is NOT trusted without a
    trusted human-approval mechanism. Stays needs_review."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [_valid_record()])
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=[_source("https://example.com/match-report", "doc-1", "Example Sports", "Hà Nội 2 - 0 TP.HCM")],
            records_dir=records_dir,
        )
        assert status["status"] == "needs_review"
        assert status["record"] is not None
        assert "not a trusted human-approval path" in status["detail"]
        assert not status["invalidated"]

        fields = content_review_readiness_fields(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=[_source("https://example.com/match-report", "doc-1", "Example Sports", "Hà Nội 2 - 0 TP.HCM")],
            records_dir=records_dir,
        )
        assert fields["content_review"] == "needs_review"


def test_missing_record_is_missing() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [])
        status = content_review_status(
            CLAIM, BEAT_ID, SEMANTICS_CLAIM, records_dir=records_dir
        )
        assert status["status"] == "missing"
        assert status["record"] is None
        assert not status["invalidated"]

        fields = content_review_readiness_fields(
            CLAIM, BEAT_ID, SEMANTICS_CLAIM, records_dir=records_dir
        )
        assert fields["content_review"] == "missing"


def test_record_does_not_leak_to_other_claim() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [_valid_record()])
        assert (
            content_review_status(
                "A completely different claim.",
                BEAT_ID,
                SEMANTICS_CLAIM,
                records_dir=records_dir,
            )["status"]
            == "missing"
        )
        assert (
            content_review_status(
                CLAIM, "other-beat", SEMANTICS_CLAIM, records_dir=records_dir
            )["status"]
            == "missing"
        )
        assert (
            content_review_status(
                CLAIM, BEAT_ID, SEMANTICS_FACT_CHECK, records_dir=records_dir
            )["status"]
            == "missing"
        )


def test_malformed_record_is_needs_review() -> None:
    import tempfile

    bad = _valid_record()
    del bad["review_status"]  # malformed: missing review status
    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [bad])
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=[_source("https://example.com/match-report", "doc-1", "Example Sports", "Hà Nội 2 - 0 TP.HCM")],
            records_dir=records_dir,
        )
        assert status["status"] == "needs_review"
        assert status["record"] is not None


def test_evidence_does_not_support_claim_is_needs_review() -> None:
    import tempfile

    record = _valid_record(supports_claim=False)
    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [record])
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=[_source("https://example.com/match-report", "doc-1", "Example Sports", "Hà Nội 2 - 0 TP.HCM", supports_claim=False)],
            records_dir=records_dir,
        )
        assert status["status"] == "needs_review"
        assert "supports" in status["detail"].lower()


def test_sources_changed_after_review_is_invalidated() -> None:
    import tempfile

    record = _valid_record()
    current_sources = [
        _source(
            "https://different.example.com/other",
            "doc-2",
            "Different Sports",
            "Different quote.",
            supports_claim=True,
        )
    ]
    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [record])
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=current_sources,
            records_dir=records_dir,
        )
        assert status["status"] == "needs_review"
        assert status["invalidated"] is True


def test_rejected_record_is_rejected() -> None:
    import tempfile

    record = _valid_record(review_status="rejected")
    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [record])
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=[_source("https://example.com/match-report", "doc-1", "Example Sports", "Hà Nội 2 - 0 TP.HCM")],
            records_dir=records_dir,
        )
        assert status["status"] == "rejected"


def test_correction_with_only_one_side_is_not_approved() -> None:
    import tempfile

    # Correction with only the original side: well-formed but the corrected
    # side has no evidence, so it cannot be approved.
    record = _valid_record(
        semantics=SEMANTICS_CORRECTION,
        claim="Corrected score.",
        sources=[
            _source(
                "https://example.com/old",
                "doc-old",
                "Example Sports",
                "Old score was 1-0.",
                supports_claim=True,
                role=SOURCE_ROLE_ORIGINAL,
            )
            # Missing the corrected/new source.
        ],
    )
    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [record])
        status = content_review_status(
            "Corrected score.", BEAT_ID, SEMANTICS_CORRECTION, records_dir=records_dir
        )
        assert status["status"] in ("needs_review", "missing")
        assert status["status"] != "approved"


def test_correction_with_both_sides_can_be_approved_if_trusted() -> None:
    import tempfile

    # Correction with both sides evidenced. Still not approved because no
    # trusted mechanism is wired; this test documents the evidence shape.
    record = _valid_record(
        semantics=SEMANTICS_CORRECTION,
        claim="Corrected score.",
        sources=[
            _source(
                "https://example.com/old",
                "doc-old",
                "Example Sports",
                "Old score was 1-0.",
                supports_claim=True,
                role=SOURCE_ROLE_ORIGINAL,
            ),
            _source(
                "https://example.com/new",
                "doc-new",
                "Example Sports",
                "Corrected score is 2-0.",
                supports_claim=True,
                role=SOURCE_ROLE_CORRECTED,
            ),
        ],
    )
    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [record])
        status = content_review_status(
            "Corrected score.",
            BEAT_ID,
            SEMANTICS_CORRECTION,
            sources=[
                _source("https://example.com/old", "doc-old", "Example Sports", "Old score was 1-0.", supports_claim=True, role=SOURCE_ROLE_ORIGINAL),
                _source("https://example.com/new", "doc-new", "Example Sports", "Corrected score is 2-0.", supports_claim=True, role=SOURCE_ROLE_CORRECTED),
            ],
            records_dir=records_dir,
        )
        # Evidence is complete but no trusted mechanism -> needs_review.
        assert status["status"] == "needs_review"
        assert "not a trusted human-approval path" in status["detail"]


def test_match_source_semantics_is_distinct() -> None:
    import tempfile

    record = _valid_record(
        semantics=SEMANTICS_MATCH_SOURCE,
        claim="Match data timestamp: 78th minute.",
    )
    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [record])
        status = content_review_status(
            "Match data timestamp: 78th minute.",
            BEAT_ID,
            SEMANTICS_MATCH_SOURCE,
            sources=[_source("https://example.com/match-data", "doc-1", "Example Sports", "78th minute.")],
            records_dir=records_dir,
        )
        # Not trusted (agent_auto mechanism) -> needs_review.
        assert status["status"] == "needs_review"

        # The same claim under attribution semantics does not match.
        assert (
            content_review_status(
                "Match data timestamp: 78th minute.",
                BEAT_ID,
                SEMANTICS_ATTRIBUTION,
                records_dir=records_dir,
            )["status"]
            == "missing"
        )


def test_unknown_semantics_is_needs_review() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [])
        status = content_review_status(
            CLAIM, BEAT_ID, "unknown-semantics", records_dir=records_dir
        )
        assert status["status"] == "needs_review"


# ---------------------------------------------------------------------------
# Credit attribution verification tests
# ---------------------------------------------------------------------------


def test_credit_matches_reviewed_source() -> None:
    """Card credit text that maps to a reviewed source's publisher/date is
    considered matching (credit mapping confirmed)."""
    from apps.measurement.content_review import _credit_matches_reviewed_source

    credit = {"source": "Example Sports", "date": "2026-10-20"}
    sources = [
        {
            "url": "https://example.com/match-report",
            "document_id": "doc-1",
            "publisher": "Example Sports",
            "published_at": "2026-10-20T20:00:00+07:00",
        }
    ]
    assert _credit_matches_reviewed_source(credit, sources) is True


def test_credit_source_mismatch_invalidates() -> None:
    """Card credit source name that does not match any reviewed publisher
    invalidates the review."""
    import tempfile

    record = _valid_record()
    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [record])
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=[
                _source(
                    "https://example.com/match-report",
                    "doc-1",
                    "Example Sports",
                    "Hà Nội 2 - 0 TP.HCM",
                    supports_claim=True,
                )
            ],
            credit={"source": "Different Publisher", "date": "2026-10-20"},
            records_dir=records_dir,
        )
        assert status["status"] == "needs_review"
        assert status["invalidated"] is True


def test_credit_date_mismatch_invalidates() -> None:
    """Card credit date that does not match any reviewed publication date
    invalidates the review."""
    import tempfile

    record = _valid_record()
    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [record])
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=[
                _source(
                    "https://example.com/match-report",
                    "doc-1",
                    "Example Sports",
                    "Hà Nội 2 - 0 TP.HCM",
                    supports_claim=True,
                )
            ],
            credit={"source": "Example Sports", "date": "2026-10-21"},
            records_dir=records_dir,
        )
        assert status["status"] == "needs_review"
        assert status["invalidated"] is True


def test_credit_without_source_identity_is_missing() -> None:
    """Credit text alone (no source identity) cannot satisfy content review."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [_valid_record()])
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=None,
            credit={"source": "Example Sports", "date": "2026-10-20"},
            records_dir=records_dir,
        )
        assert status["status"] == "missing"
        assert status["record"] is not None


def test_credit_source_name_exact_match_only() -> None:
    """Credit source name matches publisher only after exact normalization;
    substring (either way) does not match."""
    from apps.measurement.content_review import _credit_matches_reviewed_source

    base = {
        "publisher": "Example Sports Media Group",
        "published_at": "2026-10-20T20:00:00+07:00",
    }

    # Exact match after normalization.
    assert _credit_matches_reviewed_source(
        {"source": "Example Sports Media Group", "date": "2026-10-20"}, [base]
    ) is True

    # Credit source is a substring of publisher -> NO match.
    assert _credit_matches_reviewed_source(
        {"source": "Example Sports", "date": "2026-10-20"}, [base]
    ) is False

    # Publisher is a substring of credit source -> NO match.
    assert _credit_matches_reviewed_source(
        {"source": "Example Sports Media Group Co Ltd", "date": "2026-10-20"},
        [base],
    ) is False

    # Short generic credit does not match.
    assert _credit_matches_reviewed_source(
        {"source": "Báo", "date": "2026-10-20"}, [base]
    ) is False

    # Diacritics-insensitive exact match still works.
    assert _credit_matches_reviewed_source(
        {"source": "Báo Mới", "date": "2026-10-20"},
        [{"publisher": "Bao Moi", "published_at": "2026-10-20T20:00:00+07:00"}],
    ) is True

    # Case-insensitive exact match.
    assert _credit_matches_reviewed_source(
        {"source": "EXAMPLE SPORTS MEDIA GROUP", "date": "2026-10-20"}, [base]
    ) is True


# ---------------------------------------------------------------------------
# evidence_identity preservation tests (script normalization boundary)
# ---------------------------------------------------------------------------


def test_clean_segment_preserves_evidence_identity() -> None:
    """_clean_segment keeps the segment's evidence_identity field so the
    content-review gate can bind the claim to a specific source."""
    segment = {
        "id": "beat-1",
        "narration": "Test narration",
        "visual": "Test visual",
        "graphic_data": {"source": "Synthetic Sports Desk", "date": "20/10/2026"},
        "evidence_identity": {
            "sources": [
                {
                    "url": "https://example.com/match-report",
                    "document_id": "doc-1",
                    "publisher": "Example Sports",
                    "published_at": "2026-10-20T20:00:00+07:00",
                    "quote_or_location": "Hà Nội 2 - 0 TP.HCM",
                    "supports_claim": True,
                }
            ]
        },
    }
    cleaned = _clean_segment(segment)
    assert cleaned is not None
    assert "evidence_identity" in cleaned
    assert cleaned["evidence_identity"]["sources"][0]["document_id"] == "doc-1"
    assert cleaned["evidence_identity"]["sources"][0]["publisher"] == "Example Sports"


def test_clean_segment_drops_evidence_identity_when_absent() -> None:
    """_clean_segment does not add evidence_identity when the input lacks it."""
    segment = {
        "id": "beat-1",
        "narration": "Test narration",
        "visual": "Test visual",
        "graphic_data": {"source": "Synthetic Sports Desk", "date": "20/10/2026"},
    }
    cleaned = _clean_segment(segment)
    assert cleaned is not None
    assert "evidence_identity" not in cleaned


def test_clean_segment_uses_graphic_data_not_as_source_identity() -> None:
    """graphic_data.source/date (credit text) is never treated as source
    identity by _clean_segment."""
    segment = {
        "id": "beat-1",
        "narration": "Test narration",
        "visual": "Test visual",
        "graphic_data": {
            "source": "https://example.com/fake-url",
            "date": "20/10/2026",
            "credit": "Nguồn: Synthetic Sports Desk • 20/10/2026 (synthetic)",
        },
    }
    cleaned = _clean_segment(segment)
    assert cleaned is not None
    assert "evidence_identity" not in cleaned
    # graphic_data is preserved as-is (credit text), but evidence_identity
    # is not derived from it.
    assert cleaned["graphic_data"]["source"] == "https://example.com/fake-url"


# ---------------------------------------------------------------------------
# Planner source ID tests
# ---------------------------------------------------------------------------


def test_planner_receives_source_ids_from_evidence_identity() -> None:
    """The planner extracts source IDs from segment.evidence_identity and
    passes them to the content-review gate (not from graphic_data credit)."""
    from apps.card_selector import select_cards

    # Beat 0 must be a hook; beat 1 is the source card.
    segments = [
        {
            "id": "beat-hook",
            "narration": "SYNTHETIC: Kết quả mới nhất",
            "visual": "Synthetic headline",
            "visual_mode": "hook_card",
            "graphic_data": {"hook_text": "SYNTHETIC: Kết quả mới nhất"},
        },
        {
            "id": "beat-source",
            "narration": "Nguồn: Example Sports, cập nhật 20/10/2026",
            "visual": "Synthetic attribution card",
            "visual_mode": "source_card",
            "graphic_data": {
                "source": "Example Sports",
                "date": "20/10/2026",
                "claim": "Hà Nội thắng 2-0 trước TP.HCM.",
                "credit": "Example Sports • 20/10/2026",
            },
            "evidence_identity": {
                "sources": [
                    {
                        "url": "https://example.com/match-report",
                        "document_id": "doc-1",
                        "publisher": "Example Sports",
                        "published_at": "2026-10-20T20:00:00+07:00",
                        "quote_or_location": "Hà Nội 2 - 0 TP.HCM",
                        "supports_claim": True,
                    }
                ]
            },
        },
    ]
    out = select_cards(segments, content_type="short")
    source_decision = next(d for d in out["decisions"] if d["segment_id"] == "beat-source")
    assert source_decision["visual_mode"] == "source_card"
    assert source_decision["starter_id"] == "C-09"
    # Content review is missing (no trusted mechanism), not approved.
    assert source_decision["readiness"]["content_review"] in ("missing", "needs_review")
    assert source_decision["readiness"]["production_ready"] is False


def test_extract_evidence_sources_none_when_absent() -> None:
    """_extract_evidence_sources returns None when segment has no
    evidence_identity (fail-closed: content review stays missing)."""
    segment = {"id": "beat-1", "graphic_data": {"source": "Synthetic Sports Desk", "date": "20/10/2026"}}
    assert _extract_evidence_sources(segment) is None


def test_extract_evidence_sources_ignores_credit_text() -> None:
    """graphic_data.source/date (credit text) is not extracted as source
    identity; only evidence_identity.sources is used."""
    segment = {
        "id": "beat-1",
        "graphic_data": {
            "source": "Synthetic Sports Desk (fixture)",
            "date": "20/10/2026 (synthetic)",
            "credit": "Nguồn: Synthetic Sports Desk • 20/10/2026 (synthetic)",
        },
        "evidence_identity": {
            "sources": [
                {
                    "url": "https://example.com/match-report",
                    "document_id": "doc-1",
                    "publisher": "Example Sports",
                    "published_at": "2026-10-20T20:00:00+07:00",
                    "accessed_at": "2026-10-21T08:00:00+07:00",
                    "quote_or_location": "Hà Nội 2 - 0 TP.HCM",
                    "supports_claim": True,
                    "role": "supporting",
                }
            ]
        },
    }
    sources = _extract_evidence_sources(segment)
    assert sources is not None
    assert len(sources) == 1
    assert sources[0]["url"] == "https://example.com/match-report"
    assert sources[0]["document_id"] == "doc-1"
    assert sources[0]["publisher"] == "Example Sports"
    # Credit text from graphic_data is NOT in the extracted sources
    assert "Synthetic Sports Desk" not in sources[0]["url"]
    assert "Synthetic Sports Desk" not in sources[0]["document_id"]


def test_extract_evidence_sources_returns_none_for_empty_sources() -> None:
    """evidence_identity with empty sources returns None."""
    segment = {"id": "beat-1", "evidence_identity": {"sources": []}}
    assert _extract_evidence_sources(segment) is None


def test_extract_evidence_sources_skips_invalid_items() -> None:
    """Items without url/document_id are skipped."""
    segment = {
        "id": "beat-1",
        "evidence_identity": {
            "sources": [
                {"publisher": "No ID"},  # invalid: no url/document_id
                {
                    "url": "https://example.com/match-report",
                    "document_id": "doc-1",
                    "publisher": "Example Sports",
                    "published_at": "2026-10-20T20:00:00+07:00",
                    "quote_or_location": "Hà Nội 2 - 0 TP.HCM",
                    "supports_claim": True,
                },
            ]
        },
    }
    sources = _extract_evidence_sources(segment)
    assert sources is not None
    assert len(sources) == 1
    assert sources[0]["document_id"] == "doc-1"


def test_record_matching_full_source_identity_still_needs_review() -> None:
    """A record matching claim/beat/semantics AND full source identity
    (URL, document_id, publisher, date, evidence) is found but NOT approved
    because no trusted human-approval mechanism is wired."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [_valid_record()])
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=[
                _source(
                    "https://example.com/match-report",
                    "doc-1",
                    "Example Sports",
                    "Hà Nội 2 - 0 TP.HCM",
                    supports_claim=True,
                )
            ],
            records_dir=records_dir,
        )
        # Record found (not missing) but not trusted -> needs_review.
        assert status["status"] == "needs_review"
        assert status["record"] is not None
        assert status["record"]["record_id"] == "review-claim-001"
        assert "not a trusted human-approval path" in status["detail"]
        assert not status["invalidated"]


def test_changing_url_invalidates_review() -> None:
    import tempfile

    record = _valid_record()
    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [record])
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=[
                _source(
                    "https://different.example.com/other",
                    "doc-1",
                    "Example Sports",
                    "Hà Nội 2 - 0 TP.HCM",
                    supports_claim=True,
                )
            ],
            records_dir=records_dir,
        )
        assert status["status"] == "needs_review"
        assert status["invalidated"] is True


def test_changing_document_id_invalidates_review() -> None:
    import tempfile

    record = _valid_record()
    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [record])
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=[
                _source(
                    "https://example.com/match-report",
                    "doc-999",
                    "Example Sports",
                    "Hà Nội 2 - 0 TP.HCM",
                    supports_claim=True,
                )
            ],
            records_dir=records_dir,
        )
        assert status["status"] == "needs_review"
        assert status["invalidated"] is True


def test_changing_publisher_invalidates_review() -> None:
    import tempfile

    record = _valid_record()
    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [record])
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=[
                _source(
                    "https://example.com/match-report",
                    "doc-1",
                    "Different Publisher",
                    "Hà Nội 2 - 0 TP.HCM",
                    supports_claim=True,
                )
            ],
            records_dir=records_dir,
        )
        assert status["status"] == "needs_review"
        assert status["invalidated"] is True


def test_changing_publication_date_invalidates_review() -> None:
    import tempfile

    record = _valid_record()
    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [record])
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=[
                _source(
                    "https://example.com/match-report",
                    "doc-1",
                    "Example Sports",
                    "Hà Nội 2 - 0 TP.HCM",
                    supports_claim=True,
                )
            ],
            records_dir=records_dir,
        )
        # Same sources except published_at differs — add a source with different date
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=[
                {
                    "url": "https://example.com/match-report",
                    "document_id": "doc-1",
                    "publisher": "Example Sports",
                    "published_at": "2026-10-21T20:00:00+07:00",
                    "accessed_at": "2026-10-22T08:00:00+07:00",
                    "quote_or_location": "Hà Nội 2 - 0 TP.HCM",
                    "supports_claim": True,
                    "role": SOURCE_ROLE_SUPPORTING,
                }
            ],
            records_dir=records_dir,
        )
        assert status["status"] == "needs_review"
        assert status["invalidated"] is True


def test_missing_source_identity_cannot_be_approved() -> None:
    """When the planner provides no source identity (sources=None), content
    review stays missing — never approved — even if a matching record exists."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [_valid_record()])
        status = content_review_status(
            CLAIM, BEAT_ID, SEMANTICS_CLAIM, sources=None, records_dir=records_dir
        )
        assert status["status"] == "missing"
        assert status["record"] is not None
        assert "no source identity provided" in status["detail"]

        fields = content_review_readiness_fields(
            CLAIM, BEAT_ID, SEMANTICS_CLAIM, sources=None, records_dir=records_dir
        )
        assert fields["content_review"] == "missing"
        assert fields["content_review_record_id"] == "review-claim-001"


def test_credit_display_text_not_used_as_source_url() -> None:
    """graphic_data.source (credit display text) must not be treated as a
    source URL. The planner extracts evidence_identity separately; credit text
    alone never satisfies source identity."""
    import tempfile

    # Simulate what would happen if credit text were wrongly passed as URL:
    # it should not match a real document_id/URL record.
    with tempfile.TemporaryDirectory() as tmp:
        records_dir = _write_records(tmp, [_valid_record()])
        # Credit display text as "url" should not match the reviewed doc-1
        status = content_review_status(
            CLAIM,
            BEAT_ID,
            SEMANTICS_CLAIM,
            sources=[
                {
                    "url": "Synthetic Sports Desk (fixture)",  # credit text, not a URL
                    "document_id": "",
                    "publisher": "",
                    "published_at": "",
                    "accessed_at": "",
                    "quote_or_location": "",
                    "supports_claim": False,
                    "role": SOURCE_ROLE_SUPPORTING,
                }
            ],
            records_dir=records_dir,
        )
        # No matching source identity → invalidated (different url/document_id)
        assert status["status"] == "needs_review"
        assert status["invalidated"] is True
