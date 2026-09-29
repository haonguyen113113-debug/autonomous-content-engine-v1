from __future__ import annotations

import sys
import unicodedata

from vieneu import Vieneu


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: tts_preview_worker.py REFERENCE OUTPUT")
    reference_path, output_path = sys.argv[1:]
    text = unicodedata.normalize("NFC", sys.stdin.read()).strip()
    engine = Vieneu(mode="v3turbo", backend="onnx")
    audio = engine.infer(text=text, ref_audio=reference_path)
    engine.save(audio, output_path)


if __name__ == "__main__":
    main()
