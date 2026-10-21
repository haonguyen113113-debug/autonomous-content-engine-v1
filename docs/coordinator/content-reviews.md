# Content review contract — factual claim verification (draft)

Status: draft. This document defines the shared content-review gate for
factual claims in beats. It is independent of any card/visual grammar: a card
decides *how* to present content that has already been reviewed; it never
verifies the claim itself.

## Purpose

Separate *content verification* (is the claim supported by evidence?) from
*visual approval* (does the static PNG look right?), *text fit* (does text
overflow its box?), *rights eligibility* (is the asset cleared for this use?),
and *contract execution* (does the card execute its authored contract?). Each
is an independent status; production readiness requires all applicable gates
to pass.

## Record schema — `ace-content-review/1.0`

Records live under `docs/coordinator/content_reviews/` as JSON files, one per
claim/beat/semantics. Example:
`docs/coordinator/content_reviews/EXAMPLE-content-review-schema.json`.

| Field | Meaning |
|---|---|
| `schema_version` | Must be `ace-content-review/1.0`. |
| `record_id` | Unique record identifier. |
| `beat_id` | Beat/run identifier the claim belongs to. |
| `claim` | Verbatim factual claim text. |
| `semantics` | One of: `claim`, `attribution`, `correction`, `fact_check`, `match_source`. |
| `sources[]` | Each source: `url` or `document_id`, `publisher`, `published_at`, `accessed_at`, `quote_or_location`, `supports_claim` (bool), `role` (`original`/`corrected`/`supporting`), `notes`. |
| `evidence_link` | How the claim maps to the evidence (not just a source name/URL). |
| `review_status` | `approved`, `needs_review`, or `rejected`. |
| `review_mechanism` | How the review was approved. Only a mechanism in the trusted set counts as trusted approval (see Trust boundary below). |
| `reviewer` | Human reviewer who made the decision (traceability only; not trust evidence by itself). |
| `reviewed_at` | Date the review was made. |
| `reason` | Reason / notes for the decision. |
| `scope` | What the review covers and what it explicitly does not cover. |

## Trust boundary — trusted human approval

A record is a JSON file and can be authored by an agent. Therefore `reviewer=
"owner"` and `review_status="approved"` are **self-assertions and are NOT
trusted by themselves**.

The engine treats an approval as trusted only when `review_mechanism` is in
`TRUSTED_REVIEW_MECHANISMS` (defined in `apps/measurement/content_review.py`).
That set is currently **empty**: the repo wires no human-approval artifact, so
no record is trusted as approved. Every self-asserted approval stays at
`needs_review` until the owner plugs in a real human-approval path (for
example a signed owner review record or a trusted policy artifact).

Until such a path exists:
- Content review for synthetic fixture claims is `missing`/`needs_review`.
- `production_ready` stays `False` for any beat that requires content review.

## Matching rules

A record is consulted **only when claim text (canonicalised), `beat_id` and
`semantics` all match exactly**. No wildcard matching:

- A record for one claim never approves another claim.
- A record for one beat never approves another beat.
- A record for one semantics class (e.g. `claim`) never approves another
  (e.g. `fact_check`).
- A missing record means "not reviewed" → content review status `missing`.

## Source identity vs credit text

Source identifiers passed to the gate must be real source identity
(`url` / `document_id` / `publisher`), **not** credit display text
(`source` / `date` strings shown on screen).

### Segment-level source identity (`evidence_identity`)

The beat/run contract segment may carry an optional `evidence_identity`
field with structured source identity:

```json
"evidence_identity": {
  "sources": [
    {
      "url": "https://example.com/official-match-report",
      "document_id": "doc-1",
      "publisher": "Example Sports Federation",
      "published_at": "2026-10-20T22:00:00+07:00",
      "accessed_at": "2026-10-21T08:00:00+07:00",
      "quote_or_location": "Kết quả cuối cùng: Hà Nội 2 - 0 TP.HCM, phút 78 và phút 89.",
      "supports_claim": true,
      "role": "supporting"
    }
  ]
}
```

This maps directly to the content review record's `sources[]` format. The
planner (`apps/card_selector.py`) extracts `evidence_identity.sources` from
the segment via `_extract_evidence_sources()` and passes them to the
content-review gate as `sources`.

