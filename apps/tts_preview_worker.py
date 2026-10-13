from __future__ import annotations

import sys
import unicodedata

from vieneu import Vieneu


def _float_env(name: str, default: float, low: float, high: float) -> float:
    import os
    try:
        return max(low, min(high, float(os.environ.get(name, default))))
    except (TypeError, ValueError):
        return default


def _silence_p() -> float:
    return _float_env("TTS_SILENCE_P", 0.08, 0.0, 0.5)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: tts_preview_worker.py REFERENCE OUTPUT")
    import os
    sys.stdin.reconfigure(encoding="utf-8")
    reference_path, output_path = sys.argv[1:]
    text = unicodedata.normalize("NFC", sys.stdin.read()).strip()
    # Shorts narration needs tighter pacing than the vendor default
    # (silence_p=0.15 leaves broadcast-style pauses between sentences).
    engine = Vieneu(mode="v3turbo", backend="onnx")
    # TTS_VOICE selects a built-in preset (e.g. a Southern voice) instead of
    # cloning the reference file. Accent and identity come from the voice
    # itself; there is no dialect switch on this engine.
    preset = os.environ.get("TTS_VOICE", "").strip()
    kwargs: dict = {
        "silence_p": _silence_p(),
        "temperature": _float_env("TTS_TEMPERATURE", 0.8, 0.1, 1.5),
        "crossfade_p": _float_env("TTS_CROSSFADE_P", 0.0, 0.0, 0.5),
    }
    if preset:
        audio = engine.infer(text=text, voice=preset, **kwargs)
    else:
        audio = engine.infer(text=text, ref_audio=reference_path, **kwargs)
    engine.save(audio, output_path)


if __name__ == "__main__":
    main()
