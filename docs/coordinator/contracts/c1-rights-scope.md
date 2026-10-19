# C1 — Upload-use rights scope and eligibility — v1.0

Status: frozen for worker tasks. Changes require coordinator approval.

## Rule

A rights decision answers one question: is this asset eligible for this
specific proposed use and upload scope? It is separate from whether the
asset looks suitable for a beat.

## Required fields on every decision

- `asset_id`, `license_type`, `source`, `provenance_ref`
- `proposed_use`: content id, beat id, media slot, upload destination
  (platform, account, territory), publish date window
- `rights_state`: one of `eligible`, `ineligible`, `needs_human_review`
- `reason`: short machine-readable code plus human sentence
- `decided_by`, `decided_at`, `contract_version: "c1/1.0"`

## Hard rules

- `verified` on the asset row is not blanket permission.
- No asset enters the render composition unless its decision for that exact
  proposed use is `eligible` and, where required, owner-approved.
- Copyright exceptions stay in `needs_human_review`. An LLM cannot approve
  them.
- YouTube results are discovery links only. They never produce an `eligible`
  decision and are never downloaded as assets.