The script normalization layer (`apps/content_workflow.py`, `_clean_segment`)
preserves `evidence_identity` when present on an input segment. `apply_script_fix`
also carries it over from the old segment when regenerating a beat. If upstream
(Hermes or a research agent) does not supply `evidence_identity`, the key is
simply absent and the gate stays fail-closed at "missing".

### Credit attribution verification

`graphic_data.source` and `graphic_data.date` are credit display text shown
on the card. They are **never** used as source identity (URL, document ID, or
publisher). However, when a card prints source/date credit **and** the
content-review gate has reviewed sources, the planner verifies that the credit
attribution maps to a reviewed source's publisher and publication
date (`_credit_matches_reviewed_source` in `content_review.py`):

- Credit source name is compared **exactly** (case- and diacritics-insensitive,
  after Unicode normalization) against reviewed sources' `publisher`. Substring
  matching in either direction does **not** match; no alias matching is
  performed because no alias contract is defined.
- Credit date is compared (date portion only) against reviewed sources'
  `published_at`.

If credit text exists but cannot be confirmed to map to a reviewed source, the
review is invalidated (`needs_review`). Changing credit attribution (source
name or date) invalidates a prior review just like changing claim, source ID,
publisher, publication date, or quote/evidence.

### Where source identity comes from

Source identity is expected to arrive via the beat/run contract (script
segments produced by research/Hermes). The Hermes authenticated submit/status
API and versioned Hermes payload are **not implemented** in the current repo,
so no upstream component reliably populates `evidence_identity`. Until a
trusted source-identity path is wired:

- The planner passes `sources=None` when `evidence_identity` is absent.
- Content review with `sources=None` returns `missing` — never `approved`.
- `production_ready` stays `False` for any beat that requires content review.

Credit display text (`graphic_data.source`, `graphic_data.date`, `credit`)
is **never** used as source URL, document ID, or publisher.

## Invalidation

A prior review is invalidated (status `needs_review`) when:

- The claim text changes after review.
- The caller supplies current sources and they differ from the reviewed
  sources (by `url`, `document_id`, `publisher`, or `published_at`).
- The card's credit attribution (`graphic_data.source` / `graphic_data.date`)
  changes and no longer maps to a reviewed source's publisher / publication
  date.

When invalidated, a new review record is required for the new claim/sources.

## Correction semantics

For `correction` semantics, both the `original` and `corrected` sides must
each carry explicit supporting evidence (`supports_claim=true` plus a
`quote_or_location`). A correction record with only one side evidenced cannot
be `approved`; it stays at `needs_review` (and cannot be `approved` until a
trusted mechanism is wired too).

## What content review does NOT do

- It does not verify asset rights (see `apps/asset_library/rights_scope.py`).
- It does not approve visual layout, typography, or text fit (see
  `apps/measurement/render_qa.py` `check_text_fit`).
- It does not approve production readiness by itself.
- It does not make a `legacy_non_ready` or `partial` card production-ready.
- It does not apply to cards other than the one whose claim/beat/semantics it
  scopes.
- An LLM may propose sources/evidence, but acceptance must come from a trusted
  policy/human reviewer. An LLM cannot self-certify a claim as verified.

## Integration with planner/QA

- Planner readiness for a `source_card` (C-09, pack 12.1.0) requires:
  contract execution, text fit `PASS`, visual approval, AND content review
  `approved`. Any missing/rejected/needs-review content review blocks
  production readiness.
- `check_card_contract` does **not** declare a factual claim correct; it only
  checks structural execution (visible bindings, required slots, contract
  hash).
- Cards with `legacy_non_ready`/`partial` execution may have a content-review
  status recorded, but they remain non-ready regardless.
- The C-09 static visual approval record
  (`docs/coordinator/review_records/c09-source-card-12-1-0-2026-10-21.json`)
  covers `C-09 / source_card / 12.1.0` visual inspection only; it is not
  content verification.

## R4

R4 remains `BLOCKED`. This task does not clear R3 blockers (S2.5 hook
hierarchy, S3.5/S4.2 source-beat semantics, S4.1 owner-approved media/purpose,
S5.2 headline motion).
