# Autonomous Content Engine v1

A portable, local-first system that turns a football topic into a reviewed,
voice-narrated video: draft script → check the Asset Library → owner review →
local voice preview → FFmpeg render. Every step runs on your machine; paid
services are optional and never foundational.

> Status: working vertical slice for Vietnamese soccer Shorts (Allen Knows
> Ball). Long-form, publishing adapters, and measurement loops are next.

## How it works

```
Topic → Script draft (per beat, with retries) → Asset check (reuse first)
  → Owner review → Voice preview (local TTS) → Owner audit
  → Render MP4 + quality report
```

- **Script drafts** are generated beat by beat (6 short / 8–9 long) with
  per-beat validation, retry, and deterministic outline fallback. Failed
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
- Full local setup (Ollama, FFmpeg, TTS runtime, fonts): [transferable-runtime.md](docs/transferable-runtime.md).
- Engine contract and architecture: [PROJECT_SPEC.md](PROJECT_SPEC.md).

## Layout

- `apps/content_workflow.py` — script drafting + agent runs
- `apps/llm.py` — provider-agnostic model transport, rotation, budgets
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
