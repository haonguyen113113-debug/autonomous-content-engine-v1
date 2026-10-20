# Integration checkpoint — 2026-10-16 (updated 2026-10-17)

## Purpose

This file is the coordination reference for the next integration pass after
the four parallel workstreams (rights, discovery, planner/Scene Graph, and
renderer/QA). It records the repository state and the decisions that the owner
confirmed. It is not a release approval or permission to commit/push.

This canonical coordination note is kept on `main`. The repository snapshot
below is historical: it was taken on `feature/template-nova` and was merged
into `main` on 2026-10-17 as commit `14a62eb`.

## Post-merge audit — 2026-10-17

- The Scene Graph schema, builder, executor, renderer/QA changes, Rights
  scope, discovery, and related tests were committed and fast-forwarded to
  `main` in `14a62eb` (`feat: integrate rights scope and scene graph workflow`).
- The integration commit was not independently retested during the merge
  operation. Session 2 reported 87 focused tests passing; retain that as an
  agent-reported result until rerun.
- The production path still needs a coordinator to build and attach
  `draft.scene_graphs` before `render_full_run`; the renderer currently
  validates graphs when present and refuses legacy fallback when explicitly
  enabled, but no production caller of `build_clip_graphs()` was found.
- `content_workflow.py` still requests `visual_mode` and
  `timeline_events` from the LLM even though its prompt also says the LLM
  owns semantic `beat_intent` only. Reconcile the prompt/parser boundary so
  deterministic planning owns composition choices.
- Rights follow-up remains: `rights_reviewed=True` can create a broad scope;
  `purpose=None` preserves legacy asset selection; and the verified-asset
  review endpoint returns before applying supplied `grant_fields`. Owner
  authorization to auto-save qualifying assets does not imply broad usage
  rights. Separate storage permission from usage scope.
- At the time of this post-merge note, `main` was still local; it has since
  been pushed and `origin/main` is synchronized. Preserve `stash@{0}`. The
  checkpoint file itself remains a coordination document, not a runtime
  artifact.

## Repository snapshot

- Repository: `autonomous-content-engine-v1`
- Branch: `feature/template-nova`
- HEAD at checkpoint: `ecdba9c7da8ea603035a01ffb7188cb4dfc8a54a`
- The four workstreams are present as a mixture of staged, unstaged, and
  untracked changes. `stash@{0}` remains as a recovery copy and must not be
  dropped or applied wholesale. Compare it file by file before resolving any
  overlap.
- `docs/audit-checkpoint-2026-10-08.md` is absent in this checkout. The
  relevant references are `docs/build-audit-protocol.md`,
  `docs/template-build-manual.md` §8, `docs/workflow-probe-2026-10-10.md`,
  and `docs/voice-baseline.md`.

## Owner decisions and constraints

- The engine is authorized to automatically save qualifying assets to keep
  the workflow smooth. This is a current operating decision; reassess the
  policy when the system scales. Continue enforcing rights and qualification
  gates, retain provenance/audit details, and reject unclear or denied rights.
- The LLM proposes beat meaning only: image goal, focal subject, evidence
  type, and emphasis. Deterministic planner/builder owns mode, layout, motion,
  transition, typography, color, and coordinates.
- Renderer executes a frozen Scene Graph. It must not silently switch to a
  legacy composition path when Scene Graph rendering is explicitly enabled.
- QA must report evidence and must not label a render ready when required
  checks fail or need human review.
- Do not commit or push. Do not run a long render. Do not read, write, or
  modify anything under `runtime/` during this integration pass.
- Keep all existing worktree changes and `stash@{0}` recoverable. Do not
  reset, clean, stash-pop, or drop the stash.

## Integration gaps to close

### 1. Persist rights scope end to end

- Add rights scope schema as the next database migration and ensure ordinary
  database initialization applies it idempotently.
- On candidate approval and later human rights review, persist the explicit
  rights scope that was actually reviewed; do not infer permission merely
  from `rights_state = verified`.
- Ensure the UI captures or clearly presents the scope being approved. Keep
  unknown source/license, YouTube referral, and copyright-exception cases
  denied or routed to human review.
- Pass the actual upload purpose into planner/discovery checks; if purpose is
  absent, do not claim scope eligibility.

