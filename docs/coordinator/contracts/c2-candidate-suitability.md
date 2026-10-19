# C2 — Candidate board, suitability, and owner approval — v1.0

Status: frozen for worker tasks. Changes require coordinator approval.

## Four separate objects — never merge them

1. **Candidate**: a discovered item with preview, provenance, license and
   credit, technical metadata, discovery source. Not yet saved.
2. **Saved library asset**: an ingested candidate the owner chose to keep.
3. **Suitability score**: how well a saved asset serves a beat (exact match,
   freshness, illustrative action, shot variety, beat coverage). This is not
   a rights decision.
4. **Rights eligibility**: the C1 decision for a specific proposed use. This
   is not a visual score.

## Candidate board row must show

- `candidate_id`, preview path or URL, `source`, `creator`, `license_type`,
  credit text, `provenance_ref`
- `suitability`: score plus reason codes per beat
- `rights_preview`: likely eligibility warnings for the intended upload
  scope, never a silent approval
- `owner_decision`: `pending`, `saved`, `approved_for_use`, `rejected`

## Rules

- The owner chooses whether to save or use an external candidate.
- The renderer may only use saved assets that are both suitable and
  C1-`eligible` plus owner-approved where required.
