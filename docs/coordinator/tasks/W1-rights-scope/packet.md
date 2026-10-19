# Task W1 — Rights scope gate (C1) — packet

## Task

- task_id: W1-rights-scope
- goal: Add a use-scoped rights decision that blocks renderer selection
  unless the exact proposed use is `eligible` under contract C1 v1.0, with
  `needs_human_review` as the fail-closed state for copyright exceptions.
- repo_root: `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`
- worktree_or_branch: `main` (create `w/w1-rights-scope` worktree before
  editing if running parallel with other tasks)
- agent: `@ace-implementer` with model `opencode/nemotron-3.5-super-vl-free`

## First reads (in order)

1. `docs/ENGINE_STATE.md`
2. `docs/engine-gap-audit-2026-10-16.md` (Stage 1)
3. Frozen contracts: `c1/1.0`, `c2/1.0`

## Allowed files (disjoint — no overlap with W2/W3/W4)

- `apps/asset_library/rights_scope.py` (new)
- `tests/test_rights_scope.py` (new)

## Forbidden paths (always)

- `runtime/`, `.env`, credentials, voice recordings, generated renders
- `docs/ENGINE_STATE.md` (coordinator owns this file)
- `apps/asset_library/discovery.py`, `apps/scene_graph/*`,
  `apps/video_renderer.py`, `apps/measurement/*` (owned by other tasks)

## Architecture constraints (repeat in every packet)

- Template Foundation is stable channel identity; Asset Library supplies
  variable media and never owns the template.
- LLM proposes semantic beat intent only. No pixels, font sizes, color
  codes, or layout coordinates from the model.
- Rights eligibility is per proposed use and upload scope, separate from
  visual suitability. `verified` is not blanket permission. Copyright
  exceptions need human review; the model cannot approve them.
- YouTube is discovery links only. Never download its video as an asset or
  infer usage rights.

## Acceptance checks

- [ ] `python -m pytest tests/test_rights_scope.py -q` passes
- [ ] Decision record carries `contract_version: "c1/1.0"` plus asset,
  proposed use, verdict, reason, decider, timestamp
- [ ] Ineligible and needs-review uses are blocked by the gate function
  (test proves both)
- [ ] YouTube-sourced items can never yield `eligible`

## Report

- Write to: `docs/coordinator/tasks/W1-rights-scope/report.md`
- Include: files changed, contract versions used, exact test command and
  result, remaining risks.
- Do not commit, push, publish, or buy a service. Stop after writing the
  report.
