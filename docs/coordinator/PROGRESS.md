# ACE Progress — auto-generated reference

> Generated 2026-10-19T13:28:12+00:00. Workers read STATE.json; humans read this. Refresh with `python tools/ace_state.py --write`.

Repo `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1` @ `main/bd9ae16`

## Tasks
- P0-port-1200: **PACKET_READY**
- R1-render-baseline: **NEEDS_REVIEW**
- R2-rights-gate: **REPORTED**
- R3-beauty-fix: **BLOCKED**
- R4-final-gate: **PACKET_READY**
- W1-rights-scope: **PACKET_READY**
- W2-discovery-board: **PACKET_READY**
- W3-scene-graph: **PACKET_READY**
- W4-render-qa: **PACKET_READY**

## Contracts
- c1-rights-scope v1.0 sha:6d51ad40
- c2-candidate-suitability v1.0 sha:82bbcd5d
- c3-beat-intent v1.0 sha:d2a2a1e0
- c4-scene-graph v1.0 sha:a01bcdb0
- c5-qa-finding v1.0 sha:9c8a6cca

## Recent renders (reference only)
- a1b2c3d4e5f6: mp4=['full-render.mp4']
- a58fdf5edca8: mp4=['full-render.mp4']
- 2556c12f9ba8: mp4=['full-render.mp4']
- 4a5ccf106f5b: mp4=['visual-benchmark-silent.mp4']
- 9787cc24a490: mp4=['template-preview.mp4']

## Dirty files
- A  .dockerignore
- M  .env.example
- M  .gitignore
- M  README.md
- A  apps/asset_library/auto_acquire.py
- M  apps/asset_library/database.py
- M  apps/asset_library/discovery.py
- M  apps/asset_library/entity_seed.py
- A  apps/asset_library/identity.py
- M  apps/asset_library/registry.py
- A  apps/asset_library/rights_scope.py
- A  apps/card_selector.py
- A  apps/content_score.py
- M  apps/content_workflow.py
- A  apps/distribution/__init__.py
- A  apps/distribution/adapters.py
- A  apps/distribution/models.py
- A  apps/distribution/routing.py
- A  apps/distribution/service.py
- A  apps/learning/__init__.py

## Handoff prose (from docs/ENGINE_STATE.md, coordinator-owned)

