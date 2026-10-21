"""Content review records: claim-scoped, versioned, provenance-carrying review data.

Content review is about the *factual claim* a beat makes, not the card that
displays it. A card only decides *how* to present content that has already been
reviewed; it never verifies the claim itself.

Review records live under ``docs/coordinator/content_reviews/`` as JSON files.
Each record scopes a review decision to exactly one claim (identified by
``beat_id`` plus claim text) plus a ``semantics`` class.

Planner/QA consult a record **only when the claim, beat id and semantics all
match**. A record never approves rights, visual layout, text fit, motion, other
claims, or production readiness by itself. It is one independent gate alongside
text-fit, rights eligibility, contract execution and visual approval.

No network, no clock, no randomness. Read-only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CONTENT_REVIEW_DIR = (
    Path(__file__).resolve().parents[2] / "docs" / "coordinator" / "content_reviews"
)

SCHEMA_VERSION = "ace-content-review/1.0"

# Semantics classes a factual claim can carry.
SEMANTICS_CLAIM = "claim"
SEMANTICS_ATTRIBUTION = "attribution"
SEMANTICS_CORRECTION = "correction"
SEMANTICS_FACT_CHECK = "fact_check"
SEMANTICS_MATCH_SOURCE = "match_source"
VALID_SEMANTICS = frozenset(
    {
        SEMANTICS_CLAIM,
        SEMANTICS_ATTRIBUTION,
        SEMANTICS_CORRECTION,
        SEMANTICS_FACT_CHECK,
        SEMANTICS_MATCH_SOURCE,
    }
)

# Review outcomes.
REVIEW_APPROVED = "approved"
REVIEW_NEEDS_REVIEW = "needs_review"
REVIEW_REJECTED = "rejected"
VALID_REVIEW_STATUSES = frozenset({REVIEW_APPROVED, REVIEW_NEEDS_REVIEW, REVIEW_REJECTED})

# Review mechanisms the engine can treat as trustworthy provenance. A JSON
# field that merely says reviewer="owner" is an agent/self-assertion and is
# NOT trusted by itself. Only a mechanism recorded through a trusted human
# approval path counts. The repo currently ships no wired human-approval
# artifact, so no mechanism is trusted by default; keep this empty until the
# owner plugs in a real human-approval record.
TRUSTED_REVIEW_MECHANISMS: frozenset[str] = frozenset()

# Source roles used in the evidence list.
SOURCE_ROLE_ORIGINAL = "original"
SOURCE_ROLE_CORRECTED = "corrected"
SOURCE_ROLE_SUPPORTING = "supporting"
VALID_SOURCE_ROLES = frozenset(
    {SOURCE_ROLE_ORIGINAL, SOURCE_ROLE_CORRECTED, SOURCE_ROLE_SUPPORTING}
)

# Content-review readiness status reported to planner/QA.
CONTENT_REVIEW_APPROVED = "approved"
CONTENT_REVIEW_MISSING = "missing"
CONTENT_REVIEW_NEEDS_REVIEW = "needs_review"
CONTENT_REVIEW_REJECTED = "rejected"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_claim(claim: str) -> str:
    """Return a claim-normalised form used for identity/hash.

    Whitespace is collapsed and the claim is stripped; case and punctuation are
    preserved so that paraphrases are treated as different claims.
    """
    return " ".join(str(claim).split()).strip()


def claim_hash(claim: str) -> str:
    return _sha256(canonical_claim(claim))


def _strip_accents(text: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFD", str(text).lower()).replace("đ", "d")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _credit_matches_reviewed_source(
    credit: dict[str, Any], sources: list[dict[str, Any]]
) -> bool:
    """Return True when card credit text verifiably maps to a reviewed source.

    ``credit`` is display text from ``graphic_data.source``/``graphic_data.date``.
    It is never used as source identity. Publisher matching is exact after
    Unicode/diacritics/case normalization; no substring or alias matching is
    performed (no alias contract is defined). Date matching compares the date
    portion against the reviewed source's ``published_at``. Both source and
    date must match when both are present on the credit. Credit text that is a
    substring of the publisher, or vice versa, does NOT match.
    """
    credit_source = str(credit.get("source", "")).strip()
    credit_date = str(credit.get("date", "")).strip()
    if not credit_source and not credit_date:
        return True  # No credit to verify.

    norm_credit_source = _strip_accents(credit_source)
    norm_credit_date = (
        credit_date.split("T")[0].split(" ")[0].strip() if credit_date else ""
    )

    for source in sources or []:
        if not isinstance(source, dict):
            continue
        publisher = str(source.get("publisher", "")).strip()
        published_at = str(source.get("published_at", "")).strip()

        source_ok = True
        if credit_source:
            norm_publisher = _strip_accents(publisher)
            source_ok = bool(
                norm_publisher and norm_credit_source == norm_publisher
            )

        date_ok = True
        if credit_date:
            norm_pub_date = published_at.split("T")[0].split(" ")[0].strip()
            date_ok = bool(norm_pub_date and norm_credit_date == norm_pub_date)

        if source_ok and date_ok:
            return True
    return False


def load_content_reviews(records_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load every content review record JSON under the content reviews directory.

    Unreadable/invalid files are skipped so a single bad record never breaks
    planning or QA.
    """
    directory = records_dir or CONTENT_REVIEW_DIR
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


