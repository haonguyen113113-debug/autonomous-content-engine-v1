"""Broadcast detailing primitives for PIL plates (emil-design-eng: unseen details).

Micro-details that compound into televised craft: hairline rules with notch
cuts, tick rulers, ticket perforation, crop-mark corners, pinstripe air.
CPU-only, seeded, palette-parametrized. Two iron rules:

1. Details never carry data. Ticks, numbers-in-graphics, and scales are
   forbidden unless the values come from reviewed graphic_data — texture
   without numerals, or numerals only from real slots.
2. Details never move type, recolor text, or touch microcopy legibility.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent.parent
FONTS = ROOT / "template_foundation" / "templates" / "allen-knows-ball" / "9.0.0" / "resources" / "fonts"


def micro_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / "BeVietnamPro-Regular.ttf"), max(11, size))


def hairline_rule(draw: ImageDraw.ImageDraw, x0: int, x1: int, y: int,
                  color: tuple[int, int, int], notched: bool = True) -> None:
    """3px rule with 45-degree notch cuts at both ends (broadcast trim)."""
    draw.line([x0, y, x1, y], fill=color, width=3)
    if notched:
        for x_end, direction in ((x0, 1), (x1, -1)):
            draw.polygon([(x_end, y - 5), (x_end + 8 * direction, y - 5),
                          (x_end, y + 5)], fill=color)


def tick_ruler(draw: ImageDraw.ImageDraw, x: int, y_top: int, y_bottom: int,
               step: int, color: tuple[int, int, int]) -> None:
    """Texture ticks only — no numerals (numerals would fake a data scale)."""
    y = y_top
    index = 0
    while y <= y_bottom:
        length = 22 if index % 5 == 0 else 12
        draw.line([x, y, x + length, y], fill=color, width=3)
        y += step
        index += 1


def corner_marks(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int],
                 color: tuple[int, int, int], arm: int = 34, width: int = 4) -> None:
    """Crop-mark corners: technical framing without boxes or borders."""
    x0, y0, x1, y1 = box
    for cx, cy, dx, dy in ((x0, y0, 1, 1), (x1, y0, -1, 1),
                           (x0, y1, 1, -1), (x1, y1, -1, -1)):
        draw.line([cx, cy, cx + arm * dx, cy], fill=color, width=width)
        draw.line([cx, cy, cx, cy + arm * dy], fill=color, width=width)


def perforation(draw: ImageDraw.ImageDraw, x0: int, x1: int, y: int,
                color: tuple[int, int, int], gap: int = 26) -> None:
    """Ticket-perforation dot row: splits zones with rhythm, not lines."""
    x = x0
    while x <= x1:
        draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=color)
        x += gap


def pinstripes(base: Image.Image, region: tuple[int, int, int, int],
               color: tuple[int, int, int], alpha: int, spacing: int,
               seed: int) -> Image.Image:
    """Seeded diagonal pinstripes inside a dead zone (air, not objects)."""
    rng = random.Random(seed)
    x0, y0, x1, y1 = region
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    offset = rng.randint(0, spacing)
    x = x0 - (y1 - y0) + offset
    while x < x1:
        layer_draw.line([x, y0, x + (y1 - y0), y1], fill=color + (alpha,), width=2)
        x += spacing
    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).rectangle(region, fill=255)
    layer.putalpha(Image.composite(layer.split()[3], Image.new("L", base.size, 0), mask))
    return Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")


def stitch_line(draw: ImageDraw.ImageDraw, x0: int, x1: int, y: int,
                color: tuple[int, int, int]) -> None:
    """Stadium-hoarding stitch: rounded dashes that read as craft, not tech."""
    x = x0
    dash, gap = 18, 12
    while x < x1:
        draw.line([x, y, min(x + dash, x1), y], fill=color, width=4,
                  joint="curve")
        x += dash + gap


def micro_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
                color: tuple[int, int, int]) -> None:
    """Sentence-case microcopy in the whisper voice (never shouty caps)."""
    draw.text(xy, text, font=micro_font(30), fill=color)


def detail_report() -> list[dict[str, Any]]:
    """Machine-readable catalog of available primitives for planners."""
    return [
        {"primitive": "hairline_rule", "use": "trim under names/scores",
         "carries_data": False},
        {"primitive": "tick_ruler", "use": "texture rhythm on edges",
         "carries_data": False},
        {"primitive": "corner_marks", "use": "technical framing of hero field",
         "carries_data": False},
        {"primitive": "perforation", "use": "zone splits with rhythm",
         "carries_data": False},
        {"primitive": "pinstripes", "use": "air in dead zones (seeded)",
         "carries_data": False},
        {"primitive": "stitch_line", "use": "craft accent near motifs",
         "carries_data": False},
        {"primitive": "micro_label", "use": "whisper annotations, sentence case",
         "carries_data": False},
    ]
