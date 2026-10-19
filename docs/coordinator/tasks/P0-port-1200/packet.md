# Task P0 — Port released 12.0.0 pack + renderer delta — packet

Sprint 2-day, Day 1 FIRST. Blocks R1-R4. Owner correction: 0.8.0 is
obsolete; canonical is 12.0.0 released in Default Project worktree.

## Task

- task_id: P0-port-1200
- goal: Port the released 12.0.0 short-form pack plus the renderer and
  contract delta from Default Project into Desktop, so R1 grades the
  real Cyber Pitch pack instead of 0.8.0.
- repo_root: `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`
- source_root: `C:/Users/Infomation Technolog/Documents/Default Project/autonomous-content-engine-v1` at commit `14a62eb`
- agent: `@ace-implementer` with model `opencode/nemotron-3.5-super-vl-free`

## First reads (in order)

1. `docs/coordinator/STATE.json`
2. `docs/coordinator/GOAL_AND_THRESHOLDS.md` (12.0.0 section)
3. Source `docs/scene-graph-contract.md` + `docs/renderer-qa-scene-graph.md`

## Port list (copy, then wire, never reinvent)

- `template_foundation/templates/allen-knows-ball/12.0.0/` (full dir,
  released, read-only after port) + catalog entry status `released`
- `apps/video_renderer.py` delta (179KB source vs 84KB Desktop):
  Scene Graph execution path behind `ACE_SCENE_GRAPH_RENDER=1`, legacy
  byte-identical when flag off
- `apps/scene_graph/` (builder, executor, intent, schema)
- `apps/asset_library/rights_scope.py` + `apps/measurement/render_qa.py`
- `apps/card_selector.py`, `apps/sportskit/crests.py` deltas
- `tests/test_rights_scope.py`, `tests/test_scene_graph*.py`,
  `tests/test_renderer_scenegraph.py`, `tests/test_crest_store.py`

## Forbidden paths (always)

- Do not edit the ported 12.0.0 pack after copy (released = immutable)
- `runtime/`, `.env`, credentials, `docs/ENGINE_STATE.md`
- Long-form 12.0.0, distribution, publishing (out of sprint)
- No commit or push

## Acceptance checks

- [ ] `catalog.json` lists 12.0.0 short-form as `released`
- [ ] `python -m pytest tests/test_rights_scope.py tests/test_scene_graph.py tests/test_renderer_scenegraph.py -q` passes
- [ ] Legacy render with flag off is byte-identical to pre-port output
- [ ] 12.0.0 preview proofs exist (at least hook + one data card)

## Report

- Write to: `docs/coordinator/tasks/P0-port-1200/report.md`
- Include: files ported, test command + result, legacy parity evidence.
- Then run `python tools/ace_state.py --write` and stop. Do not commit.
