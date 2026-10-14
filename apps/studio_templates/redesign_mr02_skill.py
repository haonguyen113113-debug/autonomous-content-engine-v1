"""MR-02 redesign proof, designed with frontend-design + canvas-design skills.

Implements docs/design/mr02-plan.md ("San Chia Doi" split pitch) with PIL,
reusing the locked palette, safe areas, and required data slots of the
original score_card builder so the filter/renderer keep working unchanged.

Run: python apps/studio_templates/redesign_mr02_skill.py
Writes: docs/design/mr02-redesign-proof.png (1080x1920)
        docs/design/mr02-compare.png (original + redesign side by side)
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random

ROOT = Path(__file__).resolve().parent.parent.parent
FONTS = ROOT / "template_foundation" / "templates" / "allen-knows-ball" / "9.0.0" / "resources" / "fonts"
SKILL_FONTS = ROOT / "skills" / "canvas-design" / "canvas-fonts"
ORIGINAL = ROOT / "template_foundation" / "templates" / "allen-knows-ball" / "9.0.0" / "previews" / "short-mr-02-proof.png"
OUT_DIR = ROOT / "docs" / "design"

W, H = 1080, 1920
INK = (22, 27, 44)
CORAL = (224, 112, 95)
PAPER = (244, 242, 236)
SLATE = (90, 107, 140)
MIST = (139, 150, 176)
SPLIT_Y = 1120
MARGIN = 76


def font_brand(kind: str, size: int) -> ImageFont.FreeTypeFont:
    name = {
        "display": "BarlowCondensed-Bold.ttf",
        "body": "BeVietnamPro-Regular.ttf",
        "body-bold": "BeVietnamPro-Bold.ttf",
    }[kind]
    return ImageFont.truetype(str(FONTS / name), size)


def font_numeral(size: int) -> ImageFont.FreeTypeFont:
    """canvas-design skill: numerals are a visual element, not text.

    BigShoulders (OFL, vendored with the skill) carries latin digits only;
    all Vietnamese text stays in the brand faces per the brief, which wins.
    """
    return ImageFont.truetype(str(SKILL_FONTS / "BigShoulders-Bold.ttf"), size)


def parse_score(score: str) -> tuple[int, int]:
    numbers = [int(n) for n in re.findall(r"\d+", score)]
    if len(numbers) >= 2:
        return numbers[0], numbers[1]
    return 0, 0


def render_redesign(home: str, away: str, score: str, comp: str, when: str,
                    depth: bool | str = False, seed: int = 7) -> Image.Image:
    """depth=False flat; depth=True full depth pass; depth='lite' restrained pass."""
    home_goals, away_goals = parse_score(score)
    if away_goals > home_goals:
        top_name, top_goals, bottom_name, bottom_goals = away, away_goals, home, home_goals
    else:
        top_name, top_goals, bottom_name, bottom_goals = home, home_goals, away, away_goals
    draw_win = home_goals != away_goals

    img = Image.new("RGB", (W, H), INK)
    draw = ImageDraw.Draw(img)
    if draw_win:
        draw.rectangle([0, 0, W, SPLIT_Y], fill=CORAL)
    # Halfway rule + faint center circle (pitch vernacular, not decoration).
    draw.rectangle([0, SPLIT_Y - 3, W, SPLIT_Y + 3], fill=PAPER)
    draw.ellipse([540 - 420, SPLIT_Y - 420, 540 + 420, SPLIT_Y + 420],
                 outline=SLATE, width=3)
    # Quiet context line: sentence case, no eyebrow chrome (skill restraint).
    context = f"{comp} • {when}"
    draw.text((MARGIN, 205), context, font=font_brand("body", 40), fill=INK if draw_win else PAPER)
    # Winner: monumental numeral (ink on coral passes; paper-on-coral does not).
    draw.text((MARGIN, 300), top_name, font=font_brand("display", 130),
              fill=INK if draw_win else PAPER)
    if depth and draw_win:
        # Hero glow (broadcast-depth move 2): blurred paper copy behind the
        # numeral. Paper glow, never white bloom.
        glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        glow_draw.text((MARGIN - 8, 410), str(top_goals), font=font_numeral(560),
                       fill=PAPER + (110,))
        img = Image.alpha_composite(
            img.convert("RGBA"),
            glow_layer.filter(ImageFilter.GaussianBlur(18))).convert("RGB")
        draw = ImageDraw.Draw(img)
    draw.text((MARGIN - 8, 400), str(top_goals), font=font_numeral(560),
              fill=INK if draw_win else PAPER)    # Loser territory: dimmed numeral + name anchored together.
    draw.text((MARGIN, SPLIT_Y + 60), str(bottom_goals), font=font_numeral(280), fill=SLATE)
    draw.text((MARGIN, SPLIT_Y + 360), bottom_name, font=font_brand("display", 84), fill=PAPER)
    draw.text((W // 2, 1820), "Nguồn + ngày", font=font_brand("body", 36),
              fill=MIST, anchor="ma")
    if depth:
        img = apply_depth_pass(img, seed=seed, lite=(depth == "lite"))
    return img


def apply_depth_pass(img: Image.Image, seed: int = 7, lite: bool = False) -> Image.Image:
    """broadcast-depth moves 1, 3, 4 (glow already drawn by the caller).

    lite=True (emil-design-eng restraint: remove accessories until it reads
    clean): keep top-light + hero glow, halve the grain, drop haze bands.
    Seeded, CPU-only, palette-safe: gradients and haze use locked colors at
    low alpha; grain is monochrome and skips microcopy zones.
    """
    lite_sigma, lite_strength = (8, 60) if lite else (16, 100)
    rgba = img.convert("RGBA")
    # Move 1: top-light gradient + bottom shade, one light direction.
    light = Image.new("L", (1, H))
    light.putdata([max(0, 26 - int(26 * y / (H // 3))) if y < H // 3 else 0
                   for y in range(H)])
    white = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    white.putalpha(light.resize((W, H)))
    rgba = Image.alpha_composite(rgba, white)
    shade = Image.new("L", (1, H))
    shade.putdata([int(40 * (y - H * 5 // 6) / (H // 6)) if y > H * 5 // 6 else 0
                   for y in range(H)])
    black = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    black.putalpha(shade.resize((W, H)))
    rgba = Image.alpha_composite(rgba, black)
    # Move 4: two haze bands over dead zones only (never over the numeral).
    # Lite restraint: haze bands are the first accessory removed.
    if not lite:
        for y0, height, color, alpha in (
                (150, 90, PAPER, 14), (1330, 110, CORAL, 16)):
            band = Image.new("RGBA", (W, height), color + (alpha,))
            rgba.paste(band, (0, y0), band)
    # Move 3: seeded monochrome grain, masked off microcopy strips.
    # Tile small with random.Random(seed) for determinism (PIL effect_noise
    # is unseeded), then upscale; gray clamped to 86..180 so every pixel
    # stays inside the locked-palette ±90 audit box on any field.
    tile_w, tile_h = 270, 480
    rng = random.Random(seed)
    tile = Image.new("L", (tile_w, tile_h))
    tile_px = tile.load()
    for ty in range(tile_h):
        for tx in range(tile_w):
            tile_px[tx, ty] = min(180, max(86, int(133 + rng.gauss(0, lite_sigma))))
    gray = tile.resize((W, H), Image.BILINEAR)
    strength = Image.new("L", (W, H), lite_strength)  # ~39% grain strength
    strength_draw = ImageDraw.Draw(strength)
    strength_draw.rectangle([0, 195, W, 260], fill=0)    # context line
    strength_draw.rectangle([0, 1790, W, H], fill=0)     # provenance line
    grain_layer = Image.merge("RGB", (gray, gray, gray)).convert("RGBA")
    grain_layer.putalpha(strength)
    rgba = Image.alpha_composite(rgba, grain_layer)
    return rgba.convert("RGB")


try:
    from apps.studio_templates.detailing import (
        corner_marks,
        hairline_rule,
        perforation,
        pinstripes,
        tick_ruler,
    )
except ImportError:  # direct script run: python apps/studio_templates/redesign_mr02_skill.py
    from detailing import (  # type: ignore[no-redef]
        corner_marks,
        hairline_rule,
        perforation,
        pinstripes,
        tick_ruler,
    )


def apply_mr02_detailing(img: Image.Image, seed: int = 21) -> Image.Image:
    """emil-design-eng detailing on the lite pass: unseen details compound.

    Only non-data details (rule: details never carry data). The card's real
    slots are all displayed already, so no micro-label is added — restraint
    is the point.
    """
    work = img.convert("RGB")
    draw = ImageDraw.Draw(work)
    # Technical framing of the winner field.
    corner_marks(draw, (48, 160, 1032, 1072), INK)
    # Notched trim under the loser name zone.
    hairline_rule(draw, MARGIN, 620, 1700, SLATE)
    # Ticket perforation above provenance.
    perforation(draw, MARGIN, W - MARGIN, 1748, MIST)
    # Texture rhythm on the loser edge + air in the right void.
    tick_ruler(draw, 40, 1180, 1700, 52, SLATE)
    work = pinstripes(work, (640, 1200, 1004, 1700), SLATE, 14, 34, seed)
    return work


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Same data slots as the locked MR-02 starter (build_starters.py).
    new = render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay • Hàng Đẫy")
    new_path = OUT_DIR / "mr02-redesign-proof.png"
    new.save(new_path)
    deep = render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay • Hàng Đẫy",
                           depth=True, seed=7)
    deep_path = OUT_DIR / "mr02-depth-proof.png"
    deep.save(deep_path)
    lite = render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay • Hàng Đẫy",
                           depth="lite", seed=7)
    lite_path = OUT_DIR / "mr02-depth-lite-proof.png"
    lite.save(lite_path)
    detail = apply_mr02_detailing(lite)
    detail_path = OUT_DIR / "mr02-detail-proof.png"
    detail.save(detail_path)
    original = Image.open(ORIGINAL).convert("RGB")
    scale = 880 / H
    side_w = int(W * scale)
    panels = [original.resize((side_w, 880)), new.resize((side_w, 880)),
              lite.resize((side_w, 880)), detail.resize((side_w, 880))]
    titles = ["ORIGINAL MR-02", "REDESIGN (skills)", "REDESIGN + LITE", "REDESIGN + DETAIL"]
    compare = Image.new("RGB", (side_w * 4 + 120, 960), (10, 12, 20))
    header = ImageDraw.Draw(compare)
    for i, (panel, title) in enumerate(zip(panels, titles)):
        x = i * (side_w + 40)
        compare.paste(panel, (x, 50))
        header.text((x + 20, 12), title, fill=CORAL if i == 3 else PAPER)
    compare.save(OUT_DIR / "mr02-compare.png")
    print(f"wrote {new_path}, {deep_path}, {lite_path}, {detail_path} + compare")


if __name__ == "__main__":
    main()