### 2. Restore the LLM/planner boundary

- Change script-generation prompts and parsing so the model owns semantic
  `beat_intent` only (image goal, focal subject, evidence type, emphasis).
- Do not ask the model to select `visual_mode`, starter/layout, motion,
  transition, effect, typography, color, or coordinates. Preserve evidence-
  backed factual content and narration fields.
- Let deterministic planning derive the composition from beat intent, approved
  assets, and the locked template. Forward exact search terms and purpose to
  discovery where available.

### 3. Make Scene Graph execution fail closed and complete

- When `ACE_SCENE_GRAPH_RENDER=1`, missing graphs must raise a clear error;
  they must never silently select the legacy renderer. Keep legacy behavior
  only when the flag is off.
- Freeze every rendered overlay/caption/media caption and tactical diagram
  specification (players, vectors, timing) into the graph. The executor must
  not call storyboard fallback specs or choose composition from beat index.
- Keep graph validation/hash checks before rendering, and preserve verbatim
  execution of frozen motion/transition decisions.

### 4. Make QA verdict actionable

- Preserve `PASS` / `FAIL` / `NEEDS_REVIEW` and attach criterion-level evidence.
- A final/readiness action must be blocked on `FAIL` and must not be marked
  ready on `NEEDS_REVIEW`. If preview rendering is allowed for inspection,
  label it explicitly as non-ready.
- Make clear which checks inspect intermediate scene images and which inspect
  the final MP4. Do not claim final-video timing/motion QA from still images.
- Tactical vectors that have not been visually verified remain
  `NEEDS_REVIEW`.

## Suggested implementation order

1. Rights persistence and approval-scope path.
2. LLM prompt/parser boundary and purpose/exact-term propagation.
3. Fail-closed Scene Graph path and frozen tactical/overlay inputs.
4. QA readiness gate and report semantics.
5. Run focused unit tests for affected modules, then the full test suite if
   practical. Do not run a long render or touch `runtime/`. Report commands,
   results, and any unverified claims.

## Completion report required

For each integration gap, report files changed, behavior before/after, tests
run and results, remaining limitations, and whether any overlap with
`stash@{0}` remains unresolved. Keep all changes uncommitted and unpushed.

## Integration review update — 2026-10-18 (local, uncommitted)

### Repository state

- Branch: `main`; HEAD: `f6f841e182d58be0a385b48c022196421122e86a`.
- All integration work below is unstaged/uncommitted. No commit or push was
  performed.
- `stash@{0}` remains `WIP on feature/template-nova: ecdba9c`; it was not
  applied, popped, dropped, or otherwise changed.
- `runtime/` was not read, written, or modified. No long render or MP4 visual
  review was performed.
- `git diff --check` is clean.

### Integrated paths reviewed

1. **Rights and asset selection:** explicit `grant_fields` are persisted by
   discovery/approval routes; missing grants remain deny-default. The shared
   upload-purpose normalizer is used by card selection and rendering. Missing
   purpose does not clear or attach a library asset. Scene Graph asset
   approval comes from persisted `rights_scope_json`, not `verified` alone.
2. **LLM/planner boundary:** script generation retains semantic
   `beat_intent`; deterministic selection uses it only as a small advisory
   scoring tie-break. The model does not choose layout, coordinates, font,
   color, or motion. `LAYOUT_MODES` is separated from `VISUAL_MODES` so
   template layouts do not mutate the shared visual-mode vocabulary.
3. **Scene Graph production path:** `render_full_run` builds and attaches one
   validated graph per beat when `ACE_SCENE_GRAPH_RENDER=1`. Missing graphs
   fail closed; flag-off remains the legacy path. Rights references and
   overlays are frozen into the graph and covered by `graph_hash`.
4. **Timeline overlays:** `build_clip_graphs` converts supported absolute
   caption/lower-third event times into beat-relative overlay times, preserves
   explicit overlays, deduplicates matching timeline events, and rejects
   malformed supported events. Other timeline event types are not converted
   to overlays. The renderer executes only frozen graph overlays in Scene
   Graph mode.
