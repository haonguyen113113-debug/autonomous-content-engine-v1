# Task W4 — Scene Graph renderer slice plus strict beauty QA (C4/C5) — packet

Owner goal 2026-10-18: beautiful render plus image QA, strict threshold
(small visible defects FAIL), short-form 9:16 first on template 0.8.0,
long-form later on stronger PC.

## Task

- task_id: W4-render-qa
- goal: Make the renderer consume C4 graph nodes for approved stills and
  video slots on short-form 9:16, then enforce the strict audit rubric
  `docs/coordinator/AUDIT_RUBRIC_STRICT_V1.md` so any S1-S5 defect FAILs.
- repo_root: `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`
- worktree_or_branch: `main` (create `w/w4-render-qa` worktree before
  editing if running parallel with other tasks)
- agent: `@ace-implementer` with model `opencode/nemotron-3.5-super-vl-free`

## First reads (in order)

1. `docs/ENGINE_STATE.md`
2. `docs/audit-checkpoint-2026-10-08.md` (layout and QA sections)
3. `docs/coordinator/AUDIT_RUBRIC_STRICT_V1.md` (mandatory gate)
4. Frozen contracts: `c4/1.0`, `c5/1.0`, `c1/1.0`

## Allowed files (disjoint — no overlap with W1/W2/W3)

- `apps/video_renderer.py` (extend short-form graph-consumption path only;
  no long-form work in this task)
- `apps/measurement/render_qa.py` (new: implement S1-S5 strict checks)
- `tests/test_render_qa.py` (new)

## Forbidden paths (always)

- `runtime/`, `.env`, credentials, voice recordings, generated renders
- `docs/ENGINE_STATE.md` (coordinator owns this file)
- `apps/asset_library/*`, `apps/scene_graph/*` (owned by other tasks)
- Long-form 16:9 templates and code paths (Gate B, out of scope)

## Architecture constraints

- Renderer consumes the Scene Graph: timing, crop, safe areas, overlays,
  transitions resolve from graph plus pinned template 0.8.0. No story
  invention in renderer code.
- Pillow may render static layers but layout decisions must not hide in
  renderer code.
- QA evaluates rendered scenes with timestamp or frame evidence. Strict
  mode: any S1-S5 defect is FAIL. NEEDS_REVIEW only when evidence is
  missing, never a silent PASS.

## Acceptance checks

- [ ] `python -m pytest tests/test_render_qa.py -q` passes
- [ ] Renderer refuses graph nodes whose assets lack C1 eligibility for the
  proposed use
- [ ] QA findings carry `contract_version: "c5/1.0"` plus rubric version
  `audit-rubric/1.0-strict`, layer S1-S5, verdict, evidence path,
  severity, confidence
- [ ] Short-form contact sheet plus at least one MP4 actually inspected and
  graded against every S1-S5 check; any single defect recorded as FAIL

## Report

- Write to: `docs/coordinator/tasks/W4-render-qa/report.md`
- Include: files changed, contract versions used, rubric version, exact
  test command and result, render evidence path with per-check verdicts,
  remaining risks.
- Do not commit, push, publish, or buy a service. Stop after writing the
  report.
