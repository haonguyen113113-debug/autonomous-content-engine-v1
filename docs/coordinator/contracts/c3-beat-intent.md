# C3 — Semantic beat intent (LLM output boundary) — v1.0

Status: frozen for worker tasks. Changes require coordinator approval.

## The LLM proposes intent only

Each beat carries exactly these semantic fields and nothing concrete:

- `beat_id`, `purpose`
- `visual_goal`: what the viewer must understand
- `focal_subject`: entity reference from `taxonomy.json` or `data/entities/`
- `evidence_type`: e.g. real footage, still, tactical diagram, data chart,
  quote card
- `emphasis`: what matters most in this beat
- `conceptual_motion`: e.g. push-in for tension, hold for reading — a
  concept, not a numeric animation spec

## Forbidden in LLM output

Pixels, coordinates, font sizes, color codes, concrete layout, z-order,
timing curves, FFmpeg filter chains. Those belong to the deterministic
planner (C4) and the renderer.

## Validation

Intent that contains concrete layout values is rejected at the schema
boundary and returned to the worker as a failure, not silently repaired.
Record `contract_version: "c3/1.0"`, model id, and prompt version with every
intent artifact.
