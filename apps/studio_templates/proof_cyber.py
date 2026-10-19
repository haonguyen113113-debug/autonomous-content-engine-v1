"""Cyber splash sketch: futuristic statement card for owner review.

Grammar: full-bleed cyber bed (perspective neon grid floor, horizon bloom,
circuit traces, scanlines, bokeh) + monumental Tektur claim with cyan glow.
Palette (custom theme, theme-factory method): void #060913, panel #0D1424,
neon cyan #00E5FF, pulse magenta #FF3D81, amber #FFB03A, paper #F2F6FF.
Seeded deterministic. Type all diacritic-clean (Tektur/BeVietnam).

Run: python apps/studio_templates/proof_cyber.py
Writes: docs/design/cyber-statement.png
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_FONTS = ROOT / "skills" / "canvas-design" / "canvas-fonts"
OUT = ROOT / "docs" / "design"

VOID = (6, 9, 19)
PANEL = (13, 20, 36)
CYAN = (0, 229, 255)
MAGENTA = (255, 61, 129)
AMBER = (255, 176, 58)
PAPER = (242, 246, 255)
SLATE = (130, 150, 190)


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


def glow_type(img, x, y, text, font, glow, blur=14):
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


def cyber_bed(w=1080, h=1920, seed=42):
    rng = random.Random(seed)
    # Vertical gradient void -> panel
    top = Image.new("RGB", (w, h), VOID)
    pixels = top.load()
    for y in range(h):
        t = y / max(1, h - 1)
        row = tuple(round(VOID[i] * (1 - t) + PANEL[i] * t) for i in range(3))
        for x in range(0, w, 4):
            pixels[x, y] = row
            if x + 1 < w:
                pixels[x + 1, y] = row
    img = top.filter(ImageFilter.GaussianBlur(2))
    d = ImageDraw.Draw(img, "RGBA")
    horizon = int(h * 0.60)
    # Horizon bloom: magenta core + cyan halo
    for r, a, col in ((520, 40, MAGENTA), (380, 52, MAGENTA), (640, 26, CYAN), (300, 60, CYAN)):
        d.ellipse([w // 2 - r, horizon - r // 5, w // 2 + r, horizon + r // 5], fill=col + (a,))
    # Perspective grid floor
    vpx, vpy = w // 2, horizon
    for i in range(-10, 11):
        d.line([vpx, vpy, vpx + i * 220, h], fill=CYAN + (46,), width=2)
    y = horizon + 8
    step = 10
    while y < h:
        d.line([0, y, w, y], fill=CYAN + (52,), width=2)
        step = step * 1.28 + 2
        y += step
    # Circuit traces (45-degree bends + nodes)
    for _ in range(4):
        x, yy = rng.uniform(0, w), rng.uniform(120, horizon - 60)
        pts = [(x, yy)]
        col = CYAN if rng.random() > 0.45 else MAGENTA
        for _ in range(5):
            dx = rng.choice((-1, 1)) * rng.uniform(60, 200)
            dy = rng.choice((-1, 1)) * rng.uniform(0, 120)
            if abs(dx) > abs(dy):
                pts.append((pts[-1][0] + dx, pts[-1][1]))
                pts.append((pts[-1][0] + dy, pts[-1][1] + dy))
            else:
                pts.append((pts[-1][0], pts[-1][1] + dy))
        d.line(pts, fill=col + (120,), width=3, joint="curve")
        for px_, py_ in (pts[0], pts[-1]):
            d.ellipse([px_ - 7, py_ - 7, px_ + 7, py_ + 7], outline=col + (170,), width=3)
            d.ellipse([px_ - 2, py_ - 2, px_ + 2, py_ + 2], fill=col + (200,))
    # Bokeh lights
    for _ in range(60):
        x, yy, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(3, 16)
        col = rng.choice([CYAN, MAGENTA, AMBER])
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (rng.randint(40, 110),))
    img = img.filter(ImageFilter.GaussianBlur(1))
    # Scanlines
    scan = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scan)
    for yy in range(0, h, 4):
        sd.line([0, yy, w, yy], fill=(0, 0, 0, 26), width=1)
    img = Image.alpha_composite(img.convert("RGBA"), scan).convert("RGB")
    # Grain + vignette
    tile = Image.new("L", (270, 480))
    tpx = tile.load()
    for ty in range(480):
        for tx in range(270):
            tpx[tx, ty] = min(200, max(120, int(160 + rng.gauss(0, 10))))
    gray = tile.resize((w, h), Image.Resampling.BILINEAR)
    layer = Image.merge("RGB", (gray, gray, gray)).convert("RGBA")
    layer.putalpha(Image.new("L", (w, h), 34))
    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    vig = Image.new("L", (1, h))
    vig.putdata([max(0, int(130 * (abs(y - h / 2) / (h / 2)) ** 2)) for y in range(h)])
    black = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    black.putalpha(vig.resize((w, h)))
    return Image.alpha_composite(img.convert("RGBA"), black).convert("RGB")


def sketch() -> Image.Image:
    W, H = 1080, 1920
    img = cyber_bed(W, H)
    d = ImageDraw.Draw(img, "RGBA")
    # HUD corner brackets
    B, L = 46, 26
    for x0, y0, dx, dy in ((B, 150, 1, 1), (W - B, 150, -1, 1), (B, H - 260, 1, -1), (W - B, H - 260, -1, -1)):
        d.line([x0, y0, x0 + L * dx, y0], fill=CYAN + (220,), width=4)
        d.line([x0, y0, x0, y0 + L * dy], fill=CYAN + (220,), width=4)
    # Kicker with glow
    img = glow_type(img, 76, 210, "TUYÊN BỐ", tektur(64), CYAN + (130,))
    d = ImageDraw.Draw(img, "RGBA")
    tracked(d, 76, 210, "TUYÊN BỐ", tektur(64), PAPER + (255,))
    d.text((76, 300), "Allen Knows Ball • Vòng 12", font=bev(34), fill=AMBER + (255,))
    # Claim
    y = 470
    for line in ["HÀNG THỦ", "SẬP ĐỔ", "TỐI NAY"]:
        f = fit_line(d, line, 236, W - 152)
        img = glow_type(img, 76, y, line, f, CYAN + (110,), blur=18)
        d = ImageDraw.Draw(img, "RGBA")
        tracked(d, 76, y, line, f, PAPER + (255,), em=-0.03)
        y += f.size + 20
    # Gradient rule cyan -> magenta
    for i in range(W - 152):
        t = i / max(1, W - 153)
        col = tuple(round(CYAN[j] * (1 - t) + MAGENTA[j] * t) for j in range(3))
        d.line([76 + i, y + 20, 76 + i, y + 32], fill=col + (255,))
    y += 100
    d.text((76, y), "Hàng thủ số 1 V.League thủng 2 bàn", font=bev(44), fill=PAPER + (255,))
    d.text((76, y + 64), "chỉ trong 15 phút cuối hiệp hai.", font=bev(44), fill=PAPER + (255,))
    # Provenance stub
    d.line([76, H - 180, W - 76, H - 180], fill=CYAN + (120,), width=2)
    d.text((76, H - 150), "Nguồn / Opta • Vòng 12", font=bev(36), fill=SLATE + (255,))
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sketch().save(OUT / "cyber-statement.png")
    print("wrote cyber-statement.png")


if __name__ == "__main__":
    main()