5. **Overlay contract and QA:** schema accepts only the documented overlay
   keys and role presets (`lower_third/name_tag`, `caption/hook`); unsupported
   styling/layout keys and role/type mismatches fail validation. QA does not
   call a structurally valid declared overlay visually verified: it remains
   `NEEDS_REVIEW` pending final-video inspection.
6. **Short-form opening hook card:** short-form no longer renders the C-01
   opening brand scene. Beat-0 opens with the new C-11 opening hook card
   (background `short-opening.jpg`, single `hook_text` slot) showing the
   approved hook from script/graphic data. If no hook is provided, no text is
   fabricated (fail-closed). C-10 ending card is unchanged for short-form;
   long-form opening/ending (LC-14) unchanged. `C-11` added to
   `card_registry.py`, `graphic-templates.json`, `build_starters.py`, and
   `card_selector.STARTERS_SHORT` (`hook_card` → `C-11`). `STARTERS_SHORT`
   mapping updated; `C-03` remains built but unreferenced by `STARTERS_SHORT`.
   `test_card_registry.py` count updated 89→90.

### Verification performed in this review

Focused combined suite, run after correcting the timeline-overlay test
fixture to call the production `build_clip_graphs` path:

```text
python -m pytest tests/test_card_selector.py tests/test_card_selector_intent.py tests/test_script_decomposition.py tests/test_workflow_end_to_end.py tests/test_scene_graph.py tests/test_scene_graph_v1_roles.py tests/test_scene_graph_pipeline.py tests/test_scene_graph_overlay_contract.py tests/test_scene_graph_executor_overlays.py tests/test_scene_graph_timeline_overlay_freeze.py tests/test_renderer_scenegraph_timeline_overlay_freeze.py tests/test_renderer_scenegraph.py tests/test_renderer_motion.py tests/test_rights_scope.py tests/test_database.py tests/test_discovery_referral.py tests/test_discovery_providers.py tests/test_ingest.py tests/test_tactical_cards.py tests/test_summary.py tests/test_web_ui_approve_candidate.py -q
```

Result: **280 passed in 15.81s**. This is a focused integration suite, not a
full repository test run. The earlier six failures in the separate timeline
bridge report came from a test helper that passed absolute timeline-shaped
data as explicit overlays instead of exercising `build_clip_graphs`; the
production-path tests now cover conversion, filtering, deduplication,
timebase, and fail-closed validation.

#### Short-render smoke test (MP4, 2026-10-18)

Added `tests/test_scene_graph_render_smoke.py`: short-form full render on the
Scene Graph production path (`ACE_SCENE_GRAPH_RENDER=1`), self-contained in
`pytest tmp_path` (no repo `runtime/`, no user voice/library/assets).

```text
python -m pytest tests/test_scene_graph_render_smoke.py -q
```

The handoff's first test version did not actually assert FPS, compare frames
within one beat, or inspect the rendered overlay window. Those assertions were
added during coordinator review and the smoke test was rerun.

Result: **1 passed in 52.06s**. Verified:
- MP4 really produced by FFmpeg (`libx264`, `yuv420p`, `1080×1920@30`) and
  confirmed by ffprobe (video stream `h264`, width/height, average FPS 30
  within 0.1, duration ≈ 20s within ±1s tolerance).
- Decoded frames at t=1.0 and t=8.0 within the same beat differ at the pixel
  level; this checks motion within a scene rather than merely a scene cut.
- Pixel counts in fixed overlay regions increase while the first caption and
  second-beat lower-third are active, then decrease after their declared
  windows. This verifies representative in/out overlay paint in the encoded
  MP4; it does not replace visual review of placement/readability.
- `run["draft"]["scene_graphs"]` attached: 2 graphs, overlays clip-relative
  within beat duration, `provenance.graph_hash` 64-hex.
- QA does not over-claim: `scene_graph_qa.verdict == NEEDS_REVIEW`,
  `ready == False`, criterion `"Overlay rendered" == NEEDS_REVIEW`; QA itself
  still requires review evidence and does not infer a PASS from declarations.
- `render_scene_png` beat-0 still renders non-empty PNG.

The smoke test exercises the real production path end-to-end
(`render_full_run → apply_card_plan → build_run_scene_graphs → _render`
FFmpeg → ffprobe). The smoke test checks overlay presence in representative
time windows and motion between two same-beat frames. Fine placement,
readability, transition appearance, narration sync, and aesthetic still need
owner review on the rendered clip; QA keeps those at `NEEDS_REVIEW`.

