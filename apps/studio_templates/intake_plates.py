"""Intake Express plates: normalize Downloads art to pack-ready backgrounds.

- Center-crops to 9:16, upscales to exactly 1080x1920 (LANCZOS; backgrounds
  are soft art, upscale artifacts negligible), converts to RGB PNG.
- Validates exact pixels + <2MB, writes intake report.
- Target: pack-drop/12.0.0/<canonical>.png (build consumes it later).

File identification (aspect + visual check) happens before running: pass
pairs of SOURCE=CANONICAL on the command line.

  python apps/studio_templates/intake_plates.py "Downloads/a.png=short-f1-duel" ...

Run with no args to list today's image candidates in Downloads.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DROP = ROOT / "pack-drop" / "12.0.0"
TARGET = (1080, 1920)
MAX_BYTES = 2 * 1024 * 1024


def candidates() -> list[Path]:
    dl = Path.home() / "Downloads"
    files = [p for p in dl.iterdir()
             if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:15]


def intake(src: Path, canonical: str) -> dict:
    from PIL import Image

    with Image.open(src) as opened:
        img = opened.convert("RGB")
    w, h = img.size
    want_ratio = TARGET[0] / TARGET[1]
    # Center-crop to 9:16, then upscale to exact pixels.
    if w / h > want_ratio:  # too wide -> crop width
        nw = int(h * want_ratio)
        box = ((w - nw) // 2, 0, (w + nw) // 2, h)
    else:  # too tall -> crop height
        nh = int(w / want_ratio)
        box = (0, (h - nh) // 2, w, (h + nh) // 2)
    img = img.crop(box).resize(TARGET, Image.Resampling.LANCZOS)
    DROP.mkdir(parents=True, exist_ok=True)
    out = DROP / f"{canonical}.png"
    img.save(out)
    size = out.stat().st_size
    return {"src": str(src), "src_size": (w, h), "out": str(out),
            "ok": img.size == TARGET and size <= MAX_BYTES, "bytes": size}


def main(argv: list[str]) -> int:
    if not argv:
        print("Candidates in Downloads (newest first):")
        for p in candidates():
            print(f"  {p.name}  {p.stat().st_size // 1024}KB")
        print('Usage: intake_plates.py "Downloads/a.png=short-f1-duel" ...')
        return 0
    bad = 0
    for item in argv:
        src_name, _, canonical = item.partition("=")
        src = Path.home() / "Downloads" / src_name if not Path(src_name).is_absolute() \
            else Path(src_name)
        report = intake(src, canonical)
        flag = "OK " if report["ok"] else "FAIL"
        if not report["ok"]:
            bad += 1
        print(f"{flag} {src_name} {report['src_size']} -> {canonical}.png "
              f"{report['bytes'] // 1024}KB")
    print(f"{len(argv) - bad}/{len(argv)} pack-ready")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
