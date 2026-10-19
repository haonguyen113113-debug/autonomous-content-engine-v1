# Task R2 — Rights gate minimal (renderer refuses ineligible) — packet

Sprint 2-day, Day 1 afternoon. Depends on R1 run existing (not on R1
verdict). Smallest gate so illegal assets can never reach pixels.

## Task

- task_id: R2-rights-gate
- goal: Add the minimal C1 check inside the short-form render path: any
  graph node whose asset lacks `eligible` for the exact proposed use is
  refused (fallback slot or blocked render with reason), never silently
  rendered.
- repo_root: `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`
- worktree_or_branch: `main`
- agent: `@ace-implementer` with model `opencode/nemotron-3.5-super-vl-free`

## First reads (in order)

1. `docs/coordinator/STATE.json`
2. `docs/coordinator/contracts/c1-rights-scope.md` (v1.0)
3. `docs/coordinator/tasks/R1-render-baseline/report.md` (if exists)

## Allowed files (disjoint — no beauty fixes here)

- `apps/video_renderer.py` (gate only, short-form path)
- `tests/test_rights_gate.py` (new, minimal)

## Forbidden paths (always)

- `runtime/`, `.env`, credentials, `docs/ENGINE_STATE.md`
- Layout, grammar, motion, chart code (belongs to R3)
- Long-form paths (out of sprint)

## Architecture constraints

- `verified` is not blanket permission. Gate checks the exact proposed
  use (beat, slot, upload scope), not the asset row flag.
- YouTube-sourced items never yield `eligible`.
- Copyright exceptions stay `needs_human_review` and are refused.

## Acceptance checks

- [ ] `python -m pytest tests/test_rights_gate.py -q` passes
- [ ] Ineligible + needs-review nodes refused (test proves both)
- [ ] Existing short-form render still runs when assets are eligible

## Report

- Write to: `docs/coordinator/tasks/R2-rights-gate/report.md`
- Include: files changed, test command + result, refusal evidence.
- Then run `python tools/ace_state.py --write` and stop. Do not commit.