def find_content_review(
    claim: str,
    beat_id: str,
    semantics: str,
    *,
    records_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Return the content review record that exactly scopes (claim, beat, semantics).

    Match requires claim text (canonicalised), beat_id and semantics to all be
    equal. No wildcard matching: a record for one claim never approves another,
    and a missing record means "not reviewed".
    """
    if semantics not in VALID_SEMANTICS:
        return None
    norm_claim = canonical_claim(claim)
    for record in load_content_reviews(records_dir):
        if (
            str(record.get("beat_id")) == beat_id
            and str(record.get("semantics")) == semantics
            and canonical_claim(str(record.get("claim", ""))) == norm_claim
        ):
            return record
    return None


def _record_is_well_formed(record: dict[str, Any]) -> bool:
    """Return True when the record carries the minimum review provenance.

    Well-formed does NOT mean trusted. A record with reviewer="owner" and
    review_status="approved" is still only a self-assertion unless its
    ``review_mechanism`` is in ``TRUSTED_REVIEW_MECHANISMS`` (currently empty
    until a real human-approval artifact is wired).
    """
    if not isinstance(record, dict):
        return False
    if str(record.get("schema_version")) != SCHEMA_VERSION:
        return False
    if not str(record.get("record_id", "")).strip():
        return False
    if str(record.get("review_status")) not in VALID_REVIEW_STATUSES:
        return False
    if not str(record.get("reviewed_at", "")).strip():
        return False
    # reviewer is documented for traceability but is not, by itself, trust
    # evidence. A self-asserted reviewer name does not make approval trusted.
    sources = record.get("sources")
    if not isinstance(sources, list) or len(sources) == 0:
        return False
    for source in sources:
        if not isinstance(source, dict):
            return False
        role = str(source.get("role", "") or SOURCE_ROLE_SUPPORTING).strip()
        if role not in VALID_SOURCE_ROLES:
            return False
        if not str(source.get("url", "") or source.get("document_id", "")).strip():
            return False
    return True


def _is_trusted_approval(record: dict[str, Any]) -> bool:
    """Return True only when the record's approval comes from a trusted
    human-approval mechanism, not a self-asserted JSON field.

    Because ``TRUSTED_REVIEW_MECHANISMS`` is empty until a real human-approval
    path is wired, no record is currently trusted as approved.
    """
    mechanism = str(record.get("review_mechanism", "")).strip()
    if mechanism not in TRUSTED_REVIEW_MECHANISMS:
        return False
    return str(record.get("review_status")) == REVIEW_APPROVED


def _source_explicitly_supports(source: dict[str, Any]) -> bool:
    """Return True when a single source explicitly supports its claim.

    A bare source name or URL is not evidence: ``supports_claim`` must be true
    and a quote/location must be present.
    """
    if not isinstance(source, dict):
        return False
    if not bool(source.get("supports_claim")):
        return False
    return bool(str(source.get("quote_or_location", "")).strip())


def _evidence_supports_claim(record: dict[str, Any], semantics: str) -> bool:
    """Return True when the record's evidence supports the claim.

    For ``correction`` semantics both the ``original`` and ``corrected`` sides
    must each carry explicit supporting evidence. A bare source name or URL is
    not evidence; ``supports_claim`` plus a quote/location is required.
    """
    sources = record.get("sources", []) or []
    if not isinstance(sources, list) or len(sources) == 0:
        return False

    if semantics == SEMANTICS_CORRECTION:
        by_role: dict[str, list[dict[str, Any]]] = {}
        for source in sources:
            if not isinstance(source, dict):
                continue
            role = str(source.get("role", "") or SOURCE_ROLE_SUPPORTING).strip()
            by_role.setdefault(role, []).append(source)
        original_ok = any(
            _source_explicitly_supports(s) for s in by_role.get(SOURCE_ROLE_ORIGINAL, [])
        )
        corrected_ok = any(
            _source_explicitly_supports(s)
            for s in by_role.get(SOURCE_ROLE_CORRECTED, [])
        )
        return bool(original_ok and corrected_ok)

    # claim / attribution / fact_check / match_source: at least one supporting
    # source with explicit evidence.
    return any(_source_explicitly_supports(s) for s in sources)


def content_review_status(
    claim: str,
    beat_id: str,
    semantics: str,
    sources: list[dict[str, Any]] | None = None,
    credit: dict[str, Any] | None = None,
    *,
    records_dir: Path | None = None,
) -> dict[str, Any]:
    """Evaluate the content-review readiness for a factual claim.

    Returns a dict with:
      - ``status``: one of ``approved``/``missing``/``needs_review``/``rejected``
      - ``record``: the matched record (or None)
      - ``detail``: human-readable reason
      - ``invalidated``: True when the claim/sources changed after review

    A missing or malformed record means ``missing``: no claim/source/date
    verification gate is satisfied, so production readiness must stay False.
    """
    if semantics not in VALID_SEMANTICS:
        return {
            "status": CONTENT_REVIEW_NEEDS_REVIEW,
            "record": None,
            "detail": f"unknown semantics {semantics!r}; content review cannot be evaluated.",
            "invalidated": False,
        }

    record = find_content_review(claim, beat_id, semantics, records_dir=records_dir)

    if record is None:
        return {
            "status": CONTENT_REVIEW_MISSING,
            "record": None,
            "detail": "no content review record matches this claim/beat/semantics.",
            "invalidated": False,
        }

    # Source identity is required to bind a review to a specific claim.
    # Without it we cannot confirm the reviewed sources still apply, so the
    # gate stays at missing (never approved) even if the claim text matches.
    if sources is None:
        return {
            "status": CONTENT_REVIEW_MISSING,
            "record": record,
            "detail": "no source identity provided; content review cannot bind to "
                      "reviewed sources and is not approved.",
            "invalidated": False,
        }

    if not _record_is_well_formed(record):
        return {
            "status": CONTENT_REVIEW_NEEDS_REVIEW,
            "record": record,
            "detail": "content review record is malformed; cannot be relied upon.",
            "invalidated": False,
        }

    review_status = str(record.get("review_status"))
    if review_status == REVIEW_REJECTED:
        return {
            "status": CONTENT_REVIEW_REJECTED,
            "record": record,
            "detail": "content review was rejected by the reviewer.",
            "invalidated": False,
        }

    # Invalidation is independent of trust: if the claim or sources changed
    # after review, the prior review is invalidated regardless of mechanism.
    record_claim = str(record.get("claim", ""))
    invalidated = canonical_claim(record_claim) != canonical_claim(claim)
    if not invalidated and sources is not None:
        record_sources = record.get("sources", []) or []
        invalidated = _sources_changed(record_sources, sources)

    # Credit attribution invalidation: if the card prints source/date credit,
    # confirm it maps to a reviewed source's publisher/publication date.
    # Changing credit attribution invalidates the review.
    credit_invalidated = False
    if credit is not None and not invalidated:
        credit_source = str(credit.get("source", "")).strip()
        credit_date = str(credit.get("date", "")).strip()
        if credit_source or credit_date:
            credit_invalidated = not _credit_matches_reviewed_source(credit, sources)
    if credit_invalidated:
        invalidated = True

    if invalidated:
        return {
            "status": CONTENT_REVIEW_NEEDS_REVIEW,
            "record": record,
            "detail": "claim or sources changed after review; prior review is invalidated.",
            "invalidated": True,
        }

    if not _evidence_supports_claim(record, semantics):
        return {
            "status": CONTENT_REVIEW_NEEDS_REVIEW,
            "record": record,
            "detail": "no source explicitly supports the claim with a quote/location.",
            "invalidated": False,
        }

    # Trust gate: only a trusted human-approval mechanism can turn a recorded
    # approval into a trusted approved status. A self-asserted reviewer name
    # (e.g. reviewer="owner") is not enough.
    if not _is_trusted_approval(record):
        mechanism = str(record.get("review_mechanism", "")).strip() or "(none)"
        return {
            "status": CONTENT_REVIEW_NEEDS_REVIEW,
            "record": record,
            "detail": (
                f"review status is {review_status} but approval mechanism "
                f"{mechanism} is not a trusted human-approval path; "
                "content review cannot be treated as approved"
            ),
            "invalidated": False,
        }

    if review_status == REVIEW_NEEDS_REVIEW:
        return {
            "status": CONTENT_REVIEW_NEEDS_REVIEW,
            "record": record,
            "detail": "content review is recorded but still needs owner review.",
            "invalidated": False,
        }

    # review_status == REVIEW_APPROVED, trusted mechanism, evidence supports,
    # and not invalidated.
    return {
        "status": CONTENT_REVIEW_APPROVED,
        "record": record,
        "detail": "content review approved: claim has supporting evidence and trusted review provenance.",
        "invalidated": False,
    }


def _sources_changed(
    record_sources: list[dict[str, Any]], current_sources: list[dict[str, Any]]
) -> bool:
    """Return True when the current sources differ from the reviewed sources.

    Comparison is by url, document_id, publisher and publication date: a
    different source URL, document ID, publisher, or publication date
    invalidates the review. Each field is compared independently (url and
    document_id are not fallbacks for each other).
    """
    if len(record_sources) != len(current_sources):
        return True
    def key(source: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            str((source or {}).get("url") or "").strip(),
            str((source or {}).get("document_id") or "").strip(),
            str((source or {}).get("publisher") or "").strip(),
            str((source or {}).get("published_at") or "").strip(),
        )
    return sorted(key(s) for s in record_sources) != sorted(key(s) for s in current_sources)


def content_review_readiness_fields(
    claim: str,
    beat_id: str,
    semantics: str,
    sources: list[dict[str, Any]] | None = None,
    credit: dict[str, Any] | None = None,
    *,
    records_dir: Path | None = None,
) -> dict[str, Any]:
    """Return content-review fields shaped for the planner readiness dict."""
    result = content_review_status(
        claim, beat_id, semantics, sources, credit, records_dir=records_dir
    )
    return {
        "content_review": result["status"],
        "content_review_detail": result["detail"],
        "content_review_invalidated": bool(result.get("invalidated")),
        "content_review_record_id": str(
            (result.get("record") or {}).get("record_id", "")
        ),
    }
