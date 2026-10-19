# C4 — Visual Scene Graph (deterministic planner output) — v1.0

Status: frozen for worker tasks. Changes require coordinator approval.

## Rule

A deterministic Visual Planner maps C3 intent plus suitable and approved
assets plus a pinned Template Foundation package to a versioned Scene Graph.
The same inputs and versions must yield the same plan.

## Scene Graph node minimum

- `node_id`, `beat_id`, `visual_grammar`: one of `editorial`, `tactical`,
  `statistical`, `documentary`, `hook`
- `template_id`, `template_version` (pinned; draft packages are preview-only)
- `asset_id` (must be saved, suitable, C1-eligible, owner-approved)
- `composition`: slot, crop, safe-area behavior, duration, transition — as
  data chosen by the planner, not invented by the renderer
- `fallback_reason` when a slot falls back (asset missing, rights blocked)
- `planner_version`, `schema_version: "c4/1.0"`, input hashes

## Rules

- The renderer consumes graph nodes. It never invents story or re-decides
  layout.
- Pillow may render static layers but layout and storytelling decisions must
  not hide inside renderer code.
