# Engine state and next-session handoff

## Coordinator update — 2026-10-19

### Verified repository state

- Branch: `main`.
- Code integration commit: `ae6932b` (`merge: integrate latest main coordinator and rights work`), which merges the remote coordinator/R2 rights work from `origin/main` commit `50cf709` with local commit `1054aad` (`feat: align engine with hermes production workflow`).
- README now separates implemented local production workflow from the Hermes target architecture and records the last known smoke-test failure.
- Docker artifacts (`compose.yaml`, `docker/worker.Dockerfile`, `.dockerignore`) are removed. The persisted local queue worker remains runnable as `python -m apps.worker.main`.
- `docs/hermes-engine-integration.md` records the target boundary: Hermes discovers, evaluates, researches, scripts, submits, monitors, and reports; ACE validates the handoff, checks media, applies deterministic template/Scene Graph composition, voices/renders, and returns QA. The owner reviews and publishes.
- The authenticated production API and versioned Hermes payload schema are not implemented.
- Latest prior focused test record (2026-10-18, before this merge): **103 passed, 1 failed**, with identical frames at 3s and 8s in the same beat. No tests were run during the 2026-10-19 merge/documentation work; this motion failure remains unverified and open.
- No final video was visually reviewed in this workstream. Do not claim aesthetic or motion QA.

### Changes integrated in this workstream

- Added short-form C-11 opening hook card using `graphic_data.hook_text`; hook text is no longer fabricated from narration.
- Removed renderer-authored free-standing copy and its overlay paint path. Text outside authored template slots is suppressed; QA reports declared unbound text as `FAIL`.
- Kept the remote branch's render-time rights gate, safe-area adjustments, and conservative visual QA statuses while resolving the renderer conflict. Do not reintroduce free-standing caption/overlay rendering without a frozen template-slot contract.
- Integrated the remote coordinator files and R2 rights-gate work from `50cf709`.

### Next concrete work

1. Rerun the focused Scene Graph/render/rights tests on the merged `main`; first resolve the known same-beat motion assertion without weakening the test.
2. Freeze the Hermes-to-Engine JSON Schema and authenticated submit/status API against `docs/hermes-engine-integration.md`.
3. Exercise one fixture job through the durable local queue, asset gates, render, and truthful QA. Keep owner review/publishing manual.

This update describes code at `ae6932b`; it is committed as a separate handoff update. Earlier snapshots below are historical and should not override this section.

Last verified: **2026-10-18**. This is a compact handoff, not a full history.
Re-check Git and worktrees before acting because another OpenCode session may
have progressed since this snapshot.

## Product goal

Prove a dependable Soccer/Vietnamese content-production vertical slice for
Allen Knows Ball. The near-term target is short form; long form follows on the
stronger PC. Voice naturalness and publishing are not current proof gates.
The larger portfolio business in `PROJECT_SPEC.md` remains the long-term
north star, not the current implementation claim.

## Owner's current architecture constraints

- Asset discovery is multi-source and multi-format. YouTube is source
  discovery/linking only, never a video downloader or rights grant.
- Rights scope is checked for each intended upload and remains separate from
  visual suitability. The owner decides external asset saving/use; exceptions
  require human review.
- The LLM emits semantic beat intent, not concrete layout values.
- A deterministic Visual Planner creates a versioned Scene Graph from intent,
  suitable/approved assets, and the pinned Template Foundation.
- The renderer consumes the graph. QA inspects rendered scenes and reports
  uncertainty as `NEEDS_REVIEW`, not a false `PASS`.
- Distinct visual grammars create story-fit variation while the Template
  Foundation preserves channel identity.

## Verified repository snapshot

- Repository: `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`
- Branch/commit last checked: `main` / `bd9ae16` (`feat: add short-form render workflow and templates`), tracking `origin/main`.
- At the time of this snapshot, `docs/audit-checkpoint-2026-10-08.md` was the only untracked change; no implementation changes from the user's active OpenCode multi-agent run were visible in this checkout.
- `PROJECT_SPEC.md` describes a much broader autonomous business engine than the current Soccer video workflow. Keep those scopes distinct.

## Current implementation, at a glance

- Present: local SQLite evidence/observation/belief foundations; soccer entity seeds; generic-looking asset registry/resource requirement seam; basic local workflow UI; Ollama script draft; local TTS preview gate; short/long template packages; Pillow + FFmpeg render path.
- Partial: asset discovery and licensing metadata; human review; selected library still-image compositing; timeline and graphic modes; technical render report.
- Not implemented as independent production layers: use-scoped rights decision, first-class video discovery/ingest/render, candidate suitability board, semantic-intent contract, deterministic Visual Planner, versioned Scene Graph, perception-based rendered-scene QA, durable end-to-end orchestration, platform distribution/publishing, analytics/economic outcomes, and learning/reallocation.
- `apps/worker/` contains a minimal in-memory queue/demo, not a durable production job system.
- The current runtime renderer/report must be re-read before relying on earlier docs; docs and implementation have drifted.

## Active work / coordination status

Four workstreams (rights scope, discovery, Scene Graph/Planner, renderer/QA)
have been implemented, integrated, and reviewed per
`docs/integration-checkpoint-2026-10-16.md` (integration review update
2026-10-18). Contracts are frozen: rights scope (`docs/rights-scope-2026-10-16.md`),
Scene Graph (`docs/scene-graph-contract.md`), LLM/planner boundary, and QA
(`docs/renderer-qa-scene-graph.md`). No commit or push was performed (owner
instruction). `stash@{0}` does not exist; all changes are staged/unstaged in
the working tree on `main`/`bd9ae16`.

