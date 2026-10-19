# Machine setup — everything the engine needs on a new PC

Source repo carries code, templates, fonts, and pins. The machine provides
runtimes, models, keys, and media. Nothing below is committed to Git
(`.gitignore` covers `.env` and `runtime/`).

## 1. Base

- Python 3.10+ (`python --version`), Git, PowerShell.
- `Copy-Item .env.example .env`, then fill keys below.

## 2. Script models (optional standalone drafting)

The target Hermes workflow supplies the structured script, so an LLM is not a
required Engine runtime dependency for that path. Configure a provider below
only when using the existing standalone/local drafting workflow.

- Default cloud-first: Groq via OpenAI-compatible endpoint.
  `.env`: `LLM_PROVIDER=openai_compatible`,
  `LLM_BASE_URL=https://api.groq.com/openai/v1`,
  `LLM_MODELS=qwen/qwen3.8-27b,openai/gpt-oss-120b,openai/gpt-oss-20b`,
  `LLM_API_KEY=<groq key>`, `LLM_BUDGET_USD_PER_RUN=0.25`.
- Fallback local: install Ollama, `ollama pull qwen3.5:2b`,
  `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://localhost:11434`.
- Verify: create a draft in Workflows; run file records provider/models/cost.

## 3. Voice (local TTS)

- `python -m venv runtime/tts-venv`
- `runtime/tts-venv/Scripts/python.exe -m pip install -r requirements-local-tts.txt`
- First preview downloads VieNeu-TTS v3 Turbo into `runtime/model-cache`.
- Voice reference: record ~30–60s sample, save in Workflows (Voice sample).
  Stored under git-ignored `runtime/voice/`.
- Optional presets/pacing in `.env`: `TTS_VOICE=Adam` (Southern),
  `TTS_SILENCE_P=0.08`, `TTS_TEMPERATURE=0.8`, `TTS_CROSSFADE_P=0.0`.

## 4. Video renderer

- `winget install --id Gyan.FFmpeg.Shared --exact` (needs `ffmpeg` + `ffprobe`
  on PATH) or set machine-local `FFMPEG_PATH` in `.env`.
- `python -m pip install -r requirements-renderer.txt` (Pillow).
- Fonts ship with each template package (`resources/fonts`, OFL).

## 5. Motion atoms (optional, build-time)

- `python -m venv runtime/motion-venv` (optional)
- `runtime/motion-venv/Scripts/python.exe -m pip install -r requirements-motion.txt`
- Renders pre-baked motion atoms; never required to serve or render video.

## 6. Asset discovery keys (optional, free tiers)

- Pixabay: `PIXABAY_API_KEY` (100 req/min). Pexels: `PEXELS_API_KEY`.
- Without keys: Openverse + Wikimedia Commons work out of the box.

## 7. AI imagery keys (optional)

- `GEMINI_API_KEY` (Google AI Studio, billing required for image models),
  `FAL_API_KEY`, `HF_TOKEN`, `LAYER_API_KEY`, `SCENARIO_API_KEY`,
  `RECRAFT_API_KEY` — add only the providers you actually use.
- AI assets always enter through owner approval + LICENSES provenance records.

## 8. Run & verify

- `python -m apps.web_ui.server --root .` → http://127.0.0.1:8000
- `python -m pytest tests -q` (no network, no keys needed) — must be green.

## 9. Move routine records between PCs (explicit, never automatic)

- `runtime/engine.db`, `runtime/runs/`, `runtime/renders/`, `runtime/voice/`,
  `runtime/assets/library/` are per-machine. Copy them deliberately when
  migrating; re-verify voice reference and payouts on the new machine.

## 10. Local queue worker

- The queue worker runs directly on the same machine as the Engine and reads
  jobs from `runtime/queue/`. Start it in a separate terminal with
  `python -m apps.worker.main` from the repository root.
- Keep the worker running while queued jobs are being processed. Stop it with
  Ctrl+C; unfinished claims are recovered when a worker starts again.
- No container runtime is required. Voice generation and rendering continue
  to use the local machine's configured tools and media.
