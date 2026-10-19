# Task R3 — Beauty fix loop (worst R1 defects first) — packet

Sprint 2-day, Day 2 morning. Depends on R1 defect list. Fix ONE layer at
a time, re-render, re-grade. Stop when S2-S5 FAIL-free or timebox hits.

## Task

- task_id: R3-beauty-fix
- goal: Fix R1 defects worst-first in `apps/video_renderer.py` short-form
  path only, re-rendering after each fix and re-grading S2-S5 strict until
  clean or timebox expires.
- repo_root: `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`
- worktree_or_branch: `main`
- agent: `@ace-implementer` with model `opencode/nemotron-3.5-super-vl-free`

## First reads (in order)

1. `docs/coordinator/STATE.json`
2. `docs/coordinator/tasks/R1-render-baseline/report.md` (defect list)
3. `docs/coordinator/AUDIT_RUBRIC_STRICT_V1.md`
4. Template 12.0.0 `design-tokens.json` + `visual-modes.json` (locked
   values — read, do not edit templates in this task)

## Allowed files

- `apps/video_renderer.py` (short-form path only)
- `docs/coordinator/tasks/R3-beauty-fix/report.md`

## Forbidden paths (always)

- `template_foundation/` (locked — template changes need a new version
  and owner review, out of sprint)
- `runtime/` except writing new render output for grading
- `.env`, credentials, `docs/ENGINE_STATE.md`, long-form paths
- Rights logic (R2 owns it), new contracts

## Fix order (worst-first from R1)

1. S2 layout: safe-area violations, overlaps, diacritics, hierarchy.
2. S3 grammar: wrong plate per beat, repetitive cards, identity breaks,
   prohibited effects, chart semantics.
3. S5 motion: missing stops, looping decoration, excess transitions.
4. Do NOT invent story in renderer; layout data comes from planner/graph
   or pinned template. If the defect needs a planner or template change,
   record it as BLOCKED with evidence instead of hacking the renderer.

## Acceptance checks

- [ ] Each fix followed by a fresh render + contact sheet re-grade
- [ ] Report shows before/after per defect with frame evidence
- [ ] Remaining FAILs listed with responsible layer + next fix

## Report

- Write to: `docs/coordinator/tasks/R3-beauty-fix/report.md`
- Include: defects fixed, render run_ids, before/after verdicts,
  remaining FAILs, BLOCKED items needing planner/template work.
- Then run `python tools/ace_state.py --write` and stop. Do not commit.
