# Transferable local runtime

The repository stores engine code, locked channel templates, font assets, and the
local dependency pins. Machine-specific configuration, downloaded AI weights,
voice recordings, generated runs, and the Asset Library database stay under the
ignored `.env` and `runtime/` paths. Recreate these on the PC that will run the
engine; do not copy credentials or personal voice recordings into Git.

## Local script model

1. Install Ollama from its official distribution for the target operating system.
2. Pull the starter model once:

   ```powershell
   ollama pull qwen3.5:2b
   ```

3. Copy `.env.example` to `.env` and configure `LLM_PROVIDER=ollama`,
   `LLM_MODEL=qwen3.5:2b`, and `OLLAMA_BASE_URL=http://localhost:11434`.
   Replace `LLM_MODEL` with another compatible model installed in Ollama when
   using a larger machine. Model weights remain in the machine's Ollama store.

The engine sends script prompts only to the configured local Ollama endpoint.
Its bounded workflow generates script drafts and asset-need suggestions.

## Optional cloud drafting

When local inference is too weak or slow for script quality, point the same
bounded workflow at any OpenAI-compatible endpoint by editing `.env` only —
no code changes, and Ollama stays the default:

```powershell
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=<a low-cost model id from your provider>
LLM_API_KEY=<paste the provider key here>
```

Low-cost starting points: a mini-tier model on OpenAI, or a cheap fast
model through an OpenRouter/Groq/DeepSeek-compatible key. The engine sends
the same small per-beat JSON prompts and records prompt/completion tokens
plus estimated cost per segment and per run (see `llm_cost_usd` in the saved
run file and under the draft notes in Workflows). `LLM_BUDGET_USD_PER_RUN`
(default `0.25`) caps spend per draft; exhausted budgets degrade to the
deterministic outline instead of spending more. The API key lives only in
the machine-local `.env`, which is never committed to Git.

## Optional local voice preview

Python 3.10 or newer is recommended. From the repository root:

```powershell
python -m venv runtime/tts-venv
runtime/tts-venv/Scripts/python.exe -m pip install --upgrade pip
runtime/tts-venv/Scripts/python.exe -m pip install -r requirements-local-tts.txt
```

The first local voice preview downloads the VieNeu-TTS v3 Turbo model assets from
Hugging Face into the ignored `runtime/model-cache` directory. The sample voice
recording is stored under ignored `runtime/voice`. Both are per-machine data and
must be supplied or recreated on the target PC. The UI requires an owner-approved
script before making a preview.

## Content packages

Template Foundation contains parallel draft packages for Allen Knows Ball:

- `allen-knows-ball.shortform-analyst`: 9:16, 30–58 seconds.
- `allen-knows-ball.longform-analyst`: 16:9, 8–20 minutes, with chapter and
  production timeline schema.

Runs pin their selected template ID and version in the saved draft. Asset Library
content, local run records, and voice data are not part of the source repository.
Plan a separate approved backup/export path if those operational records need to
move between PCs.

## Local video renderer

Install the local FFmpeg runtime with `winget install --id Gyan.FFmpeg.Shared --exact`;
make `ffmpeg` and `ffprobe` available on `PATH`, or set the machine-specific
`FFMPEG_PATH` in `.env`. The Workflows page can render an 18-second silent visual
template preview without voice/media, then emit an MP4 and a quality report under
ignored `runtime/renders/`. Full-run rendering is gated on owner script approval
and an owner-audited local voice preview. Voice reference recordings, voice outputs,
rendered videos, and run records remain per-machine runtime data and are not
committed to Git.

Install the renderer's Python dependency with `python -m pip install -r requirements-renderer.txt`.
It rasterizes Vietnamese-labeled tactical boards with pitch geometry, player markers,
directional vectors, and an animated ball.

The renderer validates the output container, target aspect ratio, Vietnamese
font, palette, full-pitch tactical markings, authored pass/run/press vectors,
and beat-by-beat ball motion. It does not yet place selected Asset Library
football media or execute the complete declared transition/effect set. The
JSON report identifies each such limit so a preview is not mistaken for a
production-ready video.
