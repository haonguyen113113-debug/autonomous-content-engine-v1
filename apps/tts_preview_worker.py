from __future__ import annotations

import sys
import unicodedata

from vieneu import Vieneu


def _silence_p() -> float:
    import os
    try:
        return max(0.0, min(0.5, float(os.environ.get("TTS_SILENCE_P", "0.08"))))
    except (TypeError, ValueError):
        return 0.08


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: tts_preview_worker.py REFERENCE OUTPUT")
    sys.stdin.reconfigure(encoding="utf-8")
    reference_path, output_path = sys.argv[1:]
    text = unicodedata.normalize("NFC", sys.stdin.read()).strip()
    # Shorts narration needs tighter pacing than the vendor default
    # (silence_p=0.15 leaves broadcast-style pauses between sentences).
    engine = Vieneu(mode="v3turbo", backend="onnx")
    audio = engine.infer(text=text, ref_audio=reference_path, silence_p=_silence_p())
    engine.save(audio, output_path)


if __name__ == "__main__":
    main()
