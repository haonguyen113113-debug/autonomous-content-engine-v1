# C5 — QA finding on rendered scenes — v1.0

Status: frozen for worker tasks. Changes require coordinator approval.

## Rule

QA evaluates rendered scenes, not intended inputs. Verdicts require frame
or timestamp evidence.

## Finding fields

- `finding_id`, `beat_id` or `node_id`, `layer`: `structural`, `visual`,
  `semantic`, `temporal`, `brand`
- `verdict`: `PASS`, `FAIL`, `PARTIAL`, `NEEDS_REVIEW`
- `evidence`: frame path or timestamp plus observed text or measurement
- `severity`, `confidence`, `contract_version: "c5/1.0"`

## Hard rules

- Never report `PASS` from an asset ID or an expected code path alone.
- Use `NEEDS_REVIEW` whenever the judgment is uncertain.
- A video-capable model may assist semantic and temporal checks but its
  score is never proof on its own; calibrate against owner audit examples.
