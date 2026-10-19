# Task R1 — Render baseline audit (read-only + one render) — packet

Sprint 2-day, Day 1 morning. Run FIRST. No code changes except a render
run plus contact sheet. Output is the defect list R3 will fix.

## Task

- task_id: R1-render-baseline
- goal: Produce one fresh short-form 9:16 render on template 12.0.0 plus
  contact sheet, then grade it against every S1-S5 check in
  `AUDIT_RUBRIC_STRICT_V1.md` and list defects worst-first.
- repo_root: `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`
- worktree_or_branch: `main` (no worktree needed, read-only)
- agent: `@ace-implementer` with model `opencode/nemotron-3.5-super-vl-free`

## First reads (in order)

1. `docs/coordinator/STATE.json`
2. `docs/coordinator/AUDIT_RUBRIC_STRICT_V1.md`
3. `docs/coordinator/GOAL_AND_THRESHOLDS.md`

## Allowed files

- `runtime/renders/` (write render output + contact sheet here; ignored
  by git, explicitly allowed for this task)
- `docs/coordinator/tasks/R1-render-baseline/report.md` (your report)

## Forbidden paths (always)

- All `apps/`, `tests/`, `template_foundation/` code (read-only audit)
- `runtime/asset_library.db`, `runtime/engine.db`, `.env`, credentials
- `docs/ENGINE_STATE.md` (coordinator owns)

## Steps

1. Run the existing short-form render path (template preview or full run)
   on template 12.0.0, 1080x1920. Record exact command + run_id.
2. Extract contact sheet (frames across the run) + ffprobe JSON.
3. Grade S1 (structural via ffprobe), S2 (safe area, overlap, diacritics,
   hierarchy), S3 (grammar per beat, identity, chart semantics), S4
   (media honesty), S5 (motion) — every check PASS/FAIL with frame path
   or timestamp evidence.
4. Rank defects worst-first with the responsible layer for each
   (planner, renderer, template, asset). Strict mode: any visible defect
   is FAIL.

## Acceptance checks

- [ ] One fresh MP4 + contact sheet + ffprobe evidence exist under
  `runtime/renders/<run_id>/`
- [ ] Every S1-S5 check graded with evidence, no NOT_ASSESSED
- [ ] Defect list ranked worst-first with responsible layer per defect

## Report

- Write to: `docs/coordinator/tasks/R1-render-baseline/report.md`
- Include: run_id, render command, MP4 + contact paths, per-check table,
  ranked defects, what R3 should fix first.
- Then run `python tools/ace_state.py --write` and stop. Do not commit.