> # Engine state and next-session handoff
>
> Last verified: **2026-10-18**. This is a compact handoff, not a full history.
> Re-check Git and worktrees before acting because another OpenCode session may
> have progressed since this snapshot.
>
> ## Product goal
>
> Prove a dependable Soccer/Vietnamese content-production vertical slice for
> Allen Knows Ball. The near-term target is short form; long form follows on the
> stronger PC. Voice naturalness and publishing are not current proof gates.
> The larger portfolio business in `PROJECT_SPEC.md` remains the long-term
> north star, not the current implementation claim.
>
> ## Owner's current architecture constraints
>
> - Asset discovery is multi-source and multi-format. YouTube is source
>   discovery/linking only, never a video downloader or rights grant.
> - Rights scope is checked for each intended upload and remains separate from
>   visual suitability. The owner decides external asset saving/use; exceptions
>   require human review.
> - The LLM emits semantic beat intent, not concrete layout values.
> - A deterministic Visual Planner creates a versioned Scene Graph from intent,
>   suitable/approved assets, and the pinned Template Foundation.
> - The renderer consumes the graph. QA inspects rendered scenes and reports
>   uncertainty as `NEEDS_REVIEW`, not a false `PASS`.
> - Distinct visual grammars create story-fit variation while the Template
>   Foundation preserves channel identity.
>
> ## Verified repository snapshot
>
> - Repository: `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`
> - Branch/commit last checked: `main` / `bd9ae16` (`feat: add short-form render workflow and templates`), tracking `origin/main`.
> - At the time of this snapshot, `docs/audit-checkpoint-2026-10-08.md` was the only untracked change; no implementation changes from the user's active OpenCode multi-agent run were visible in this checkout.
> - `PROJECT_SPEC.md` describes a much broader autonomous business engine than the current Soccer video workflow. Keep those scopes distinct.
>
> ## Current implementation, at a glance
>
> - Present: local SQLite evidence/observation/belief foundations; soccer entity seeds; generic-looking asset registry/resource requirement seam; basic local workflow UI; Ollama script draft; local TTS preview gate; short/long template packages; Pillow + FFmpeg render path.
> - Partial: asset discovery and licensing metadata; human review; selected library still-image compositing; timeline and graphic modes; technical render report.
> - Not implemented as independent production layers: use-scoped rights decision, first-class video discovery/ingest/render, candidate suitability board, semantic-intent contract, deterministic Visual Planner, versioned Scene Graph, perception-based rendered-scene QA, durable end-to-end orchestration, platform distribution/publishing, analytics/economic outcomes, and learning/reallocation.
> - `apps/worker/` contains a minimal in-memory queue/demo, not a durable production job system.
> - The current runtime renderer/report must be re-read before relying on earlier docs; docs and implementation have drifted.
>
> ## Active work / coordination status
>
> Four workstreams (rights scope, discovery, Scene Graph/Planner, renderer/QA)
> have been implemented, integrated, and reviewed per
> `docs/integration-checkpoint-2026-10-16.md` (integration review update
> 2026-10-18). Contracts are frozen: rights scope (`docs/rights-scope-2026-10-16.md`),
> Scene Graph (`docs/scene-graph-contract.md`), LLM/planner boundary, and QA
> (`docs/renderer-qa-scene-graph.md`). No commit or push was performed (owner
> instruction). `stash@{0}` does not exist; all changes are staged/unstaged in
> the working tree on `main`/`bd9ae16`.
>
> ## Current implementation, at a glance
>
> - Present (foundations): local SQLite evidence/observation/belief; soccer entity seeds; asset registry/provenance/rights; local UI; Ollama script draft; TTS preview gate; short/long template packages; Pillow + FFmpeg render path.
> - New/integrated (workstreams, uncommitted):
>   - `apps/asset_library/rights_scope.py` — `is_usable_for(asset, purpose)`, use-scoped rights, deny-default, human-review exceptions.
>   - `apps/scene_graph/` — `intent.py`, `builder.py`, `schema.py`, `executor.py`, `pipeline.py`; deterministic Scene Graph v1, `graph_hash`, fail-closed validate.
>   - `apps/card_selector.py`, `apps/video_renderer.py` (Scene Graph path, flag-gated `ACE_SCENE_GRAPH_RENDER`), `apps/measurement/render_qa.py`.
>   - `apps/worker/` (persisted queue/run state), `apps/distribution/`, `apps/learning/`, `apps/measurement/`, `apps/llm.py`, `apps/orchestrator/`.
>   - Many `studio_templates/*.json` (pack 12.0.0) + new `pack-drop/`, `soundpacks/`, `assets/`, `media/`, `skills/`, docs.
> - Renderer reads Scene Graph nodes verbatim; no silent legacy fallback when flag on. Rights gate (`is_usable_for`) blocks attach when purpose ineligible. QA returns `PASS`/`FAIL`/`NEEDS_REVIEW` with evidence; `ready == (verdict == PASS)`.
> - `video_renderer.py` modified unstaged; old `template_foundation/0.x-*` dirs deleted unstaged (superseded by pack 12.0.0). No `runtime/` writes by tests/code path under review (`runtime/` is pre-existing gitignored app data).
>
> ## Tests run
>
> Focused integration suite (per integration-checkpoint §7) run 2026-10-18:
> `tests/test_card_selector.py tests/test_card_selector_intent.py
> tests/test_script_decomposition.py tests/test_workflow_end_to_end.py
> tests/test_scene_graph.py tests/test_scene_graph_v1_roles.py
> tests/test_scene_graph_pipeline.py tests/test_scene_graph_overlay_contract.py
> tests/test_scene_graph_executor_overlays.py tests/test_scene_graph_timeline_overlay_freeze.py
> tests/test_renderer_scenegraph_timeline_overlay_freeze.py tests/test_renderer_scenegraph.py
> tests/test_renderer_motion.py tests/test_rights_scope.py tests/test_database.py
> tests/test_discovery_referral.py tests/test_discovery_providers.py tests/test_ingest.py
> tests/test_tactical_cards.py tests/test_summary.py tests/test_web_ui_approve_candidate.py`
> → **278 passed, 2 failed** (in 18.48s).
>
> The 2 failures are environmental, not regressions:
> - `test_scene_graph_pipeline.py::test_fetch_asset_infos_selects_rights_scope_json`
> - `test_scene_graph_pipeline.py::test_fetch_asset_infos_old_registry_without_rights_scope_json`
> Both assert `not (ROOT / "runtime").exists()`, but `runtime/` is pre-existing
> gitignored app data at the repo root (subdirs dated 9/28–10/8, engine.db present).
> Code path under test is read-only (`root / runtime / engine.db`, early-return if absent);
> tests assume a pristine repo root without `runtime/`.
>
> Not run: full repository test suite; final MP4 render / pixel-level visual QA
> (owner constraint: no long render, no MP4 review). Visual QA remains `NEEDS_REVIEW`
> pending owner eyeball of motion/video/narration sync on a rendered clip.
>
> ## Decisions added/changed
>
> - Rights: `verified` is necessary but never sufficient; `is_usable_for(asset, purpose)` is the use-scoped gate. Deny-default for YouTube/unknown-source/license, expired/unclear expiry, and copyright exceptions (human review only, LLM cannot clear).
> - LLM/planner boundary restored: model owns semantic `beat_intent` only (image_goal, focus_subject, evidence_type, emphasis_level); deterministic planner owns mode/layout/motion/transition/typography/color/coordinates.
> - Scene Graph: fail-closed when `ACE_SCENE_GRAPH_RENDER=1` + missing graph; freeze overlays/tactical/media specs into graph; `graph_hash` = sha256 canonical JSON minus itself; renderer executes verbatim, no remap.
> - QA semantics: 1 FAIL → FAIL; any NEEDS_REVIEW → NEEDS_REVIEW (not ready); PASS = ready. No false PASS from mere asset presence.
>
> ## Remaining work
>
> 1. Pixel-level visual QA / render inspection: owner eyeball a rendered short clip (motion, narration sync, aesthetic) — currently `NEEDS_REVIEW`.
> 2. Full repository test suite run (focused suite only was run).
> 3. Address integration-checkpoint remaining limits: no final MP4 reviewed; overlay paint/transition appearance not verified; `use_count`/`clip_limit` caller-counted (no shared DB counter); no UI scope entry yet.
> 4. Then commit/push only when explicitly requested.
>
> ## Next concrete action
>
> Run full repository test suite (`python -m pytest tests -q`) and, if green,
> arrange owner review of a rendered short-form clip for pixel-level visual QA.
> Do not commit/push unless explicitly requested; do not touch `runtime/` or run
> a long render.
>
> ## Session closeout format
>
> Update this handoff with: verified commit/branch; completed work; work still in
> progress; decisions added/changed; tests and render inspections performed;
> known risks; next concrete action. Keep detailed rationale in the relevant
> architecture/decision document instead of growing this file into a diary.
>