### Remaining limits / owner review

- Final MP4 was rendered (smoke test, 20s short clip) but not visually
  reviewed. Automated sample-frame checks establish changing pixels within a
  beat and overlay paint during/outside representative windows; actual
  placement/readability, transition quality, narration synchronization, and
  overall aesthetic still need an owner review.
- The full test suite was not run; only the focused integration command above
  plus the smoke test were run.
- Strict overlay validation is a compatibility tightening: legacy graphs
  without an `overlays` field remain accepted, while old graphs that include
  non-preset roles or extra per-overlay styling/layout keys will now be
  rejected and must be rebuilt under the current contract.
- The active change set (uncommitted) contains 1 modified tracked checkpoint
  and 1 new untracked test file (`tests/test_scene_graph_render_smoke.py`);
  the integration work (rights scope, Scene Graph production path, planner
  boundary, timeline overlays) was committed in `edd522e`. No overlap with
  `stash@{0}` was applied or resolved wholesale. Keep the stash intact until
  any future file-by-file comparison is explicitly needed.

## Current continuation checkpoint — 2026-10-18 (local, uncommitted)

This addendum supersedes earlier short-render smoke results and any statement
that all current integration checks pass. Earlier sections remain historical.

### Repository state

- Branch: `main`; HEAD: `edd522edb4cb3b1f8173897b4413a860169d4fae`.
- Current worktree contains uncommitted changes from the previous integration
  rounds, including C-11, Scene Graph overlay suppression, renderer changes,
  tests, and docs. Preserve all of them; do not reset/clean/revert/stash.
- `stash@{0}` remains `WIP on feature/template-nova: ecdba9c`; do not apply,
  pop, or drop it.
- No commit or push has been made. Do not read/write/modify the repository's
  `runtime/` directory.

### Completed since the preceding checkpoint

1. **Short opening hook card C-11:** registered in `card_registry.py`,
   `graphic-templates.json`, `build_starters.py`, and
   `card_selector.STARTERS_SHORT`. Short-form does not render C-01 as a separate
   opening; its first beat uses the approved hook card and C-10 remains the
   short ending. Missing `graphic_data.hook_text` stays empty; the selector
   does not infer it from narration.
2. **C-11 proof/layout correction:** `C-11.short.json` uses the existing
   `short-opening.jpg` artwork. Its single text slot is positioned above the
   central mark (`x=90`, `y=310`, `width=900`, `height=250`) with base
   `fontSize=72`, so the existing shrink-to-fit path can fit hooks up to the
   selector's eight-word cap. The proof image is
   `template_foundation/templates/allen-knows-ball/12.0.0/previews/short-c-11-proof.png`.
   Manual still renders confirmed 1080x1920 output and readable, non-clipped
   text for a representative eight-word Vietnamese hook. This is not an MP4
   review.
3. **Selector wording:** `_normalize_hook_text` now normalizes/caps only the
   already supplied `graphic_data.hook_text`; it does not derive hook copy from
   narration. The reason/warning strings describe that source accurately.
   The selector session reported 43 focused tests passing.

### Latest verification and unresolved failure

The latest combined command was:

```text
python -m pytest tests/test_card_selector.py tests/test_card_selector_intent.py tests/test_card_registry.py tests/test_renderer_scenegraph.py tests/test_scene_graph_executor_overlays.py tests/test_renderer_scenegraph_timeline_overlay_freeze.py tests/test_scene_graph_render_smoke.py -q
```

Result: **103 passed, 1 failed in 94.35s**. The sole failure is
`tests/test_scene_graph_render_smoke.py::test_scene_graph_short_render_smoke`:
the decoded RGB frames at 3.0s and 8.0s within the same beat are identical.
The test also verified the encoded H.264 1080x1920@30 MP4 path before reaching
that failing temporal assertion. Treat the prior `1 passed` smoke result above
as superseded; the current state has a confirmed same-beat motion failure.

Additional checks after the C-11 layout correction:

