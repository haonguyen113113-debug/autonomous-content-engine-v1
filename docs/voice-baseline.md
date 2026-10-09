# Voice baseline (build phase → production)

During build, every run's voice preview is owner-audited to lock the
baseline below. In production the final gate is the **finished video**;
voice becomes automated QC (approved script + audited reference + duration
fit) with sampling, re-audited only when the reference or params change.

## Locked reference (fill in at audit)

- Engine: `pnnbao-ump/VieNeu-TTS-v3-Turbo (CPU/ONNX)`, local `runtime/tts-venv`
- Reference recording: `runtime/voice/` (per-machine, git-ignored — back it up separately)
- Pacing: `TTS_SILENCE_P=0.08` (vendor default 0.15 leaves broadcast pauses)
- Speech pace enforced in drafts: `CHARS_PER_SECOND=14`, `MAX_SPEECH_OVERRUN=1.25`
- Sample previews audited: _list run ids + dates here_

## Production QC (automatic, fail-loud)

1. `voice_profile_status`: reference present, runtime installed
2. `synthesize_voice_preview` requires owner-approved script, rejects `[CẦN NGUỒN]` markers
3. `render_full_run` requires `voice_preview_audited` + voice duration within `MAX_SPEECH_OVERRUN`
4. `render-report.json` marks voice `PENDING OWNER AUDIT` until the finished video is reviewed

## Re-baseline triggers

- New reference recording, engine/model change, pacing change, or systematic
  duration mismatch across runs. Otherwise: sample, don't gate every item.
