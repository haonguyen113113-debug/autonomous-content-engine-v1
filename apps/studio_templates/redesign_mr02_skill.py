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

from PIL import Image, ImageDraw, ImageFont

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


def render_redesign(home: str, away: str, score: str, comp: str, when: str) -> Image.Image:
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
    draw.text((MARGIN - 8, 400), str(top_goals), font=font_numeral(560),
              fill=INK if draw_win else PAPER)    # Loser territory: dimmed numeral + name anchored together.
    draw.text((MARGIN, SPLIT_Y + 60), str(bottom_goals), font=font_numeral(280), fill=SLATE)
    draw.text((MARGIN, SPLIT_Y + 360), bottom_name, font=font_brand("display", 84), fill=PAPER)
    draw.text((W // 2, 1820), "Nguồn + ngày", font=font_brand("body", 36),
              fill=MIST, anchor="ma")
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Same data slots as the locked MR-02 starter (build_starters.py).
    new = render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay • Hàng Đẫy")
    new_path = OUT_DIR / "mr02-redesign-proof.png"
    new.save(new_path)
    original = Image.open(ORIGINAL).convert("RGB")
    scale = 880 / H
    side_w = int(W * scale)
    left = original.resize((side_w, 880))
    right = new.resize((side_w, 880))
    compare = Image.new("RGB", (side_w * 2 + 40, 960), (10, 12, 20))
    compare.paste(left, (0, 50))
    compare.paste(right, (side_w + 40, 50))
    header = ImageDraw.Draw(compare)
    header.text((20, 12), "ORIGINAL MR-02", fill=PAPER)
    header.text((side_w + 60, 12), "REDESIGN (skills)", fill=CORAL)
    compare.save(OUT_DIR / "mr02-compare.png")
    print(f"wrote {new_path} + compare")


if __name__ == "__main__":
    main()
