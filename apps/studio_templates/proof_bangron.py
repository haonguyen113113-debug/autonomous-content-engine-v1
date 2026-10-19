"""Băng Rôn sketches: 3 proof cards (duel + statement + pitch) for owner review.

Grammar: docs/design/bang-ron-philosophy.md, plan docs/design/bang-ron-plan.md.
Palette (locked 5): ticket paper #F6F1E3, deep paper #E4DCC8, turnstile ink
#171A26, LED orange #F07862 (never body text on paper), slate #5A6B8C.
Type: Barlow Condensed (VI), Be Vietnam Pro (micro), BigShoulders (numerals
latin only). Motifs: LED band, perforation, stub notches, paper grain —
all non-data, seeded deterministic.

Run: python apps/studio_templates/proof_bangron.py
Writes: docs/design/bangron-duel.png, bangron-statement.png, bangron-pitch.png
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent.parent
FONTS = ROOT / "template_foundation" / "templates" / "allen-knows-ball" / "10.0.0" / "resources" / "fonts"
SKILL_FONTS = ROOT / "skills" / "canvas-design" / "canvas-fonts"
OUT = ROOT / "docs" / "design"

PAPER = (246, 241, 227)
DEEP = (228, 220, 200)
INK = (23, 26, 38)
ORANGE = (240, 120, 98)
AMBER = (255, 176, 58)
SLATE = (90, 107, 140)


def display(size: int):
    """Tektur: techy broadcast display with precomposed Vietnamese glyphs
    (immune to the no-raqm mark-positioning bug that breaks Barlow)."""
    return ImageFont.truetype(str(SKILL_FONTS / "Tektur-Medium.ttf"), size)


def tracked(draw, x, y, text, font, fill, em: float = -0.02):
    """Apple-design tracking: negative tracking on large display type."""
    cx = x
    for ch in text:
        draw.text((cx, y), ch, font=font, fill=fill)
        try:
            adv = draw.textlength(ch, font=font)
        except (ValueError, TypeError):
            adv = font.size * 0.6
        cx += adv + em * font.size
    return cx - x


def barlow(size: int):
    return ImageFont.truetype(str(FONTS / "BarlowCondensed-Bold.ttf"), size)


def bev(size: int, bold: bool = False):
    name = "BeVietnamPro-Bold.ttf" if bold else "BeVietnamPro-Regular.ttf"
    return ImageFont.truetype(str(FONTS / name), size)


def numeral(size: int):
    return ImageFont.truetype(str(SKILL_FONTS / "BigShoulders-Bold.ttf"), size)


def left(draw, x, y, text, font, fill):
    draw.text((x, y), text, font=font, fill=fill)
    return draw.textbbox((0, 0), text, font=font)[3]


def center(draw, cx, y, text, font, fill):
    w = draw.textbbox((0, 0), text, font=font)[2]
    draw.text((cx - w / 2, y), text, font=font, fill=fill)


def perforation(draw, x0, x1, y, color=INK, gap=26):
    x = x0
    while x <= x1:
        draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=color)
        x += gap


def notches(img, y, r=26):
    """Ticket notch bites on a band edge (paper discs over the band)."""
    draw = ImageDraw.Draw(img, "RGBA")
    w, _ = img.size
    draw.ellipse([-r, y - r, r, y + r], fill=PAPER + (255,))
    draw.ellipse([w - r, y - r, w + r, y + r], fill=PAPER + (255,))


def grain(img, seed=7, strength=46):
    from PIL import Image as _I

    w, h = img.size
    rng = random.Random(seed)
    tile = _I.new("L", (270, 480))
    px = tile.load()
    for ty in range(480):
        for tx in range(270):
            px[tx, ty] = min(235, max(150, int(192 + rng.gauss(0, 9))))
    gray = tile.resize((w, h), _I.Resampling.BILINEAR)
    layer = _I.merge("RGB", (gray, gray, gray)).convert("RGBA")
    alpha = _I.new("L", (w, h), strength)
    guard = ImageDraw.Draw(alpha)
    guard.rectangle([0, int(h * 0.93), w, h], fill=0)
    layer.putalpha(alpha)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def initials(name: str) -> str:
    import re

    words = [w for w in re.findall(r"[A-Za-zÀ-ỹĐđ]+", name) if w]
    return "".join(w[0].upper() for w in words[:2]) or "•"


def stub_box(draw, x, y, w, h, name):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=10,
                           fill=PAPER + (255,), outline=INK + (255,), width=5)
    center(draw, x + w // 2, y + 24, initials(name), display(84), INK + (255,))
    center(draw, x + w // 2, y + 136, name.upper(), display(46), INK + (255,))


def extrude(draw, x, y, text, font, face, depth=6, step=2):
    """Faux-3D cast type: layered ink shade offset down-right, face on top."""
    for i in range(depth, 0, -1):
        draw.text((x + i * step, y + i * step), text, font=font, fill=(13, 15, 26, 255))
    draw.text((x, y), text, font=font, fill=face)


def soft_shadow(img, box, radius=18, alpha=70):
    """Sticker lift: blurred black rounded rect composited under content."""
    from PIL import Image as _I, ImageDraw as _D, ImageFilter as _F

    layer = _I.new("RGBA", img.size, (0, 0, 0, 0))
    _D.Draw(layer).rounded_rectangle(box, radius=10, fill=(0, 0, 0, alpha))
    layer = layer.filter(_F.GaussianBlur(radius))
    return _I.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def glow_text(img, x, y, text, font, glow=(255, 176, 58, 90), blur=14):
    """LED glow: blurred amber copy behind lit type."""
    from PIL import Image as _I, ImageDraw as _D, ImageFilter as _F

    layer = _I.new("RGBA", img.size, (0, 0, 0, 0))
    _D.Draw(layer).text((x, y), text, font=font, fill=glow)
    layer = layer.filter(_F.GaussianBlur(blur))
    return _I.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def sketch_duel(v2: bool = False) -> Image.Image:
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img, "RGBA")
    # LED band
    d.rectangle([0, 0, W, 260], fill=INK + (255,))
    if v2:
        img = glow_text(img, 76, 60, "ĐỐI ĐẦU", display(108))
        d = ImageDraw.Draw(img, "RGBA")
    tracked(d, 76, 60, "ĐỐI ĐẦU", display(108), (246, 241, 227, 255))
    left(d, 76, 196, "V.League • Vòng 12", bev(36), AMBER + (255,))
    notches(img, 260)
    d = ImageDraw.Draw(img, "RGBA")
    perforation(d, 76, W - 76, 306)
    # Team stub boxes
    if v2:
        for bx in (76, 564):
            img = soft_shadow(img, [bx, 360, bx + 440, 620])
        d = ImageDraw.Draw(img, "RGBA")
    stub_box(d, 76, 360, 440, 260, "HÀ NỘI")
    stub_box(d, 564, 360, 440, 260, "NAM ĐỊNH")
    left(d, 76, 646, "5 trận bất bại", bev(34), SLATE + (255,))
    left(d, 564, 646, "3 thắng liên tiếp", bev(34), SLATE + (255,))
    d.line([76, 716, W - 76, 716], fill=INK + (255,), width=4)
    # Metric bands
    rows = [("Bàn thắng", "45", "38", "home"),
            ("Kiến tạo", "30", "30", "tie"),
            ("Sút trúng đích", "120", "98", "home")]
    y = 780
    for label, home, away, winner in rows:
        left(d, 76, y, label.upper(), display(44), SLATE + (255,))
        f = numeral(168)
        lw = d.textbbox((0, 0), home, font=f)[2]
        rw = d.textbbox((0, 0), away, font=f)[2]
        if v2:
            extrude(d, 270 - lw / 2, y + 60, home, f, INK + (255,))
            extrude(d, 810 - rw / 2, y + 60, away, f, INK + (255,))
        else:
            d.text((270 - lw / 2, y + 60), home, font=f, fill=INK + (255,))
            d.text((810 - rw / 2, y + 60), away, font=f, fill=INK + (255,))
        if winner == "home":
            d.rectangle([270 - 110, y + 60 + 178, 270 + 110, y + 60 + 190], fill=ORANGE + (255,))
        elif winner == "away":
            d.rectangle([810 - 110, y + 60 + 178, 810 + 110, y + 60 + 190], fill=ORANGE + (255,))
        y += 300
        if y < 1620:
            d.line([76, y - 14, W - 76, y - 14], fill=INK + (255,), width=2)
    # Stub
    d.rectangle([0, 1660, W, H], fill=DEEP + (255,))
    perforation(d, 76, W - 76, 1660)
    center(d, W // 2, 1780, "Nguồn / Opta • Vòng 12", bev(38), INK + (255,))
    return grain(img)


def sketch_statement() -> Image.Image:
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([0, 0, W, 300], fill=INK + (255,))
    tracked(d, 76, 70, "TUYÊN BỐ", display(110), (246, 241, 227, 255))
    left(d, 76, 226, "Allen Knows Ball", bev(36), AMBER + (255,))
    notches(img, 300)
    d = ImageDraw.Draw(img, "RGBA")
    perforation(d, 76, W - 76, 346)
    lines = ["HÀNG THỦ", "SẬP ĐỔ", "TỐI NAY"]
    y = 470
    for line in lines:
        f = display(240)
        w = d.textbbox((0, 0), line, font=f)[2]
        while w > W - 152 and f.size > 60:
            f = display(f.size - 8)
            w = d.textbbox((0, 0), line, font=f)[2]
        tracked(d, 76, y, line, f, INK + (255,))
        y += f.size + 18
    d.rectangle([76, y + 20, W - 76, y + 32], fill=ORANGE + (255,))
    y += 110
    left(d, 76, y, "Hàng thủ số 1 V.League thủng 2 bàn", bev(44), INK + (255,))
    left(d, 76, y + 64, "chỉ trong 15 phút cuối hiệp hai.", bev(44), INK + (255,))
    d.rectangle([0, 1660, W, H], fill=DEEP + (255,))
    perforation(d, 76, W - 76, 1660)
    center(d, W // 2, 1780, "Nguồn / Opta • Vòng 12", bev(38), INK + (255,))
    return grain(img)


def sketch_pitch() -> Image.Image:
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([0, 0, W, 180], fill=INK + (255,))
    tracked(d, 140, 36, "PRESSING TẦM CAO • BẪY BIÊN", display(74), (246, 241, 227, 255))
    left(d, 140, 124, "TA-06 • V.League • Vòng 12", bev(32), AMBER + (255,))
    notches(img, 180, r=22)
    d = ImageDraw.Draw(img, "RGBA")
    x0, y0, x1, y1 = 140, 250, 1780, 880
    d.rectangle([x0, y0, x1, y1], fill=(250, 247, 236, 255),
                outline=INK + (255,), width=6)
    d.line([x0, y0, x0, y1], fill=INK + (255,), width=10)
    d.line([x1, y0, x1, y1], fill=INK + (255,), width=10)
    d.line([(x0 + x1) // 2, y0, (x0 + x1) // 2, y1], fill=INK + (255,), width=5)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    d.ellipse([cx - 143, cy - 110, cx + 143, cy + 110], outline=INK + (255,), width=5)
    d.rectangle([x0, 420, x0 + 420, 580], fill=SLATE + (90,))
    d.rectangle([1050, 350, 1500, 650], fill=ORANGE + (56,))
    for gx in (300, 1340):
        d.rectangle([gx, 470, gx + 140, 530], fill=(250, 247, 236, 255),
                    outline=INK + (255,), width=4)

    def token(x, y, num, fill):
        d.ellipse([x, y, x + 96, y + 96], fill=fill + (255,), outline=INK + (255,), width=4)
        center(d, x + 48, y + 12, num, numeral(52), INK + (255,))

    for x, n in [(700, "9"), (1000, "10"), (1300, "7")]:
        token(x, 350, n, ORANGE)
    token(1100, 550, "6", (250, 247, 236))
    d.ellipse([1178, 583, 1222, 627], fill=ORANGE + (255,))
    d.ellipse([1192, 597, 1208, 613], fill=PAPER + (255,))
    for x0a in (790, 1090, 1390):
        x, x1a, y = x0a, x0a + 180, 390
        for seg in range(0, 180, 24):
            d.line([x + seg, y, x + seg + 14, y], fill=ORANGE + (255,), width=8)
        d.polygon([(x1a + 24, y), (x1a, y - 12), (x1a, y + 12)], fill=ORANGE + (255,))
    left(d, 165, 800, "BẪY PRESSING • PHÚT 67", display(42), INK + (255,))
    center(d, W - 260, 985, "Nguồn / Opta • Vòng 12", bev(32), INK + (255,))
    return grain(img)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sketch_duel().save(OUT / "bangron-duel.png")
    sketch_duel(v2=True).save(OUT / "bangron-duel-v2.png")
    sketch_statement().save(OUT / "bangron-statement.png")
    sketch_pitch().save(OUT / "bangron-pitch.png")
    # One contact sheet so all sketches are visible at once.
    duel = Image.open(OUT / "bangron-duel-v2.png").resize((540, 960))
    state = Image.open(OUT / "bangron-statement.png").resize((540, 960))
    pitch = Image.open(OUT / "bangron-pitch.png").resize((1080, 607))
    sheet = Image.new("RGB", (1080, 960 + 607 + 40), (23, 26, 38))
    sheet.paste(duel, (0, 0))
    sheet.paste(state, (540, 0))
    sheet.paste(pitch, (0, 1000))
    sheet.save(OUT / "bangron-sheet.png")
    print("wrote bangron-duel/statement/pitch/v2 + sheet")


if __name__ == "__main__":
    main()
