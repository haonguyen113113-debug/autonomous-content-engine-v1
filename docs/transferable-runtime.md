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
Its bounded workflow generates script drafts and asset-need suggestions; it does
not render video.

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

## Video renderer boundary

Template timelines specify the visuals, event intervals, transitions, and effects
that a renderer should execute. The renderer is a separate workflow component and
is not included in the current implementation. Model installation does not provide
video editing or rendering capability.
