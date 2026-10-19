# Repository gap audit and build map — 2026-10-16

## Purpose and scope

This is a repository-level architecture review against `PROJECT_SPEC.md`, the
owner's audit checkpoint, and the current target of proving the Allen Knows
Ball Soccer workflow. It records observed implementation boundaries and
proposed work order. It does not claim the full long-term portfolio business
engine is built, and it is not a replacement for runtime/render inspection.

The audit was read-only. No tests or renders were run in this review.

## Executive assessment

The repo has useful foundations and a working local production slice, but it
does not yet have one connected, autonomous engine. Its strongest areas are
local evidence/asset foundations, versioned visual packages, a basic content
draft flow, and FFmpeg output. Its largest gaps are the intended-use rights
model, multi-format media path, independent deterministic visual planning,
honest perceptual QA, and durable orchestration. Most of the broader business
loops in `PROJECT_SPEC.md`—opportunity portfolio, channels, publishing,
economics, and learning—are absent.

The right distinction is:

- **Complete the architecture/framework:** define module boundaries, contracts,
  state transitions, failure/review semantics, and acceptance checks across
  every target layer.
- **Implement in vertical slices:** first make the Soccer video workflow
  dependable. Do not implement the entire portfolio business before validating
  that slice with real runs.

## Current-to-target map

| Layer | Current repo evidence | Gap / target |
|---|---|---|
| Product/domain boundary | `PROJECT_SPEC.md` states generic core plus domain packs; `data/entities/` is soccer seed data. | The active content prompt, templates, UI, and parts of workflow remain Allen/Soccer-specific. Define the core/domain interface before adding categories; do not generalize prematurely. |
| Portfolio, audience, theme, channel strategy | Channel identity is represented in Template Foundation files. | No strategic category portfolio, audience model, opportunity scoring loop, theme/channel lifecycle, or allocation workflow. Long-term scope only. |
| Research and opportunity discovery | Workflow accepts a topic and optional pasted evidence; script prompt asks not to invent claims. | No autonomous source research pipeline, claim/source graph, freshness/conflict resolution for script facts, or evidence retrieval quality gate connected to content generation. |
| Script and beat plan | `apps/content_workflow.py` calls local Ollama and stores a run draft; deterministic timeline normalization exists. | LLM prompt currently asks for detailed timeline items/effects and the data remains embedded in script segments. Separate semantic visual intent from composition. Persist model/prompt/schema versions and validation results. |
| Asset inventory/evidence | `apps/asset_library/` includes registry, provenance/source revisions, entities, observations, beliefs, and requirement evaluation. | Resource suitability is shallow: type/entity/purpose/context checks; limited technical metadata for video; no robust ranking for exact match, freshness, illustrative action, shot variety, or beat coverage. |
| Discovery/candidate board | `discovery.py` searches Openverse and Commons images; UI presents license/creator/credit and save choices. | Discovery/download path requires `image`; there is no first-class video provider/preview/ingest path, stock/licensed adapter contract, YouTube reference-only adapter, or ranked candidate board separating provenance, suitability, and use eligibility. |
| Rights and intended use | Asset rows store `rights_state`, `license_type`, source and metadata. | No structured per-upload scope (platform, territory, commercial use, term, edits, attribution, clip limits). UI's review action marks `verified`; run workflow uses `rights_state="verified"`; renderer gates on verified/active. Replace this broad boolean gate with use-specific eligibility plus explicit human-review states. |
| Template Foundation | Versioned short/long packages, design tokens, visual modes, graphic templates, previews, and runtime package resolution exist. | All packages are draft. Define release/approval acceptance and ensure actual renderer reads authored package contracts instead of duplicating design decisions. Keep stable identity separate from story variation. |
| Visual planning / Scene Graph | Beat timeline events and `visual_mode` exist on script segments. | No independent semantic-intent schema or Scene Graph artifact. Build deterministic planner with versioned node roles, asset references, timing, transitions, fallback and provenance. Same inputs/version must yield same graph. |
| Renderer | `apps/video_renderer.py` uses Pillow for scene images and FFmpeg for compositing/timing; selected library images can be included. | Large module owns scene selection, composition and rendering. It resolves only verified active **images**; library video is not rendered. Refactor incrementally into graph consumer; preserve Pillow for static surfaces if useful. Implement authored transitions/motion from graph and avoid silently substituting unsupported visual modes. |
| QA / perception | Render report checks container, aspect ratio, duration/audio and contains fixed/manual status entries. | Several aesthetic/visual checks are asserted from intended paths rather than inspecting rendered frames. No scene-to-narration alignment QA, clipping/overlap detection, density assessment, false-pass prevention, or visual evidence in report. Use deterministic checks + VLM review + calibrated owner rubric; uncertainty => `NEEDS_REVIEW`. |
| Voice/audio | Local TTS preview exists behind script approval and owner audit. | Full voice naturalness remains owner-rated; timing is a single continuous audio track with no demonstrated phrase-level alignment. Not a blocker for the present visual architecture review. |
| Orchestration/reliability | `run_content_agent` performs synchronous draft/evaluation and writes a local run JSON. | `apps/worker/` is an in-memory demonstration, not durable jobs. No unified state machine, retries/backoff across workflow steps, cancellation, idempotent run recovery, long-task progress, or auditable per-step artifacts. |
| UI/review | Local UI exposes library, templates, workflow, script and voice gates, preview and report. | No candidate board with use scope/visual ranking; no Scene Graph inspection; no temporal QA findings with frame/time evidence; no end-to-end run progress/recovery view. |
| Distribution/publishing | No production platform adapters found in current `apps/` tree. | Channel routing, platform-native adaptation, scheduling, authorization lifecycle, publishing, retry/reconciliation, and publication record are absent. Long-term scope. |
| Measurement/economics/learning | Evidence subsystem resolves beliefs and detects changes for source observations. | No connected audience analytics, conversion attribution, platform earnings/payout verification, content outcome model, experiments, or allocation learning. Do not conflate evidence-belief infrastructure with business learning loop. |
| Portability/operations | `.env.example`, runtime separation, and `docs/transferable-runtime.md` support local setup. | Documentation drift exists: runtime guide says selected Asset Library football media is not yet placed, while current renderer contains selected-image compositing. Verify guide and reports against actual behavior during each release. No durable workflow state migration/backup path is documented. |
| Validation | Tests cover asset registry, evidence, entities, perception and migrations. | No tests found for content workflow, UI review transitions, renderer output/QA, rights scope, candidate ranking, Scene Graph, or publish/learning flows. Current test inventory mirrors the foundations, not the production vertical slice. |