- `python -m pytest tests/test_card_registry.py -q` — **5 passed**.
- `python apps/studio_templates/check_starters.py` — **90 files, 0 errors**.
- Manual `render_starter_scene` output for a Vietnamese eight-word hook —
  **1080x1920**, visual still checked; not an MP4 render.

### Active follow-up workstreams

- **Renderer motion:** investigate and fix the same-beat identical-frame smoke
  failure. Do not weaken the assertion without evidence; verify actual frame
  pixel differences and preserve the authored card safe area. Ownership:
  `apps/video_renderer.py` and `tests/test_scene_graph_render_smoke.py`.
- **QA truthfulness audit (read-only):** inspect whether motion/structure QA can
  claim PASS based on configured filters rather than observed rendered output;
  also audit fail-closed overlay behavior and C-11 role/order checks. Do not
  edit files while the renderer workstream runs.

Both tasks were handed to separate OpenCode sessions. Their completion has not
yet been confirmed. Keep the worktree uncommitted and rerun the focused
integration command after the motion fix.

## Architecture direction update — Hermes orchestration (2026-10-19)

### Decision

- Hermes is the outer daily coordinator for story discovery, relevance
  assessment, evidence gathering, structured script drafting, Engine job
  submission, monitoring, and completion reporting.
- The Engine's target role is video production: validate the handoff, enforce
  asset qualification/rights/provenance/purpose gates, plan deterministically
  from the fixed template and Scene Graph, generate voice, render, run QA, and
  return the artifact plus evidence-backed status.
- The owner reviews and publishes. The Engine/Hermes flow must not publish or
  receive publishing credentials.
- Research and script generation do not need to be duplicated inside the
  Engine's target Hermes path. Existing standalone drafting remains during
  migration, but is not the target orchestrator.
- Asset auto-save for qualifying candidates remains authorized for workflow
  smoothness; this does not bypass rights scope, provenance, qualification, or
  use-purpose checks.

### Integration work still required

- Freeze a versioned JSON Schema for topic, research sources and claim/evidence
  references, short/long content type, ordered beats, narration, timing,
  semantic `beat_intent`, supported `graphic_data`, asset requests, and upload
  purpose. The model must not control layout, coordinates, typography, color,
  motion, or transitions.
- Implement a dedicated authenticated production-job submit/status contract
  and connect it to the existing durable local queue. The current
  `/api/content/batch-runs` interface is draft-oriented and is not yet the
  Hermes production contract. Submission must be idempotent and validate the
  whole payload before enqueueing.
- Return stable job IDs, explicit lifecycle states, artifact location, QA
  verdict/evidence, warnings, and actionable errors. `FAIL` and
  `NEEDS_REVIEW` must never be reported as ready for owner review.
- Add completion webhooks only after polling/status behavior is stable.
- Keep Engine and queue worker as local Python processes on the production PC.
  Docker/Compose support has been removed from the repository; this does not
  remove the durable queue or local worker.

### Rollout gates and known blocker

1. Freeze the handoff schema and API contract.
2. Implement and validate submit/status against the existing queue.
3. Prove one fixture job through asset gates, render, and QA.
4. Connect Hermes in draft/render/report mode; owner retains review/publishing.
5. Enable scheduled production only after the same-beat motion smoke failure
   below is rerun and confirmed fixed, and the owner has visually reviewed the
   resulting video.

The latest verified checkpoint still reports identical decoded frames at 3s
and 8s within one beat. The completion status of the two previously assigned
OpenCode sessions has not been confirmed in this checkout; treat the motion
issue as open. Do not claim the Hermes API or schema has been implemented.

### Files updated for this direction

- `docs/hermes-engine-integration.md` records the responsibility boundary,
  contract requirements, job lifecycle, runtime, and rollout gates.
- `README.md`, `PROJECT_SPEC.md`, and `docs/machine-setup.md` distinguish the
  target Hermes workflow from the existing standalone drafting path.
- Docker artifacts are deleted; queue processing remains available through
  `python -m apps.worker.main`.
- The current worktree also contains the C-11/template and renderer/QA changes
  listed in the repository status; preserve them with this documentation work.
  No new tests were run for this architecture/documentation update. The latest
  recorded focused result remains 103 passed / 1 failed on the same-beat
  motion assertion. Preserve `stash@{0}`.