## Current implementation, at a glance

- Present (foundations): local SQLite evidence/observation/belief; soccer entity seeds; asset registry/provenance/rights; local UI; Ollama script draft; TTS preview gate; short/long template packages; Pillow + FFmpeg render path.
- New/integrated (workstreams, uncommitted):
  - `apps/asset_library/rights_scope.py` — `is_usable_for(asset, purpose)`, use-scoped rights, deny-default, human-review exceptions.
  - `apps/scene_graph/` — `intent.py`, `builder.py`, `schema.py`, `executor.py`, `pipeline.py`; deterministic Scene Graph v1, `graph_hash`, fail-closed validate.
  - `apps/card_selector.py`, `apps/video_renderer.py` (Scene Graph path, flag-gated `ACE_SCENE_GRAPH_RENDER`), `apps/measurement/render_qa.py`.
  - `apps/worker/` (persisted queue/run state), `apps/distribution/`, `apps/learning/`, `apps/measurement/`, `apps/llm.py`, `apps/orchestrator/`.
  - Many `studio_templates/*.json` (pack 12.0.0) + new `pack-drop/`, `soundpacks/`, `assets/`, `media/`, `skills/`, docs.
- Renderer reads Scene Graph nodes verbatim; no silent legacy fallback when flag on. Rights gate (`is_usable_for`) blocks attach when purpose ineligible. QA returns `PASS`/`FAIL`/`NEEDS_REVIEW` with evidence; `ready == (verdict == PASS)`.
- `video_renderer.py` modified unstaged; old `template_foundation/0.x-*` dirs deleted unstaged (superseded by pack 12.0.0). No `runtime/` writes by tests/code path under review (`runtime/` is pre-existing gitignored app data).

## Tests run

Focused integration suite (per integration-checkpoint §7) run 2026-10-18:
`tests/test_card_selector.py tests/test_card_selector_intent.py
tests/test_script_decomposition.py tests/test_workflow_end_to_end.py
tests/test_scene_graph.py tests/test_scene_graph_v1_roles.py
tests/test_scene_graph_pipeline.py tests/test_scene_graph_overlay_contract.py
tests/test_scene_graph_executor_overlays.py tests/test_scene_graph_timeline_overlay_freeze.py
tests/test_renderer_scenegraph_timeline_overlay_freeze.py tests/test_renderer_scenegraph.py
tests/test_renderer_motion.py tests/test_rights_scope.py tests/test_database.py
tests/test_discovery_referral.py tests/test_discovery_providers.py tests/test_ingest.py
tests/test_tactical_cards.py tests/test_summary.py tests/test_web_ui_approve_candidate.py`
→ **278 passed, 2 failed** (in 18.48s).

The 2 failures are environmental, not regressions:
- `test_scene_graph_pipeline.py::test_fetch_asset_infos_selects_rights_scope_json`
- `test_scene_graph_pipeline.py::test_fetch_asset_infos_old_registry_without_rights_scope_json`
Both assert `not (ROOT / "runtime").exists()`, but `runtime/` is pre-existing
gitignored app data at the repo root (subdirs dated 9/28–10/8, engine.db present).
Code path under test is read-only (`root / runtime / engine.db`, early-return if absent);
tests assume a pristine repo root without `runtime/`.

Not run: full repository test suite; final MP4 render / pixel-level visual QA
(owner constraint: no long render, no MP4 review). Visual QA remains `NEEDS_REVIEW`
pending owner eyeball of motion/video/narration sync on a rendered clip.

## Decisions added/changed

- Rights: `verified` is necessary but never sufficient; `is_usable_for(asset, purpose)` is the use-scoped gate. Deny-default for YouTube/unknown-source/license, expired/unclear expiry, and copyright exceptions (human review only, LLM cannot clear).
- LLM/planner boundary restored: model owns semantic `beat_intent` only (image_goal, focus_subject, evidence_type, emphasis_level); deterministic planner owns mode/layout/motion/transition/typography/color/coordinates.
- Scene Graph: fail-closed when `ACE_SCENE_GRAPH_RENDER=1` + missing graph; freeze overlays/tactical/media specs into graph; `graph_hash` = sha256 canonical JSON minus itself; renderer executes verbatim, no remap.
- QA semantics: 1 FAIL → FAIL; any NEEDS_REVIEW → NEEDS_REVIEW (not ready); PASS = ready. No false PASS from mere asset presence.

## Remaining work

1. Pixel-level visual QA / render inspection: owner eyeball a rendered short clip (motion, narration sync, aesthetic) — currently `NEEDS_REVIEW`.
2. Full repository test suite run (focused suite only was run).
3. Address integration-checkpoint remaining limits: no final MP4 reviewed; overlay paint/transition appearance not verified; `use_count`/`clip_limit` caller-counted (no shared DB counter); no UI scope entry yet.
4. Then commit/push only when explicitly requested.

## Next concrete action

Run full repository test suite (`python -m pytest tests -q`) and, if green,
arrange owner review of a rendered short-form clip for pixel-level visual QA.
Do not commit/push unless explicitly requested; do not touch `runtime/` or run
a long render.

## Session closeout format

Update this handoff with: verified commit/branch; completed work; work still in
progress; decisions added/changed; tests and render inspections performed;
known risks; next concrete action. Keep detailed rationale in the relevant
architecture/decision document instead of growing this file into a diary.