## High-priority design risks

1. **Rights boolean can over-authorize.** `rights_state="verified"` is used as
   a generic eligibility filter, while user review does not record scope.
2. **Video request is accepted but not fulfilled.** Script can emit video asset
   needs, but web search only executes for image requests; external save and
   renderer resolution also reject video.
3. **Story/layout boundary is blurred.** The model emits timeline event kinds,
   visual modes and effects, and `video_renderer.py` chooses/render layouts.
4. **QA can overstate certainty.** The quality report marks some subjective
   visual criteria `PASS` without a visual inspection result tied to frames.
5. **The north star and current MVP can be confused.** `PROJECT_SPEC.md` is a
   business-portfolio specification; README milestone describes a local video
   workflow. A staged roadmap must make their relationship explicit.
6. **Operational execution is not yet autonomous.** Synchronous workflow plus
   demo in-memory worker cannot support reliable multi-minute/multi-step runs.

## Recommended implementation order

### Stage 0 — Contracts and project continuity

- Maintain root `AGENTS.md` and `docs/ENGINE_STATE.md` as session start memory.
- Freeze shared contracts for upload objective, rights evaluation, candidate
  suitability, semantic beat intent, Scene Graph and QA findings.
- Record schema versions, ownership boundaries and fail-closed/review states.

### Stage 1 — Rights-aware candidate workflow

- Model upload objective and rights scope explicitly.
- Separate discovery candidate, saved library asset, suitability score, and
  rights eligibility result.
- Add candidate board and YouTube reference-only results.
- Add still/video provider adapters and technical metadata, starting with
  sources that can be used without unapproved spend.
- Block renderer selection unless the specific intended use is eligible and
  owner-approved as required.

### Stage 2 — Visual planning contract

- Define validated semantic beat-intent and Scene Graph schemas.
- Implement a deterministic Visual Planner that consumes intent, suitable
  assets, and a pinned template package.
- Record planner/template/asset/schema versions and explain fallback choices.
- Add contract and determinism tests before broad renderer work.

### Stage 3 — Scene Graph rendering vertical slice

- Make the renderer consume graph nodes and treat composition as upstream
  data. Keep rendering primitives replaceable; Pillow is allowed for static
  layers.
- Support approved image and video media with crop, safe-area, duration,
  motion, source credit and transition behavior.
- Produce short-form review output first; test long-form later on stronger PC.

### Stage 4 — Honest multi-layer QA

- Structural QA: stream, size, duration, black/frozen intervals, audio presence.
- Visual QA: rendered frame sampling/contact sheets, text bounds/OCR, overlap,
  contrast, density, scene variation and source display.
- Semantic/temporal QA: beat ↔ narration ↔ asset/evidence coherence, event
  timing and transitions. Use a video-capable model with timestamped findings,
  but calibrate against owner audit examples and never treat its score as proof.
- Report findings with timestamp/frame evidence, severity, confidence and
  `PASS`/`FAIL`/`PARTIAL`/`NEEDS_REVIEW` state.

### Stage 5 — Durable workflow operations

- Replace/demo-integrate in-memory worker with persisted job/run state,
  idempotency, retry/backoff, cancellation, progress and resumability.
- Ensure every step has input/output artifact, version and failure reason.

### Stage 6 — Prove the Soccer channel loop

- Run repeated short-form workflows with owner-approved assets and audit each
  rendered result against a stable aesthetic/narrative rubric.
- Improve the layer responsible for each defect; do not patch around the
  Scene Graph in renderer code.
- Exit this stage only when script, candidate selection, rights gate, render,
  and QA reliably meet the agreed basic quality bar.

### Later expansion — distribution and business learning

After the production slice is proven, add channel routing/platform adapters,
publishing and reconciliation, outcomes/payout truth, experiments and portfolio
reallocation. These remain requirements in `PROJECT_SPEC.md`, not current MVP
claims.

## Audit method and limitations

This pass inspected repository files and architecture paths, not a fresh local
UI session or rendered MP4. It did not run tests. Status and references should
be refreshed after the current Muse/OpenCode work lands. A future audit pass
should inspect the actual candidate board, Scene Graph artifact, render report,
and timestamped frames for a completed short-form run.

