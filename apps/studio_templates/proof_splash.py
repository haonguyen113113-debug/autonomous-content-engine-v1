"""Splash-art sketches: documentary type vs artwork beds (divergence proof).

Two genuinely different splash directions for the same brief (statement card,
"HÀNG THỦ SẬP ĐỔ TỐI NAY"), one sheet, owner picks:
- S1 "Ember Stadium": dark ink ground, seeded ember flow-field, amber bloom,
  paper monumental type with orange glow.
- S2 "Paper Storm": daylight paper ground, ink-wash turbulence strokes,
  orange seal hits, monumental ink type.
Method: algorithmic-art ported to PIL (seeded randomness, flow fields,
parametric variation — no browser/GPU). Deterministic seeds; beds pre-render
once and reuse. Type: Tektur display, BeVietnam micro (both diacritic-clean).

Run: python apps/studio_templates/proof_splash.py
Writes: docs/design/splash-sheet.png
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_FONTS = ROOT / "skills" / "canvas-design" / "canvas-fonts"
OUT = ROOT / "docs" / "design"

INK = (23, 26, 38)
PAPER = (246, 241, 227)
ORANGE = (240, 120, 98)
AMBER = (255, 176, 58)
SLATE = (90, 107, 140)


def tektur(size: int):
    return ImageFont.truetype(str(SKILL_FONTS / "Tektur-Medium.ttf"), size)


def bev(size: int, bold: bool = False):
    from PIL import ImageFont as _F

    base = ROOT / "template_foundation/templates/allen-knows-ball/10.0.0/resources/fonts"
    name = "BeVietnamPro-Bold.ttf" if bold else "BeVietnamPro-Regular.ttf"
    for cand in (base / name, SKILL_FONTS / name):
        try:
            return _F.truetype(str(cand), size)
        except OSError:
            continue
    return _F.load_default()


def tracked(draw, x, y, text, font, fill, em=-0.02):
    cx = x
    for ch in text:
        draw.text((cx, y), ch, font=font, fill=fill)
        try:
            adv = draw.textlength(ch, font=font)
        except (ValueError, TypeError):
            adv = font.size * 0.6
        cx += adv + em * font.size
    return cx - x


def grain(img, seed=7, strength=40, lo=150, hi=235):
    w, h = img.size
    rng = random.Random(seed)
    tile = Image.new("L", (270, 480))
    px = tile.load()
    for ty in range(480):
        for tx in range(270):
            px[tx, ty] = min(hi, max(lo, int((lo + hi) // 2 + rng.gauss(0, 9))))
    gray = tile.resize((w, h), Image.Resampling.BILINEAR)
    layer = Image.merge("RGB", (gray, gray, gray)).convert("RGBA")
    layer.putalpha(Image.new("L", (w, h), strength))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def ember_bed(w=540, h=960, seed=11):
    """Night stadium ember field: bloom core + rising particle streaks."""
    rng = random.Random(seed)
    img = Image.new("RGB", (w, h), INK)
    d = ImageDraw.Draw(img, "RGBA")
    # Bloom core low-center
    for r, a in ((420, 26), (320, 34), (220, 46), (130, 60)):
        d.ellipse([w // 2 - r, h - r // 2 - 120, w // 2 + r, h + r // 2 - 120],
                  fill=(255, 140, 60, a))
    # Rising embers on a sine flow-field
    for _ in range(900):
        x = rng.uniform(0, w)
        y = rng.uniform(0, h)
        drift = math.sin(y * 0.012 + seed) * 60
        length = rng.uniform(6, 42)
        heat = rng.random()
        col = (255, 176, 58) if heat > 0.6 else ((240, 120, 98) if heat > 0.25 else (90, 107, 140))
        d.line([x + drift * 0.2, y, x + drift * 0.2 + rng.uniform(-4, 4), y - length],
               fill=col + (rng.randint(60, 170),), width=rng.choice((1, 2, 2, 3)))
    # Hot dots
    for _ in range(130):
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(1, 4)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 200, 120, rng.randint(90, 200)))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    # Vignette
    vig = Image.new("L", (1, h))
    vig.putdata([max(0, int(120 * (abs(y - h / 2) / (h / 2)) ** 2)) for y in range(h)])
    black = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    black.putalpha(vig.resize((w, h)))
    img = Image.alpha_composite(img.convert("RGBA"), black).convert("RGB")
    return grain(img, seed=seed)


def storm_bed(w=540, h=960, seed=23):
    """Daylight ink-wash storm: flowing strokes + splatter on paper."""
    rng = random.Random(seed)
    img = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(img, "RGBA")
    # Long wash strokes following a flow field
    for _ in range(46):
        x, y = rng.uniform(-40, w + 40), rng.uniform(0, h)
        pts = []
        for _ in range(26):
            ang = math.sin(x * 0.008 + seed) + math.cos(y * 0.011) * 1.4
            x += math.cos(ang) * 22
            y += math.sin(ang) * 22
            pts.append((x, y))
        kind = rng.random()
        col = (23, 26, 38) if kind > 0.72 else ((90, 107, 140) if kind > 0.5 else (240, 120, 98))
        d.line(pts, fill=col + (rng.randint(22, 60),), width=rng.randint(4, 14), joint="curve")
    # Splatter
    for _ in range(160):
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(1, 6)
        col = (23, 26, 38) if rng.random() > 0.3 else (240, 120, 98)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (rng.randint(40, 110),))
    # Seal hit
    d.ellipse([w - 190, 90, w - 60, 220], fill=(240, 120, 98, 220))
    dd = ImageDraw.Draw(img, "RGBA")
    dd.text((w - 168, 128), "AKB", font=tektur(56), fill=(246, 241, 227, 255))
    return grain(img.filter(ImageFilter.GaussianBlur(0.6)), seed=seed)


def glow_type(img, x, y, text, font, glow, blur=12):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((x, y), text, font=font, fill=glow)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def fit_line(draw, text, start, max_w):
    size = start
    while size > 40:
        f = tektur(size)
        try:
            w = draw.textlength(text, font=f)
        except (ValueError, TypeError):
            break
        if w <= max_w:
            return f
        size -= 6
    return tektur(40)


def card_s1() -> Image.Image:
    W, H = 540, 960
    img = ember_bed(W, H)
    d = ImageDraw.Draw(img, "RGBA")
    left, top = 38, 120
    img = glow_type(img, left, top - 40, "TUYÊN BỐ", tektur(54), (255, 176, 58, 110))
    d = ImageDraw.Draw(img, "RGBA")
    tracked(d, left, top - 40, "TUYÊN BỐ", tektur(54), PAPER + (255,))
    d.text((left, top + 30), "Allen Knows Ball", font=bev(20), fill=AMBER + (255,))
    y = 300
    for line in ["HÀNG THỦ", "SẬP ĐỔ", "TỐI NAY"]:
        f = fit_line(d, line, 118, W - left * 2)
        img = glow_type(img, left, y, line, f, (240, 120, 98, 120))
        d = ImageDraw.Draw(img, "RGBA")
        tracked(d, left, y, line, f, PAPER + (255,), em=-0.03)
        y += f.size + 12
    d.rectangle([left, y + 10, W - left, y + 18], fill=ORANGE + (255,))
    d.text((left, y + 44), "Hàng thủ số 1 V.League thủng 2 bàn", font=bev(22), fill=PAPER + (255,))
    d.text((left, y + 74), "trong 15 phút cuối hiệp hai.", font=bev(22), fill=PAPER + (255,))
    d.text((38, H - 56), "Nguồn / Opta • Vòng 12", font=bev(20), fill=AMBER + (255,))
    return img


def card_s2() -> Image.Image:
    W, H = 540, 960
    img = storm_bed(W, H)
    d = ImageDraw.Draw(img, "RGBA")
    # Type hold-back: quiet paper veil behind the hero zone, storm at edges.
    d.rectangle([0, 250, W, 700], fill=(246, 241, 227, 150))
    left, top = 38, 120
    tracked(d, left, top - 40, "TUYÊN BỐ", tektur(54), INK + (255,))
    d.text((left, top + 30), "Allen Knows Ball", font=bev(20, True), fill=INK + (255,))
    y = 300
    for line in ["HÀNG THỦ", "SẬP ĐỔ", "TỐI NAY"]:
        f = fit_line(d, line, 118, W - left * 2)
        tracked(d, left, y, line, f, INK + (255,), em=-0.03)
        y += f.size + 12
    d.rectangle([left, y + 10, W - left, y + 18], fill=ORANGE + (255,))
    d.text((left, y + 44), "Hàng thủ số 1 V.League thủng 2 bàn", font=bev(22, True), fill=INK + (255,))
    d.text((left, y + 74), "trong 15 phút cuối hiệp hai.", font=bev(22, True), fill=INK + (255,))
    d.text((38, H - 56), "Nguồn / Opta • Vòng 12", font=bev(20, True), fill=INK + (255,))
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s1 = card_s1()
    s2 = card_s2()
    sheet = Image.new("RGB", (1080, 960), (23, 26, 38))
    sheet.paste(s1, (0, 0))
    sheet.paste(s2, (540, 0))
    sheet.save(OUT / "splash-sheet.png")
    print("wrote splash-sheet.png (S1 ember | S2 paper-storm)")


if __name__ == "__main__":
    main()
