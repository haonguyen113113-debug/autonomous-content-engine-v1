"""Generative art-bed library for the v11 pack — CYBER FAMILY ONLY (seeded, offline).

Six cool-neon beds x two aspects. Rendered small then upscaled (soft art),
grain + vignette at full size. Every pixel audits inside the cyber set
(void/panel/cyan/magenta/amber/paper/slate) or its blends. Beds live under
resources/beds/; starters composite type over them via image elements.

Run: python apps/studio_templates/build_beds.py
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent.parent
SHORT_DIR = ROOT / "template_foundation/templates/allen-knows-ball/12.0.0/resources/beds"
LONG_DIR = ROOT / "template_foundation/templates/allen-knows-ball/longform-12.0.0/resources/beds"

VOID = (6, 9, 19)
PANEL = (13, 20, 36)
CYAN = (0, 229, 255)
MAGENTA = (255, 61, 129)
AMBER = (255, 176, 58)
PAPER = (242, 246, 255)
SLATE = (130, 150, 190)


def _finish(small: Image.Image, tw: int, th: int, seed: int,
            grain_strength: int = 34) -> Image.Image:
    img = small.resize((tw, th), Image.Resampling.LANCZOS)
    w, h = img.size
    rng = random.Random(seed)
    tile = Image.new("L", (270, 480))
    px = tile.load()
    for ty in range(480):
        for tx in range(270):
            px[tx, ty] = min(200, max(120, int(160 + rng.gauss(0, 10))))
    gray = tile.resize((w, h), Image.Resampling.BILINEAR)
    layer = Image.merge("RGB", (gray, gray, gray)).convert("RGBA")
    layer.putalpha(Image.new("L", (w, h), grain_strength))
    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    vig = Image.new("L", (1, h))
    vig.putdata([max(0, int(120 * (abs(y - h / 2) / (h / 2)) ** 2)) for y in range(h)])
    black = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    black.putalpha(vig.resize((w, h)))
    return Image.alpha_composite(img.convert("RGBA"), black).convert("RGB")


def _dots(d, w, h, rng, n, colors, rmin=1, rmax=5, amin=50, amax=170):
    for _ in range(n):
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(rmin, rmax)
        d.ellipse([x - r, y - r, x + r, y + r],
                  fill=rng.choice(colors) + (rng.randint(amin, amax),))


def _circuits(d, w, h, rng, n, y_lo, y_hi):
    for _ in range(n):
        x, yy = rng.uniform(0, w), rng.uniform(y_lo, y_hi)
        pts = [(x, yy)]
        col = CYAN if rng.random() > 0.45 else MAGENTA
        for _ in range(5):
            dx = rng.choice((-1, 1)) * rng.uniform(w * 0.05, w * 0.18)
            dy = rng.choice((-1, 1)) * rng.uniform(0, h * 0.1)
            if abs(dx) > abs(dy):
                pts.append((pts[-1][0] + dx, pts[-1][1]))
                pts.append((pts[-1][0] + dy, pts[-1][1] + dy))
            else:
                pts.append((pts[-1][0], pts[-1][1] + dy))
        d.line(pts, fill=col + (110,), width=3, joint="curve")
        for px_, py_ in (pts[0], pts[-1]):
            d.ellipse([px_ - 7, py_ - 7, px_ + 7, py_ + 7], outline=col + (160,), width=3)


def bed_cyber_grid(w, h, seed, horizon_t=0.60, glow=1.0):
    rng = random.Random(seed)
    img = Image.new("RGB", (w, h), VOID)
    d = ImageDraw.Draw(img, "RGBA")
    horizon = int(h * horizon_t)
    for r, a, col in ((int(w * 0.96), int(26 * glow), MAGENTA),
                      (int(w * 0.7), int(34 * glow), MAGENTA),
                      (int(w * 1.18), int(18 * glow), CYAN),
                      (int(w * 0.55), int(44 * glow), CYAN)):
        d.ellipse([w // 2 - r, horizon - r // 5, w // 2 + r, horizon + r // 5], fill=col + (a,))
    for i in range(-10, 11):
        d.line([w // 2, horizon, w // 2 + i * w * 0.2, h], fill=CYAN + (40,), width=2)
    y, step = horizon + 8, 10
    while y < h:
        d.line([0, y, w, y], fill=CYAN + (44,), width=2)
        step = step * 1.28 + 2
        y += step
    _circuits(d, w, h, rng, 4, int(h * 0.08), max(int(h * 0.08) + 1, horizon - 40))
    _dots(d, w, h, rng, 60, [CYAN, MAGENTA, AMBER], 3, 16, 40, 110)
    return img.filter(ImageFilter.GaussianBlur(1))


def bed_grid_deep(w, h, seed):
    img = bed_cyber_grid(w, h, seed)
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([0, 0, w, h], fill=VOID + (110,))
    return img


def bed_floodlight(w, h, seed):
    """Cyber floodlight: cyan-white cones over void (no green)."""
    rng = random.Random(seed)
    img = Image.new("RGB", (w, h), VOID)
    d = ImageDraw.Draw(img, "RGBA")
    for cx in (w * 0.2, w * 0.5, w * 0.8):
        d.polygon([(cx - 26, 0), (cx + 26, 0), (cx + w * 0.16, h), (cx - w * 0.16, h)],
                  fill=(150, 220, 235, 30))
        d.ellipse([cx - 30, -30, cx + 30, 30], fill=(230, 250, 255, 130))
    _dots(d, w, h, rng, 200, [PAPER, AMBER, CYAN], 1, 3, 40, 120)
    return img


def bed_bokeh(w, h, seed):
    rng = random.Random(seed)
    img = Image.new("RGB", (w, h), VOID)
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse([w // 2 - w, -h // 3, w // 2 + w, h // 3], fill=CYAN + (26,))
    for _ in range(46):
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(8, 42)
        col = rng.choice([AMBER, CYAN, PAPER, MAGENTA])
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (rng.randint(24, 70),))
    img = img.filter(ImageFilter.GaussianBlur(6))
    d = ImageDraw.Draw(img, "RGBA")
    _dots(d, w, h, rng, 90, [PAPER, AMBER, CYAN], 1, 3, 90, 180)
    return img


def bed_inkstorm(w, h, seed):
    rng = random.Random(seed)
    img = Image.new("RGB", (w, h), VOID)
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(46):
        x, y = rng.uniform(-40, w + 40), rng.uniform(0, h)
        pts = []
        for _ in range(26):
            ang = math.sin(x * 0.014 + seed) + math.cos(y * 0.02) * 1.4
            x += math.cos(ang) * 22
            y += math.sin(ang) * 22
            pts.append((x, y))
        kind = rng.random()
        col = SLATE if kind > 0.72 else (CYAN if kind > 0.5 else MAGENTA)
        d.line(pts, fill=col + (rng.randint(22, 60),), width=rng.randint(4, 14), joint="curve")
    _dots(d, w, h, rng, 160, [SLATE, MAGENTA, AMBER], 1, 6, 40, 110)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def bed_pitch_void(w, h, seed):
    """Quiet bed for dense cards: void + giant faint pitch lines."""
    rng = random.Random(seed)
    img = Image.new("RGB", (w, h), VOID)
    d = ImageDraw.Draw(img, "RGBA")
    d.line([0, int(h * 0.5), w, int(h * 0.5)], fill=CYAN + (30,), width=3)
    d.ellipse([w // 2 - w * 0.42, int(h * 0.5) - int(w * 0.42),
               w // 2 + w * 0.42, int(h * 0.5) + int(w * 0.42)],
              outline=CYAN + (30,), width=3)
    _circuits(d, w, h, rng, 2, 0, int(h * 0.3))
    _dots(d, w, h, rng, 50, [SLATE, CYAN], 1, 4, 40, 90)
    return img


BEDS = {
    "cyber-grid": (lambda w, h, s: bed_cyber_grid(w, h, s), 42),
    "grid-deep": (lambda w, h, s: bed_grid_deep(w, h, s), 43),
    "floodlight": (bed_floodlight, 7),
    "neon-bokeh": (bed_bokeh, 5),
    "inkstorm": (bed_inkstorm, 23),
    "pitch-void": (bed_pitch_void, 77),
}


def main() -> None:
    # Remove retired warm beds so no stale file can be referenced.
    for d in (SHORT_DIR, LONG_DIR):
        d.mkdir(parents=True, exist_ok=True)
        for stale in ("ember-night", "magma-flow", "stand-bokeh",
                      "floodlight-turf", "inkstorm-wash"):
            for old in d.glob(f"*-{stale}.png"):
                old.unlink()
    for name, (fn, seed) in BEDS.items():
        short = _finish(fn(540, 960, seed), 1080, 1920, seed)
        short.save(SHORT_DIR / f"short-{name}.png")
        long = _finish(fn(960, 540, seed + 1), 1920, 1080, seed + 1)
        long.save(LONG_DIR / f"long-{name}.png")
        print(f"ok short/long-{name}.png")


if __name__ == "__main__":
    main()
