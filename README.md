# Autonomous Content Engine v1

A portable, local-first video production engine for Allen Knows Ball. The
target workflow uses Hermes for scheduled story discovery, evidence gathering,
and structured script drafting; the Engine validates the handoff, resolves
eligible media, applies its template and Scene Graph, generates voice, renders,
and returns QA results for owner review. The owner publishes manually.

## Current progress

- The local Engine workflow includes the asset library, short/long template
  foundations, voice/render stages, Scene Graph execution, and QA reporting.
- The target Hermes integration is architecture only: its versioned input
  schema and authenticated production-job API have not been implemented.
- Current uncommitted template/renderer work adds the C-11 short opening hook,
  keeps text inside authored template slots, and makes QA fail closed for
  unbound free-standing copy. This change set has not been verified by a new
  test run.
- Latest recorded focused run: **103 passed, 1 failed**. The failing
  `test_scene_graph_short_render_smoke` assertion found identical frames at 3s
  and 8s within one beat. Treat same-beat motion as unresolved until the smoke
  test passes on the current code.
- Docker/Compose support has been removed from the working tree. The durable
  queue remains and its worker runs locally with Python.

## How it works

```
Hermes: daily discovery → evidence-backed structured script
  → Engine: validate → eligible assets → template/Scene Graph → TTS → render + QA
  → Hermes reports result → owner reviews and publishes
```

- **Standalone local drafting path:** scripts can still be generated beat by
  beat (6 short / 8–9 long) with per-beat validation, retry, and deterministic
  outline fallback. Failed
  beats carry their failure reason; drafts record cost, models used, and
  fallback beats. Long local-model calls are bounded by per-draft time
  budgets; cloud drafting via any OpenAI-compatible endpoint is optional
  (`LLM_PROVIDER=openai_compatible`), with per-run spend caps and automatic
  model rotation on rate limits.
- **Asset Library** is reuse-first: `REUSE` existing verified inventory before
  `ACQUIRE`. External discovery spans Openverse, Wikimedia Commons
  (images + video), and optional keyed Pexels/Pixabay, with relevance +
  license + resolution ranking, provider interleaving, upload-date sorting,
  and entity identity screening (wrong-person photos are removed with
  reasons). Nothing downloads without your explicit save action; rights
  review is a separate, recorded step.
- **Quality gates** block publishing: unresolved research markers, unapproved
  scripts, unaudited voice, and voice/video duration mismatch all fail
  loudly instead of shipping silently.
- **Provenance** is persisted: every run file records template version,
  generation mode per beat, asset licenses/sources, voice engine, render
  report, and cost.

## Quickstart

```powershell
Copy-Item .env.example .env   # then add optional keys (Pexels, Pixabay, LLM)
python -m apps.web_ui.server --root .
# open http://127.0.0.1:8000
```

- Workflows: pick short (9:16, ~40s) or long (16:9, 8–20 min), draft, review,
  attach verified media, render preview, generate voice, audit, render full.
- Asset library: describe a need → check inventory → search → save/verify.
- Runs & queue: live run statuses; Overview: asset/run analytics.
- Full local setup (FFmpeg, TTS runtime, fonts; Ollama only for standalone drafting): [transferable-runtime.md](docs/transferable-runtime.md).
- Engine contract and architecture: [PROJECT_SPEC.md](PROJECT_SPEC.md).
- Hermes/Engine boundary and integration plan: [docs/hermes-engine-integration.md](docs/hermes-engine-integration.md).

## Layout

- `apps/content_workflow.py` — script drafting + agent runs
- `apps/llm.py` — provider-agnostic model transport, rotation, budgets
- `apps/orchestrator/` — legacy/local drafting orchestration; external Hermes integration is planned
- `apps/distribution/` — channel routing + replaceable platform adapters (local_file ships; platform stubs stage only)
- `apps/measurement/` — lifecycle states (generated…paid) + outcome/payout ledger
- `apps/learning/` — advisory portfolio allocation + channel lifecycle (owner decides)
- `apps/worker/` — local Python queue consumer
- `apps/asset_library/` — registry, discovery, identity, ingest, QA layers
- `apps/video_renderer.py` — FFmpeg composition (Ken Burns, fades, overlays, end-card)
- `apps/voice_tts.py` + `apps/tts_preview_worker.py` — local voice previews
- `apps/web_ui/` — stdlib-only web UI (static `index.html`/`app.js`/`styles.css`)
- `template_foundation/` — versioned Allen Knows Ball channel packages
- `data/entities/` + `taxonomy.json` — domain packs (clubs, players, competitions)
- `tests/` — `python -m pytest tests -q` (no network, no keys needed)
- `runtime/` — git-ignored per-machine state (DB, runs, renders, voice, model cache)
- `.env` — machine-local keys and paths, never committed (see `.env.example`)

## Core principles

- Portable by design; local-first where practical
- Free/open-source tools preferred; paid APIs never foundational
- Secrets never committed to Git
- Source evidence and provenance are first-class data
- AI generation is separated from validation and publishing
- Platform adapters remain replaceable
- The system must decline publishing when quality or evidence thresholds fail

## Initial channel focus

**Soccer** for a Vietnamese-speaking audience. First channel: **Allen Knows
Ball**. Template Foundation is the fixed, versioned identity layer; the Asset
Library supplies only approved variable media.
