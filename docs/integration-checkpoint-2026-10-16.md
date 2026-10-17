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
