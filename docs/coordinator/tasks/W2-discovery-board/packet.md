# Task W2 — Multi-format discovery and candidate board (C2) — packet

## Task

- task_id: W2-discovery-board
- goal: Extend discovery with a first-class video provider path and a
  ranked candidate board that keeps provenance, suitability, and C1 use
  eligibility visibly separate, with YouTube as reference-only links.
- repo_root: `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`
- worktree_or_branch: `main` (create `w/w2-discovery-board` worktree before
  editing if running parallel with other tasks)
- agent: `@ace-implementer` with model `opencode/nemotron-3.5-super-vl-free`

## First reads (in order)

1. `docs/ENGINE_STATE.md`
2. `docs/audit-checkpoint-2026-10-08.md` (candidate board section)
3. Frozen contracts: `c1/1.0`, `c2/1.0`

## Allowed files (disjoint — no overlap with W1/W3/W4)

- `apps/asset_library/discovery.py` (extend, keep existing image path green)
- `apps/asset_library/candidate_board.py` (new)
- `tests/test_candidate_board.py` (new)

## Forbidden paths (always)

- `runtime/`, `.env`, credentials, voice recordings, generated renders
- `docs/ENGINE_STATE.md` (coordinator owns this file)
- `apps/asset_library/rights_scope.py`, `apps/scene_graph/*`,
  `apps/video_renderer.py`, `apps/measurement/*` (owned by other tasks)

## Architecture constraints

- External candidates are discovered and ranked before ingestion. The owner
  chooses whether to save or use them.
- Candidate, saved asset, suitability score, and rights eligibility are four
  separate objects. Never merge them into one flag.
- YouTube may provide discovery links only; never download its video as an
  asset or infer usage rights.
- No spend on stock or licensed sources without explicit owner approval.

## Acceptance checks

- [ ] `python -m pytest tests/test_candidate_board.py tests/test_ingest.py -q` passes
- [ ] Board rows show preview, provenance, license and credit, suitability
  reason codes, use-scope warnings, and `pending/saved/approved/rejected`
- [ ] Video provider path returns technical metadata; image path unbroken

## Report

- Write to: `docs/coordinator/tasks/W2-discovery-board/report.md`
- Include: files changed, contract versions used, exact test command and
  result, remaining risks.
- Do not commit, push, publish, or buy a service. Stop after writing the
  report.
