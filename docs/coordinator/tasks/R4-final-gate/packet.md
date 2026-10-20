# Task R4 — Final gate (full S1-S5 strict on fresh render) — packet

Sprint 2-day, Day 2 afternoon. Depends on R2 + R3. One fresh render,
full strict grade, human PASS or FAIL. This is the sprint done-marker.

## Task

- task_id: R4-final-gate
- goal: Render one fresh short-form 9:16 MP4 on template 12.0.0 with R2
  gate + R3 fixes in place, grade every S1-S5 check strict with frame
  evidence, and deliver the human PASS/FAIL verdict package.
- repo_root: `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`
- worktree_or_branch: `main`
- agent: `@ace-reviewer` with model `opencode/nemotron-3.5-super-vl-free`
  (read-only audit; no code changes in this task)

## First reads (in order)

1. `docs/coordinator/STATE.json`
2. `docs/coordinator/AUDIT_RUBRIC_STRICT_V1.md`
3. `docs/coordinator/tasks/R1-render-baseline/report.md`
4. `docs/coordinator/tasks/R3-beauty-fix/report.md`
5. `docs/coordinator/r3-r4-c6-c7-reconciliation-2026-10-20.md` and
   `docs/coordinator/contracts/c7-card-contract.md`

## Preconditions status — C6/C7 (2026-10-20)

The card text/media contract work is complete as a contract layer: 89/89 built
cards have one record, planner bindings are frozen, media is fail-closed on
use-scoped rights, and QA never PASSes a legacy/fallback graph. This does
**not** clear R3's unresolved BLOCKED items: per-beat grammar variety (S3.1),
owner-purpose real media (S4.1), source-card/provenance beats (S3.5/S4.2),
hook→evidence→attribution hierarchy (S2.5), and headline wipe motion (S5.2).

Therefore step 1 below still stops R4 before rendering. Do not claim the final
gate is ready to run, and do not start a fresh final-gate render, until those
blockers are fixed at the planner/template/data layer or the owner explicitly
accepts a scoped exception and a human review is scheduled.

## Allowed files

- `runtime/renders/` (fresh render output for grading)
- `docs/coordinator/reviews/R4-final-gate.md` (verdict package)
- `docs/coordinator/tasks/R4-final-gate/report.md`

## Forbidden paths (always)

- All code edits (reviewer is read-only)
- `.env`, credentials, `docs/ENGINE_STATE.md`

## Steps

1. Read the R3 report first. If R3 still has unresolved BLOCKED items, stop
   before rendering, report R4 as blocked with the specific prerequisites,
   and do not claim the final gate is ready to run.
2. Trigger or locate one fresh render (record run_id, command, template
   pin 12.0.0, renderer version).
3. Grade every S1-S5 check with frame path or timestamp evidence.
   Strict: any visible defect is FAIL. No PARTIAL, no NOT_ASSESSED.
4. Write verdict package: per-check table, worst frames, rights-gate
   confirmation (R2 refusal path exercised or N/A with reason), and the
   recommended human verdict PASS or FAIL.
5. A human opens the contact sheet + MP4 to confirm. Nemotron findings
   alone never conclude PASS.

## Acceptance checks

- [ ] Fresh MP4 + contact sheet + ffprobe evidence recorded
- [ ] Every S1-S5 check graded with evidence
- [ ] Verdict package written with recommended PASS/FAIL + reasons

## Report

- Write verdict to `docs/coordinator/reviews/R4-final-gate.md` and a
  short task report to `docs/coordinator/tasks/R4-final-gate/report.md`.
- Then run `python tools/ace_state.py --write` and stop. Do not commit.
