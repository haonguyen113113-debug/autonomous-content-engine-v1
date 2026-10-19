# Task W3 — Semantic intent plus deterministic Scene Graph (C3/C4) — packet

## Task

- task_id: W3-scene-graph
- goal: Add the validated C3 semantic beat-intent schema and a
  deterministic C4 Visual Planner that maps intent plus suitable and
  approved assets plus a pinned template to a versioned Scene Graph.
- repo_root: `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`
- worktree_or_branch: `main` (create `w/w3-scene-graph` worktree before
  editing if running parallel with other tasks)
- agent: `@ace-implementer` with model `opencode/nemotron-3.5-super-vl-free`

## First reads (in order)

1. `docs/ENGINE_STATE.md`
2. `docs/engine-gap-audit-2026-10-16.md` (Stage 2)
3. Frozen contracts: `c3/1.0`, `c4/1.0`, `c1/1.0`

## Allowed files (disjoint — no overlap with W1/W2/W4)

- `apps/scene_graph/intent.py` (new: C3 schema plus validation)
- `apps/scene_graph/planner.py` (new: deterministic planner)
- `apps/scene_graph/schema.py` (new: C4 graph schema)
- `tests/test_scene_graph_contract.py` (new)

## Forbidden paths (always)

- `runtime/`, `.env`, credentials, voice recordings, generated renders
- `docs/ENGINE_STATE.md` (coordinator owns this file)
- `apps/asset_library/rights_scope.py`,
  `apps/asset_library/candidate_board.py`, `apps/video_renderer.py`,
  `apps/measurement/*` (owned by other tasks)

## Architecture constraints

- LLM output is semantic intent only: visual goal, focal subject, evidence
  type, emphasis, conceptual motion. Reject concrete layout values at the
  schema boundary.
- Planner is deterministic: same intent, assets, template versions, and
  planner version yield byte-identical graphs. Record planner, template,
  asset, and schema versions plus fallback reasons.
- Renderer is a consumer of the graph; do not put storytelling decisions in
  this task.

## Acceptance checks

- [ ] `python -m pytest tests/test_scene_graph_contract.py -q` passes
- [ ] Intent with concrete layout values is rejected, not repaired
- [ ] Planner rerun on same inputs yields identical graph hash
- [ ] Graph nodes reference only C1-eligible, owner-approved assets

## Report

- Write to: `docs/coordinator/tasks/W3-scene-graph/report.md`
- Include: files changed, contract versions used, exact test command and
  result, determinism evidence, remaining risks.
- Do not commit, push, publish, or buy a service. Stop after writing the
  report.
