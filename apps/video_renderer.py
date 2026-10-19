from __future__ import annotations

"""Local FFmpeg renderer for a template motion preview and reviewed production runs."""

import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import unicodedata
import wave
from datetime import datetime, timezone
import textwrap
from typing import Any

from template_foundation import resolve_template


def _ffmpeg(root: Path) -> str:
    configured = os.environ.get("FFMPEG_PATH")
    if not configured:
        env_file = root / ".env"
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8-sig").splitlines():
                key, separator, value = line.partition("=")
                if separator and key.strip() == "FFMPEG_PATH":
                    configured = value.strip().strip("\"'")
                    break
    found = configured or shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("FFmpeg was not found. Install FFmpeg or set FFMPEG_PATH.")
    if not shutil.which(found) and not Path(found).is_file():
        raise RuntimeError(f"FFmpeg executable does not exist: {found}")
    return found


def _ffprobe(ffmpeg: str) -> str:
    configured = os.environ.get("FFPROBE_PATH")
    found = configured or shutil.which("ffprobe")
    if not found:
        sibling = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        found = str(sibling) if sibling.is_file() else None
    if not found:
        raise RuntimeError("FFprobe was not found. Install it with FFmpeg or set FFPROBE_PATH.")
    resolved = shutil.which(found) or (found if Path(found).is_file() else None)
    if not resolved:
        raise RuntimeError(f"FFprobe executable does not exist: {found}")
    return resolved


def _safe_run_id(value: str) -> bool:
    return len(value) == 12 and all(ch in "0123456789abcdef" for ch in value)


_STARTER_TACTICAL_RE = re.compile(r"TA-\d{2}")


def _write_starter_scene(scene_path: Path, card_id: str) -> None:
    """Render an authored Sprint 2 long-form plate (apps/studio_templates/TA-*.long.json).

    Raises ValueError for unknown ids or wrong canvases; callers fall back to
    the generic pitch plate so one bad id can never break a render.
    """
    from apps.studio_templates.render_starters import render_design

    if not _STARTER_TACTICAL_RE.fullmatch(card_id or ""):
        raise ValueError(f"Unknown tactical card: {card_id}")
    starter = Path(__file__).resolve().parents[0] / "studio_templates" / f"{card_id}.long.json"
    try:
        data = json.loads(starter.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Tactical card unreadable: {card_id}") from error
    image = render_design(data)
    if image.size != (1920, 1080):
        raise ValueError(f"Tactical card has wrong canvas: {card_id}")
    image.save(scene_path)


def _normalise(value: str) -> str:
    return unicodedata.normalize("NFC", str(value)).strip()


def _write_text(path: Path, text: str) -> str:
    # FFmpeg reads UTF-8 text files directly; this also avoids filter escaping issues.
    path.write_text(text, encoding="utf-8")
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def _hook_lines(hook_text: str, max_lines: int = 3) -> list[str]:
    """Balance a hook claim into at most max_lines lines for staggered reveals."""
    words = " ".join(str(hook_text or "").replace("*", "").split())[:120].split() or ["CÂU HỎI TRẬN ĐẤU"]
    if len(words) <= max_lines:
        return [" ".join(words)] if len(words) == 1 else words[:max_lines]
    total = sum(len(word) for word in words)
    lines: list[str] = []
    current = ""
    target = total / max_lines
    current_len = 0
    for word in words:
        if current and current_len + len(word) > target and len(lines) < max_lines - 1:
            lines.append(current)
            current, current_len = word, len(word)
        else:
            current = f"{current} {word}".strip()
            current_len += len(word)
    if current:
        lines.append(current)
    return lines[:max_lines]


def _count_steps(value: str, steps: int = 6) -> list[str]:
    """Interpolate a leading number from zero; non-numeric values stay static.

    Only animates reviewed values; Vietnamese decimal commas are preserved.
    """
    text = str(value or "").strip()
    match = re.match(r"(\d+(?:[.,]\d+)?)(.*)$", text, re.DOTALL)
    if not match:
        return [text or "—"]
    raw_number, suffix = match.groups()
    decimals = len(raw_number.split(",")[1]) if "," in raw_number else (
        len(raw_number.split(".")[1]) if "." in raw_number else 0)
    try:
        target = float(raw_number.replace(",", "."))
    except ValueError:
        return [text]
    if target <= 0:
        return [text]
    out = []
    for step in range(1, steps + 1):
        reached = target * step / steps
        if decimals:
            rendered = f"{reached:.{decimals}f}".replace(".", ",")
        else:
            rendered = str(round(reached))
        out.append(f"{rendered}{suffix}")
    return out


def _spotlight(image: Any, cx: float, cy: float, radius: float,
               color: tuple[int, int, int] = (232, 199, 90), max_alpha: int = 70) -> None:
    """Faux-3D key light: radial glow behind the focal point, under later shapes."""
    from PIL import Image as _Image, ImageDraw as _Draw

    layer = _Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay = _Draw.Draw(layer)
    steps = max(8, round(radius / 24))
    for i in range(steps, 0, -1):
        circle = radius * i / steps
        alpha = round(max_alpha * (1 - i / (steps + 1)))
        overlay.ellipse((cx - circle, cy - circle, cx + circle, cy + circle),
                        fill=color + (alpha,))
    image.alpha_composite(layer)


def _extrude(draw: Any, xy: tuple[float, float], text: str, font: Any,
             fill: tuple[int, int, int, int], depth: int = 6,
             shadow: tuple[int, int, int, int] = (0, 0, 0, 220)) -> None:
    """Faux-3D type: dark offset stack behind the final face color."""
    x, y = xy
    for step in range(depth, 0, -1):
        draw.text((x + step, y + step), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)


def _vignette(image: Any, strength: int = 44) -> None:
    """Darken plate edges so the focal area carries the eye."""
    from PIL import Image as _Image, ImageDraw as _Draw

    width, height = image.size
    layer = _Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay = _Draw.Draw(layer)
    for x in range(width):
        alpha = round(strength * max(0.0, 1.0 - min(x, width - 1 - x) / (width * 0.12)))
        if alpha:
            overlay.line((x, 0, x, height), fill=(0, 0, 0, alpha))
    for y in range(height):
        alpha = round(strength * max(0.0, 1.0 - min(y, height - 1 - y) / (height * 0.12)))
        if alpha:
            overlay.line((0, y, width, y), fill=(0, 0, 0, alpha))
    image.alpha_composite(layer)


def _gradient_rounded(image: Any, box: tuple[float, float, float, float], radius: int,
                      top: tuple[int, int, int, int],
                      bottom: tuple[int, int, int, int],
                      axis: str = "vertical") -> None:
    """Gradient fill clipped to a rounded rectangle (glassy bars).

    axis="vertical" blends top→bottom, "horizontal" blends left→right.
    """
    from PIL import Image as _Image, ImageDraw as _Draw

    x1, y1, x2, y2 = (round(value) for value in box)
    width, height = max(1, x2 - x1), max(1, y2 - y1)
    gradient = _Image.new("RGBA", (width, height))
    painter = _Draw.Draw(gradient)
    span = max(1, (height - 1) if axis == "vertical" else (width - 1))
    if axis == "vertical":
        for row in range(height):
            blend = row / span
            painter.line((0, row, width, row), fill=tuple(
                round(top[i] + (bottom[i] - top[i]) * blend) for i in range(3)) + (255,))
    else:
        for col in range(width):
            blend = col / span
            painter.line((col, 0, col, height), fill=tuple(
                round(top[i] + (bottom[i] - top[i]) * blend) for i in range(3)) + (255,))
    mask = _Image.new("L", (width, height), 0)
    _Draw.Draw(mask).rounded_rectangle((0, 0, width, height), radius=radius, fill=255)
    image.paste(gradient, (x1, y1), mask)


def _reflection(image: Any, box: tuple[float, float, float, float],
                gap: int = 10, height: int = 130, alpha: int = 60) -> None:
    """Faux-3D floor: faded flipped copy of a region, pasted below it."""
    from PIL import Image as _Image

    x1, y1, x2, y2 = (round(value) for value in box)
    region = image.crop((x1, y1, x2, min(y2, image.height))).transpose(_Image.FLIP_TOP_BOTTOM)
    region = region.resize((x2 - x1, height))
    fade = _Image.new("L", region.size, 0)
    for row in range(height):
        fade.paste(round(alpha * (1 - row / max(1, height - 1))),
                   (0, row, region.width, row + 1))
    region.putalpha(fade)
    image.alpha_composite(region, (x1, y2 + gap))


def _accent_split(text: str) -> list[tuple[str, bool]]:
    """Split *accent* markup into (segment, is_accent) pieces."""
    parts = re.split(r"\*([^*]+)\*", str(text or ""))
    out: list[tuple[str, bool]] = []
    for index, part in enumerate(parts):
        if part:
            out.append((part, index % 2 == 1))
    return out or [(str(text or ""), False)]


# Design-system unit: every margin/gap is a multiple of U (panel pixels).
U = 12


def _role_size(panel_h: int, role: str) -> int:
    """Type scale with exactly three roles per frame."""
    if role == "boss":
        return round(panel_h * 0.078)
    if role == "support":
        return round(panel_h * 0.024)
    return round(panel_h * 0.012)


def _phrase_lines(text: str, max_lines: int = 3) -> list[str]:
    """Semantic line breaks: explicit `/` wins; else keep phrases together and
    never strand a tiny word alone on the last line."""
    clean = " ".join(str(text or "").replace("*", "").split())[:140]
    if not clean:
        return []
    forced = [part.strip() for part in clean.split("/") if part.strip()]
    if len(forced) > 1:
        return forced[:max_lines]
    words = clean.split()
    if len(words) <= max_lines:
        return [" ".join(words)] if len(words) == 1 else [" ".join(words)]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(lines) < max_lines - 1 and len(candidate) > len(clean) // max_lines + 8:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    lines = lines[:max_lines]
    if len(lines) > 1 and len(lines[-1].split()) == 1 and len(lines[-1]) <= 4:
        lines[-2] = f"{lines[-2]} {lines[-1]}"
        lines.pop()
    return lines


def _luminance(color: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        value /= 255.0
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    red, green, blue = (channel(component) for component in color[:3])
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast_ratio(foreground: tuple[int, int, int], background: tuple[int, int, int]) -> float:
    lighter = max(_luminance(foreground), _luminance(background))
    darker = min(_luminance(foreground), _luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def _ensure_contrast(draw: Any, image: Any, box: tuple[float, float, float, float],
                     text_fill: tuple[int, int, int, int], minimum: float = 4.5) -> bool:
    """Sample the plate behind a text box; lay a scrim pill when ratio fails."""
    from PIL import Image as _Image

    x1, y1, x2, y2 = (round(value) for value in box)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(image.width, x2), min(image.height, y2)
    if x2 <= x1 or y2 <= y1:
        return False
    crop = image.crop((x1, y1, x2, y2)).convert("RGB").resize((8, 8))
    from PIL import ImageStat
    means = ImageStat.Stat(crop).mean
    background = (round(means[0]), round(means[1]), round(means[2]))
    if _contrast_ratio(text_fill[:3], background) >= minimum:
        return False
    scrim = _Image.new("RGBA", image.size, (0, 0, 0, 0))
    from PIL import ImageDraw as _Draw
    pad = U * 2
    _Draw.Draw(scrim).rounded_rectangle((x1 - pad, y1 - pad, x2 + pad, y2 + pad),
                                       radius=pad, fill=(4, 7, 6, 150))
    image.alpha_composite(scrim)
    return True


def _accent_line(draw: Any, x_center: float, y: float, text: str, font: Any,
                 plain: tuple[int, int, int, int], accent: tuple[int, int, int, int],
                 depth: int = 0) -> int:
    """Centered line with *accent* words; returns rendered line height."""
    segments = _accent_split(text)
    widths = [draw.textbbox((0, 0), part, font=font)[2] for part, _ in segments]
    x = x_center - sum(widths) / 2
    for (part, is_acc), width in zip(segments, widths):
        fill = accent if is_acc else plain
        if depth > 0:
            _extrude(draw, (x, y), part, font, fill, depth=depth)
        else:
            draw.text((x, y), part, font=font, fill=fill)
        x += width
    bounds = draw.textbbox((0, 0), str(text).replace("*", ""), font=font)
    return bounds[3] - bounds[1]


def _wave_field(image: Any, panel_w: int, panel_h: int, scale: int,
                ink: tuple[int, int, int, int], deep: tuple[int, int, int, int],
                phase: float = 0.0) -> None:
    """Neon Grid bed: abyss gradient, running data streams, wireframe floor."""
    from PIL import ImageDraw as _Draw

    width, height = panel_w * scale, panel_h * scale
    draw = _Draw.Draw(image, "RGBA")
    for row in range(height):
        blend = row / max(1, height - 1)
        draw.line((0, row, width, row), fill=tuple(
            round(ink[i] + (deep[i] - ink[i]) * blend) for i in range(3)) + (255,))
    streams = [
        ((57, 255, 136), 0.30, 46, 0.0),
        ((0, 229, 255), 0.38, 60, 2.1),
        ((255, 47, 179), 0.62, 38, 4.2),
    ]
    stream_alpha = 150
    from math import pi, sin
    for color, vpos, amplitude, offset in streams:
        base = height * vpos
        wavelength = max(60, width / 2)
        previous: tuple[float, float] | None = None
        x = 0
        while x <= width:
            y = base + amplitude * scale * sin(2 * pi * x / (wavelength * scale) + phase + offset)
            if previous is not None:
                draw.line((previous[0], previous[1], x, y),
                          fill=color + (stream_alpha,), width=max(2, 2 * scale))
            previous = (x, y)
            x += 4 * scale
    floor_top = height * 0.80
    for index in range(9):
        across = width * (0.5 + (index - 4) * 0.22)
        draw.line((width / 2, floor_top, across, height),
                  fill=(91, 74, 138, 90), width=max(1, scale // 2))
    row = 0
    while True:
        y = floor_top + row * row * scale
        if y > height:
            break
        draw.line((0, y, width, y), fill=(91, 74, 138, 80), width=max(1, scale // 2))
        row += 1


def _neon_rect(draw: Any, box: tuple[float, float, float, float], radius: int,
               color: tuple[int, int, int, int], scale: int) -> None:
    """Neon tube: soft halo, hot tube, bright core."""
    light = tuple(min(255, component + 110) for component in color[:3]) + (255,)
    draw.rounded_rectangle(box, radius=radius, outline=color[:3] + (64,), width=9 * scale)
    draw.rounded_rectangle(box, radius=radius, outline=color[:3] + (170,), width=4 * scale)
    draw.rounded_rectangle(box, radius=radius, outline=light, width=2 * scale)


def _painted_pitch_frame(draw: Any, fx: float, fy: float, fw: float, fh: float,
                         scale: int, line: tuple[int, int, int, int]) -> None:
    """Hand-painted chalk frame: bold outer line plus a thin inner echo."""
    draw.rectangle((fx * scale, fy * scale, (fx + fw) * scale, (fy + fh) * scale),
                   outline=line, width=max(2, 3 * scale))
    draw.rectangle(((fx + 5) * scale, (fy + 5) * scale,
                    (fx + fw - 5) * scale, (fy + fh - 5) * scale),
                   outline=line[:3] + (110,), width=max(1, scale // 2))


def _photo_bed(image: Any, photo_path: Any, panel_w: int, panel_h: int,
               scale: int, darken: int = 125) -> bool:
    """Paste a photographic bed under authored type (cover-crop, darkened).

    Drops the bottom strip where generator watermarks usually sit. Returns
    False when the photo is missing or unreadable so callers keep the
    procedural field.
    """
    from PIL import Image as _Image, ImageDraw as _Draw

    try:
        photo = _Image.open(photo_path).convert("RGB")
    except (OSError, ValueError):
        return False
    width, height = photo.size
    height = round(height * 0.93)
    photo = photo.crop((0, 0, width, height))
    target = panel_w / panel_h
    if width / height > target:
        new_width = round(height * target)
        left = (width - new_width) // 2
        photo = photo.crop((left, 0, left + new_width, height))
    else:
        new_height = round(width / target)
        top = (height - new_height) // 2
        photo = photo.crop((0, top, width, top + new_height))
    photo = photo.resize((panel_w * scale, panel_h * scale),
                         _Image.Resampling.LANCZOS).convert("RGBA")
    image.alpha_composite(photo)
    shade = _Image.new("RGBA", image.size, (0, 0, 0, 0))
    _Draw.Draw(shade).rectangle((0, 0) + image.size, fill=(5, 8, 7, darken))
    image.alpha_composite(shade)
    return True


def _sprite(image: Any, sprite_path: Any, center: tuple[float, float],
            size: int, tint: tuple[int, int, int] = (255, 255, 255),
            opacity: int = 200) -> bool:
    """Composite a tinted CC0 kit sprite (flare, glow, smoke, spark).

    Missing files are skipped so plates degrade to procedural finish.
    """
    from PIL import Image as _Image

    try:
        sprite = _Image.open(sprite_path).convert("RGBA")
    except (OSError, ValueError):
        return False
    sprite = sprite.resize((max(1, size), max(1, size)))
    colored = _Image.new("RGBA", sprite.size, tint + (255,))
    alpha = sprite.split()[-1].point(lambda value: round(value * opacity / 255))
    colored.putalpha(alpha)
    image.alpha_composite(colored, (round(center[0] - size / 2), round(center[1] - size / 2)))
    return True


def _kit(sprite_name: str, font_path: Any) -> Any:
    """Resolve a kit sprite next to the template fonts; may not exist."""
    from pathlib import Path

    return Path(font_path).parent.parent / "kit" / sprite_name


def _night_field(image: Any, panel_w: int, panel_h: int, scale: int,
                 ink: tuple[int, int, int, int], deep: tuple[int, int, int, int],
                 phase: float = 0.0) -> None:
    """San Dem bed: asphalt gradient, floodlight cones, bokeh, concrete grain."""
    from PIL import Image as _Image, ImageDraw as _Draw
    import random

    width, height = panel_w * scale, panel_h * scale
    draw = _Draw.Draw(image, "RGBA")
    for row in range(height):
        blend = row / max(1, height - 1)
        draw.line((0, row, width, row), fill=tuple(
            round(ink[i] + (deep[i] - ink[i]) * blend) for i in range(3)) + (255,))
    # NOTE: ImageDraw does not alpha-blend onto RGBA images (it overwrites),
    # so translucent cones must be drawn on a layer and composited.
    from PIL import ImageFilter
    cones = _Image.new("RGBA", (width, height), (0, 0, 0, 0))
    cone_draw = _Draw.Draw(cones)
    for cx, direction in ((width * 0.16, 1), (width * 0.84, -1)):
        cone_draw.polygon([(cx, 0), (cx + direction * width * 0.30, height),
                           (cx + direction * width * 0.07, height)],
                          fill=(255, 179, 0, 14))
        cone_draw.polygon([(cx, 0), (cx + direction * width * 0.20, height),
                           (cx + direction * width * 0.04, height)],
                          fill=(255, 240, 200, 12))
    image.alpha_composite(cones.filter(ImageFilter.GaussianBlur(max(8, 12 * scale))))
    rng = random.Random(7)
    for _ in range(6):
        x = rng.uniform(0, width)
        y = rng.uniform(height * 0.06, height * 0.92)
        radius = rng.uniform(20, 42) * scale
        draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                     fill=(255, 214, 140, rng.randint(10, 20)))
    for _ in range(14):
        x = rng.uniform(0, width)
        y = rng.uniform(height * 0.06, height * 0.92)
        radius = rng.uniform(5, 13) * scale
        draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                     fill=(255, 214, 140, rng.randint(25, 55)))
    for _ in range(420):
        x = rng.uniform(0, width)
        y = rng.uniform(0, height)
        draw.point((x, y), fill=(232, 228, 218, 10))


def _tick_ruler(draw: Any, x: float, y: float, width: float,
                color: tuple[int, int, int, int], scale: int) -> None:
    """Broadcast tick ruler: baseline with tall ticks every fifth mark."""
    draw.line((x, y, x + width, y), fill=color, width=max(1, scale // 2))
    step = 14 * scale
    tick = 0
    cursor = x
    while cursor <= x + width:
        tall = tick % 5 == 0
        height = (10 if tall else 5) * scale
        draw.line((cursor, y - height, cursor, y), fill=color,
                  width=(2 * scale if tall else scale))
        cursor += step
        tick += 1


def _notch_rect(draw: Any, box: tuple[float, float, float, float], cut: int,
                fill: Any, outline: Any = None, width: int = 1) -> None:
    """Card with one clipped corner (broadcast stat-card grammar)."""
    x1, y1, x2, y2 = box
    draw.polygon([(x1, y1), (x2 - cut, y1), (x2, y1 + cut), (x2, y2), (x1, y2)],
                 fill=fill, outline=outline, width=width)


def _ticket_cut(draw: Any, width: int, y: float, scale: int,
                hole: tuple[int, int, int, int]) -> None:

    """Perforated ticket divider: dashed rule punched with holes."""
    draw.line((0, y, width, y), fill=(232, 228, 218, 70), width=max(1, scale // 2))
    x = 12 * scale
    while x < width - 8 * scale:
        draw.ellipse((x, y - 4 * scale, x + 8 * scale, y + 4 * scale), fill=hole)
        x += 26 * scale


def _draw_vector_arrow(draw: Any, start: tuple[int, int], end: tuple[int, int], color: tuple[int, int, int, int], *, dashed: bool, width: int) -> None:
    from math import atan2, cos, pi, sin

    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    length = max(1.0, (dx * dx + dy * dy) ** 0.5)
    ux, uy = dx / length, dy / length
    head_len = max(16, width * 4)
    shaft_end = (int(x2 - ux * head_len * 0.7), int(y2 - uy * head_len * 0.7))
    if dashed:
        dash, gap = max(10, width * 2), max(7, width)
        position = 0
        while position < length - head_len:
            stop = min(position + dash, length - head_len)
            draw.line(
                (int(x1 + ux * position), int(y1 + uy * position), int(x1 + ux * stop), int(y1 + uy * stop)),
                fill=color,
                width=width,
            )
            position += dash + gap
    else:
        draw.line((x1, y1, *shaft_end), fill=color, width=width)
    angle = atan2(dy, dx)
    left = (int(x2 - head_len * cos(angle - pi / 6)), int(y2 - head_len * sin(angle - pi / 6)))
    right = (int(x2 - head_len * cos(angle + pi / 6)), int(y2 - head_len * sin(angle + pi / 6)))
    draw.polygon((end, left, right), fill=color)


def _diagram_specs() -> list[dict[str, Any]]:
    """Small fallback storyboard for template previews without authored diagrams."""
    common = [
        {"id": "1", "team": "possession", "x": 0.12, "y": 0.54},
        {"id": "2", "team": "possession", "x": 0.32, "y": 0.34},
        {"id": "3", "team": "possession", "x": 0.48, "y": 0.60},
        {"id": "4", "team": "possession", "x": 0.72, "y": 0.40},
        {"id": "5", "team": "press", "x": 0.25, "y": 0.51},
        {"id": "6", "team": "press", "x": 0.45, "y": 0.37},
        {"id": "7", "team": "press", "x": 0.65, "y": 0.49},
    ]
    return [
        {
            "players": common,
            "highlight_player_id": "3",
            "pass_vector": {"from": [0.12, 0.54], "to": [0.32, 0.34]},
            "run_vectors": [{"from": [0.48, 0.60], "to": [0.66, 0.38]}],
            "press_vectors": [{"from": [0.25, 0.51], "to": [0.12, 0.54]}],
        },
        {
            "players": [dict(p, x=min(0.90, p["x"] + 0.06)) for p in common],
            "highlight_player_id": "6",
            "pass_vector": {"from": [0.32, 0.34], "to": [0.21, 0.57]},
            "run_vectors": [{"from": [0.48, 0.60], "to": [0.65, 0.41]}],
            "press_vectors": [{"from": [0.45, 0.37], "to": [0.32, 0.34]}],
        },
        {
            "players": [dict(p, y=max(0.12, p["y"] - 0.04)) for p in common],
            "highlight_player_id": "4",
            "pass_vector": {"from": [0.21, 0.57], "to": [0.62, 0.35]},
            "run_vectors": [{"from": [0.65, 0.41], "to": [0.82, 0.28]}],
            "press_vectors": [{"from": [0.65, 0.45], "to": [0.62, 0.35]}],
        },
    ]


def _write_tactical_scene(
    path: Path,
    *,
    width: int,
    height: int,
    font_path: Path,
    display_font_path: Path,
    palette: dict[str, str],
    spec: dict[str, Any],
    is_long: bool = False,
    scene_number: int = 1,
    scene_count: int = 1,
) -> None:
    """Rasterize an editorial match-analysis plate for a timed story beat.

    The composition borrows broadly from illustrated football explainers and
    match-analysis telestration: one clear tactical claim, a field as evidence,
    and sparse editorial labels. It does not reproduce another channel's art.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as error:
        raise RuntimeError("Tactical diagrams require Pillow. Install requirements-renderer.txt.") from error

    scale = 2
    panel_w, panel_h = (1540, 840) if is_long else (1080, 1920)
    image = Image.new("RGBA", (panel_w * scale, panel_h * scale), (10, 15, 13, 255))
    _night_field(image, panel_w, panel_h, scale, (10, 15, 13, 255), (18, 33, 27, 255),
                 phase=scene_number * 1.1)
    draw = ImageDraw.Draw(image, "RGBA")

    def rgba(name: str, alpha: int = 255) -> tuple[int, int, int, int]:
        raw = str(palette.get(name, "#F4F3E9")).lstrip("#")
        return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)

    def box(coords: tuple[float, float, float, float], radius: int, fill: tuple[int, int, int, int], outline: tuple[int, int, int, int] | None = None, line: int = 1) -> None:
        draw.rounded_rectangle(tuple(round(v * scale) for v in coords), radius=radius * scale, fill=fill, outline=outline, width=line * scale)

    ink = rgba("ink", 246)
    line = rgba("chalk", 185)
    lime = rgba("signal_lime")
    orange = rgba("signal_orange")
    chalk = rgba("chalk")
    muted = rgba("muted")

    # Portrait pitch in short-form and a wide pitch in long-form. The reserved
    # side rail supplies hierarchy and breathing room around the evidence.
    fx, fy, fw, fh = (505, 138, 865, 560) if is_long else (260, 142, 490, 760)
    lw = 2 * scale
    draw.rectangle((fx * scale, fy * scale, (fx + fw) * scale, (fy + fh) * scale), fill=rgba("deep_pitch", 238))
    if is_long:
        band = fw / 10
        for stripe in range(10):
            if stripe % 2 == 0:
                x1, x2 = fx + stripe * band, fx + (stripe + 1) * band
                draw.rectangle((x1*scale,fy*scale,x2*scale,(fy+fh)*scale),fill=(0,0,0,42))
    else:
        band = fh / 10
        for stripe in range(10):
            if stripe % 2 == 0:
                y1, y2 = fy + stripe * band, fy + (stripe + 1) * band
                draw.rectangle((fx*scale,y1*scale,(fx+fw)*scale,y2*scale),fill=(0,0,0,42))
    _painted_pitch_frame(draw, fx, fy, fw, fh, scale, line)
    mid_x, mid_y = fx + fw / 2, fy + fh / 2
    if is_long:
        draw.line((mid_x * scale, fy * scale, mid_x * scale, (fy + fh) * scale), fill=line, width=lw)
    else:
        draw.line((fx * scale, mid_y * scale, (fx + fw) * scale, mid_y * scale), fill=line, width=lw)
    center_r = (fh * 9.15 / 68) if is_long else (fw * 9.15 / 68)
    draw.ellipse(((mid_x-center_r)*scale, (mid_y-center_r)*scale, (mid_x+center_r)*scale, (mid_y+center_r)*scale), outline=line, width=lw)
    spot_r = 4 * scale
    draw.ellipse(((mid_x-spot_r/scale)*scale, (mid_y-spot_r/scale)*scale, (mid_x+spot_r/scale)*scale, (mid_y+spot_r/scale)*scale), fill=line)
    if is_long:
        area_h = fh * 40.32 / 68
        area_y1, area_y2 = mid_y - area_h / 2, mid_y + area_h / 2
        pa_depth, six_depth = fw * 16.5 / 105, fw * 5.5 / 105
        six_h = fh * 18.32 / 68
        six_y1, six_y2 = mid_y - six_h / 2, mid_y + six_h / 2
        draw.rectangle((fx*scale, area_y1*scale, (fx+pa_depth)*scale, area_y2*scale), outline=line, width=lw)
        draw.rectangle(((fx+fw-pa_depth)*scale, area_y1*scale, (fx+fw)*scale, area_y2*scale), outline=line, width=lw)
        draw.rectangle((fx*scale, six_y1*scale, (fx+six_depth)*scale, six_y2*scale), outline=line, width=lw)
        draw.rectangle(((fx+fw-six_depth)*scale, six_y1*scale, (fx+fw)*scale, six_y2*scale), outline=line, width=lw)
        pen_dist = fw * 11 / 105
        pen_centers = [(fx+pen_dist, mid_y), (fx+fw-pen_dist, mid_y)]
        arc_r = fh * 9.15 / 68
        arc_specs = [
            ((fx+pen_dist-arc_r,mid_y-arc_r,fx+pen_dist+arc_r,mid_y+arc_r),305,55),
            ((fx+fw-pen_dist-arc_r,mid_y-arc_r,fx+fw-pen_dist+arc_r,mid_y+arc_r),125,235),
        ]
    else:
        area_w = fw * 40.32 / 68
        area_x1, area_x2 = mid_x - area_w / 2, mid_x + area_w / 2
        pa_depth, six_depth = fh * 16.5 / 105, fh * 5.5 / 105
        six_w = fw * 18.32 / 68
        six_x1, six_x2 = mid_x - six_w / 2, mid_x + six_w / 2
        draw.rectangle((area_x1*scale, fy*scale, area_x2*scale, (fy+pa_depth)*scale), outline=line, width=lw)
        draw.rectangle((area_x1*scale, (fy+fh-pa_depth)*scale, area_x2*scale, (fy+fh)*scale), outline=line, width=lw)
        draw.rectangle((six_x1*scale, fy*scale, six_x2*scale, (fy+six_depth)*scale), outline=line, width=lw)
        draw.rectangle((six_x1*scale, (fy+fh-six_depth)*scale, six_x2*scale, (fy+fh)*scale), outline=line, width=lw)
        pen_dist = fh * 11 / 105
        pen_centers = [(mid_x,fy+pen_dist),(mid_x,fy+fh-pen_dist)]
        arc_r = fh * 9.15 / 105
        arc_specs = [
            ((mid_x-arc_r,fy+pen_dist-arc_r,mid_x+arc_r,fy+pen_dist+arc_r),35,145),
            ((mid_x-arc_r,fy+fh-pen_dist-arc_r,mid_x+arc_r,fy+fh-pen_dist+arc_r),215,325),
        ]
    for px, py in pen_centers:
        draw.ellipse(((px*scale)-spot_r,(py*scale)-spot_r,(px*scale)+spot_r,(py*scale)+spot_r), fill=line)
    for rect, start_angle, end_angle in arc_specs:
        draw.arc(tuple(value*scale for value in rect), start=start_angle, end=end_angle, fill=line, width=lw)
    corner_r = fw * 1 / (105 if is_long else 68)
    draw.arc(((fx-corner_r)*scale, (fy-corner_r)*scale, (fx+corner_r)*scale, (fy+corner_r)*scale), start=0, end=90, fill=line, width=lw)
    draw.arc(((fx+fw-corner_r)*scale, (fy-corner_r)*scale, (fx+fw+corner_r)*scale, (fy+corner_r)*scale), start=90, end=180, fill=line, width=lw)
    draw.arc(((fx-corner_r)*scale, (fy+fh-corner_r)*scale, (fx+corner_r)*scale, (fy+fh+corner_r)*scale), start=270, end=360, fill=line, width=lw)
    draw.arc(((fx+fw-corner_r)*scale, (fy+fh-corner_r)*scale, (fx+fw+corner_r)*scale, (fy+fh+corner_r)*scale), start=180, end=270, fill=line, width=lw)

    def point(value: list[float] | tuple[float, float]) -> tuple[int, int]:
        if is_long:
            return round((fx+float(value[0])*fw)*scale), round((fy+float(value[1])*fh)*scale)
        return round((fx+float(value[1])*fw)*scale), round((fy+(1-float(value[0]))*fh)*scale)

    pass_vector = spec.get("pass_vector", {})
    for zone in spec.get("zones", []) or []:
        zone_points = zone.get("points", []) if isinstance(zone, dict) else []
        if len(zone_points) >= 3:
            flat = [point(value) for value in zone_points]
            zone_tint = rgba("team_home") if (zone.get("side") if isinstance(zone, dict) else None) != "away" else rgba("team_away")
            draw.polygon(flat, fill=zone_tint[:3] + (40,))
            draw.line(flat + [flat[0]], fill=zone_tint[:3] + (210,), width=3 * scale)
    if pass_vector.get("from") and pass_vector.get("to"):
        _draw_vector_arrow(draw, point(pass_vector["from"]), point(pass_vector["to"]), lime, dashed=False, width=4 * scale)
    for vector in spec.get("run_vectors", []):
        _draw_vector_arrow(draw, point(vector["from"]), point(vector["to"]), chalk, dashed=True, width=3 * scale)
    for vector in spec.get("press_vectors", []):
        _draw_vector_arrow(draw, point(vector["from"]), point(vector["to"]), orange, dashed=True, width=3 * scale)

    header_font = ImageFont.truetype(str(font_path), 15 * scale)
    small_font = ImageFont.truetype(str(font_path), 12 * scale)
    players = spec.get("players", [])
    highlighted_player = str(spec.get("highlight_player_id", ""))
    if highlighted_player:
        focus_y = 554 if is_long else 820
        draw.text((38*scale, focus_y*scale), f"#{highlighted_player}  ·  FOCUS", font=header_font, fill=lime)
    for player in players:
        if str(player.get("id", "")) == highlighted_player:
            hx, hy = point((player["x"],player["y"]))
            halo = 48 * scale
            draw.ellipse((hx-halo,hy-halo,hx+halo,hy+halo),fill=rgba("signal_lime",18),outline=lime,width=2*scale)
            # A small open notch makes the focus ring feel like a hand-placed
            # tactical annotation rather than a generic selection halo.
            draw.arc((hx-halo-6*scale,hy-halo-6*scale,hx+halo+6*scale,hy+halo+6*scale),start=210,end=280,fill=lime,width=2*scale)
    for player in players:
        cx, cy = point((player["x"], player["y"]))
        fill = rgba("team_home", 255) if player.get("team") == "possession" else rgba("team_away", 255)
        # Common analyst-board grammar: numbered kit markers, team-color
        # encoding, and a separate emphasis ring for the selected player.
        # Layer a deep drop shadow, double team ring, and compact shirt glyph
        # so the player token stays legible at phone scale without fake faces.
        is_focus = str(player.get("id", "")) == highlighted_player
        radius = (44 if is_focus else 37) * scale
        draw.ellipse((cx-radius-9*scale, cy-radius-9*scale, cx+radius+9*scale, cy+radius+9*scale), fill=fill[:3]+(40,))
        draw.ellipse((cx-radius+3*scale,cy-radius+6*scale,cx+radius+3*scale,cy+radius+6*scale), fill=rgba("ink",150))
        draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius), fill=fill, outline=chalk, width=3*scale)
        inner = radius - 7*scale
        draw.ellipse((cx-inner,cy-inner,cx+inner,cy+inner), fill=rgba("ink",235), outline=rgba("ink"), width=scale)
        shirt_w, shirt_h = (25 if is_focus else 21)*scale, (27 if is_focus else 23)*scale
        jersey = [
            (cx-shirt_w*.30,cy-shirt_h*.48),(cx-shirt_w*.78,cy-shirt_h*.25),
            (cx-shirt_w*1.05,cy-shirt_h*.02),(cx-shirt_w*.78,cy-shirt_h*.30),
            (cx-shirt_w*.57,cy-shirt_h*.20),(cx-shirt_w*.57,cy+shirt_h*.55),
            (cx+shirt_w*.57,cy+shirt_h*.55),(cx+shirt_w*.57,cy-shirt_h*.20),
            (cx+shirt_w*.78,cy-shirt_h*.30),(cx+shirt_w*1.05,cy-shirt_h*.02),
            (cx+shirt_w*.78,cy-shirt_h*.25),(cx+shirt_w*.30,cy-shirt_h*.48),
            (cx+shirt_w*.17,cy-shirt_h*.34),(cx-shirt_w*.17,cy-shirt_h*.34),
        ]
        draw.polygon(jersey, fill=chalk, outline=rgba("ink"))
        draw.line(jersey+[jersey[0]], fill=rgba("ink"), width=2*scale, joint="curve")
        # Team color remains visible in the badge ring and sleeve trim while
        # leaving the shirt-number area unobstructed.
        draw.line((cx-shirt_w*.72,cy-shirt_h*.17,cx-shirt_w*.51,cy+shirt_h*.17),fill=fill,width=3*scale)
        draw.line((cx+shirt_w*.72,cy-shirt_h*.17,cx+shirt_w*.51,cy+shirt_h*.17),fill=fill,width=3*scale)
        label = str(player.get("id", ""))
        number_font = ImageFont.truetype(str(display_font_path), (20 if is_focus else 18) * scale)
        draw.text((cx, cy+2*scale), label, font=number_font, fill=rgba("ink"), anchor="mm")
        role = str(player.get("role_label", "")).strip()
        if role:
            role_font = ImageFont.truetype(str(font_path), 9*scale)
            rb = draw.textbbox((0,0),role,font=role_font)
            rw = rb[2]-rb[0]+12*scale
            rx, ry = cx-rw//2, cy+radius-3*scale
            draw.rounded_rectangle((rx,ry,rx+rw,ry+18*scale),radius=8*scale,fill=rgba("ink",245),outline=fill,width=2*scale)
            draw.text((cx-(rb[2]-rb[0])/2,ry+1*scale),role,font=role_font,fill=chalk)

    # Legend also makes the two teams and the two movement-vector types legible.
    if highlighted_player:
        for player in players:
            if str(player.get("id", "")) == highlighted_player:
                focus = point((player["x"], player["y"]))
                _spotlight(image, focus[0], focus[1], 130 * scale, (232, 199, 90), 40)
                break
    legend_font = ImageFont.truetype(str(font_path), 12 * scale)
    legend_y = (758 if is_long else 1110) * scale
    draw.ellipse((32*scale, legend_y, 46*scale, legend_y+14*scale), fill=rgba("team_home"))
    draw.text((52*scale, (legend_y-2*scale)), "ĐỘI GIỮ BÓNG", font=legend_font, fill=rgba("team_home"))
    draw.ellipse((278*scale, legend_y, 292*scale, legend_y+14*scale), fill=rgba("team_away"))
    draw.text((298*scale, (legend_y-2*scale)), "ĐỘI PRESSING", font=legend_font, fill=rgba("team_away"))
    draw.line((520*scale, legend_y+7*scale, 558*scale, legend_y+7*scale), fill=lime, width=4*scale)
    draw.polygon(((558*scale, legend_y+1*scale),(570*scale,legend_y+7*scale),(558*scale,legend_y+13*scale)), fill=lime)
    draw.text((578*scale, legend_y-2*scale), "CHUYỀN BÓNG", font=legend_font, fill=chalk)

    _vignette(image)
    image.resize((panel_w, panel_h), Image.Resampling.LANCZOS).save(path)


def render_graphic_template_previews(root: Path) -> dict[str, Any]:
    """Create review PNGs with the same graphic renderer used in video."""
    from template_foundation import resolve_template

    outputs: dict[str, Any] = {}
    samples = {
        "statline-preview.png": ("statline_scorecard", {
            "headline": "CON SỐ KỂ CÂU CHUYỆN GÌ?",
            "teams": ["ĐỘI A · DEMO", "ĐỘI B · DEMO"],
            "metrics": [
                {"label": "Cơ hội rõ rệt", "home": "4", "away": "2"},
                {"label": "Sút trúng đích", "home": "6", "away": "3"},
                {"label": "Thu hồi bóng", "home": "11", "away": "14"},
            ],
            "source": "DỮ LIỆU MINH HỌA · KHÔNG PHẢI TRẬN THẬT", "date": "Bản demo",
        }),
        "chart-preview.png": ("chart_comparison", {
            "chart_type": "donut",
            "part_to_whole": True,
            "unit": "LƯỢT",
            "headline": "CƠ CẤU HƯỚNG TẤN CÔNG",
            "values": [
                {"label": "Trung lộ", "value": 48},
                {"label": "Cánh trái", "value": 32},
                {"label": "Cánh phải", "value": 20},
            ],
            "source": "DỮ LIỆU MINH HỌA · KHÔNG PHẢI TRẬN THẬT", "date": "Bản demo",
        }),
        "chart-bar-preview.png": ("chart_comparison", {
            "chart_type": "bar", "headline": "XẾP HẠNG THEO CHỈ SỐ",
            "values": [{"label":"Đội A","value":6},{"label":"Đội B","value":4},{"label":"Đội C","value":2}],
            "source":"DỮ LIỆU MINH HỌA · KHÔNG PHẢI TRẬN THẬT", "date":"Bản demo",
        }),
        "chart-column-preview.png": ("chart_comparison", {
            "chart_type": "column", "headline": "SO SÁNH SỐ CƠ HỘI",
            "values": [{"label":"Đội A","value":6},{"label":"Đội B","value":3},{"label":"Đội C","value":4}],
            "source":"DỮ LIỆU MINH HỌA · KHÔNG PHẢI TRẬN THẬT", "date":"Bản demo",
        }),
        "chart-pie-preview.png": ("chart_comparison", {
            "chart_type": "pie", "part_to_whole": True, "headline": "TỶ TRỌNG ĐƯỜNG TẤN CÔNG",
            "values": [{"label":"Trung lộ","value":48},{"label":"Cánh trái","value":32},{"label":"Cánh phải","value":20}],
            "source":"DỮ LIỆU MINH HỌA · KHÔNG PHẢI TRẬN THẬT", "date":"Bản demo",
        }),
        "chart-donut-preview.png": ("chart_comparison", {
            "chart_type": "donut", "part_to_whole": True, "unit":"LƯỢT",
            "headline": "CƠ CẤU HƯỚNG TẤN CÔNG",
            "values": [{"label":"Trung lộ","value":48},{"label":"Cánh trái","value":32},{"label":"Cánh phải","value":20}],
            "source":"DỮ LIỆU MINH HỌA · KHÔNG PHẢI TRẬN THẬT", "date":"Bản demo",
        }),
        "chart-line-preview.png": ("chart_timeline", {
            "chart_type":"line", "headline":"NHỊP TẤN CÔNG THEO TRẬN",
            "values":[{"label":"T10","value":2},{"label":"T25","value":5},{"label":"THT","value":3},{"label":"T70","value":7},{"label":"T90","value":4}],
            "source":"DỮ LIỆU MINH HỌA · KHÔNG PHẢI TRẬN THẬT", "date":"Bản demo",
        }),
        "source-preview.png": ("source_card", {
            "headline": "LUẬN ĐIỂM CẦN CÓ NGUỒN",
            "source": "Nguồn ví dụ · không phải trích dẫn thật", "date": "Ngày cần xác minh",
            "claim": "Thẻ này cho thấy cách luận điểm, ngày xuất bản và xuất xứ sẽ xuất hiện cạnh nhau khi nội dung thật được duyệt.",
            "url": "example.invalid · placeholder",
        }),
        "hook-card-preview.png": ("hook_card", {
            "hook_text": "Ai đang đọc trận đấu hay nhất?",
        }),
        "hero-preview.png": ("statline_scorecard", {
            "hero": {"label": "BÀN THẮNG QUYẾT ĐỊNH", "value": "19"},
            "source": "DỮ LIỆU MINH HỌA · KHÔNG PHẢI TRẬN THẬT", "date": "Bản demo",
        }),
    }
    for template_id, prefix, is_long in (
        ("allen-knows-ball.shortform-analyst", "short", False),
        ("allen-knows-ball.longform-analyst", "long", True),
    ):
        package = resolve_template(root, template_id, allow_draft=True)
        out_dir = package.root / "previews"
        out_dir.mkdir(parents=True, exist_ok=True)
        for filename, (mode, data) in samples.items():
            # Pair the primary chart card with its aspect ratio; the full
            # chart-family strip below still shows every supported geometry.
            if filename == "chart-preview.png" and not is_long:
                data = {
                    "chart_type": "column", "headline": "SO SÁNH SỐ CƠ HỘI",
                    "values": [{"label":"Đội A","value":6},{"label":"Đội B","value":3},{"label":"Đội C","value":4}],
                    "source": "DỮ LIỆU MINH HỌA · KHÔNG PHẢI TRẬN THẬT", "date": "Bản demo",
                }
            out_path = out_dir / f"{prefix}-{filename}"
            _write_editorial_data_scene(
                out_path,
                font_path=package.root / "resources/fonts/BeVietnamPro-Bold.ttf",
                display_font_path=package.root / "resources/fonts/BarlowCondensed-Bold.ttf",
                mode=mode,
                data=data,
                palette=package.design_tokens.get("palette", {}),
                is_long=is_long,
                scene_number=1,
            )
            outputs[f"{prefix}_{filename.removesuffix('.png')}"] = str(out_path)
    return {"status": "preview_only", "note": "Numbers and sources are illustrative, not match evidence.", "previews": outputs}


def _library_image_record(root: Path, asset_id: str) -> dict[str, Any]:
    """Resolve only verified, active image assets stored inside the local library."""
    from apps.asset_library.registry import connect

    conn = connect(root / "runtime/engine.db")
    try:
        row = conn.execute(
            "SELECT asset_id, stored_path, asset_type, rights_state, lifecycle_state, "
            "source_url, creator, license_type, metadata_json FROM assets WHERE asset_id = ?",
            (asset_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError(f"Selected library asset does not exist: {asset_id}")
    if row["asset_type"] != "image" or row["rights_state"] != "verified" or row["lifecycle_state"] != "active":
        raise ValueError(f"Selected media must be an active, rights-verified library image: {asset_id}")
    library_root = (root / "runtime/assets/library").resolve()
    image_path = (root / row["stored_path"]).resolve()
    if library_root not in image_path.parents or not image_path.is_file():
        raise ValueError(f"Selected library image is missing or outside the library: {asset_id}")
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return {
        "asset_id": row["asset_id"],
        "path": image_path,
        "source_url": row["source_url"],
        "creator": row["creator"],
        "license_type": row["license_type"],
        "metadata": metadata if isinstance(metadata, dict) else {},
    }


def _gate_media_for_use(
    root: Path, asset_id: str, purpose: dict[str, Any] | None
) -> None:
    """C1 rights gate for legacy short-form media slots.

    Refuses (raises) when the asset is not ``eligible`` for the exact
    proposed use. ``verified`` on the row is not blanket permission: the
    upload-intent scope (platform, territory, commercial, monetization,
    edit, credit, clip limit) must allow the use. YouTube sources and
    copyright exceptions deny by default and route to human review.
    """
    if purpose is None:
        raise ValueError(
            f"library asset {asset_id} is refused: no upload purpose "
            f"(platform/territory) is declared for this run, so eligibility "
            f"for this exact use cannot be confirmed; refusing to paint it."
        )
    from apps.measurement.render_qa import _registry_row
    from apps.asset_library.rights_scope import is_usable_for

    row, error = _registry_row(root, asset_id)
    if error == "missing":
        raise ValueError(
            f"library asset {asset_id} is refused: the asset registry is "
            f"unavailable."
        )
    if error == "absent" or row is None:
        raise ValueError(
            f"library asset {asset_id} is refused: it does not exist in the "
            f"asset registry."
        )
    if error:
        raise ValueError(
            f"library asset {asset_id} is refused: it is unverifiable at "
            f"render time ({error})."
        )
    if row.get("asset_type") != "image" or row.get("rights_state") != "verified" \
            or row.get("lifecycle_state") != "active":
        raise ValueError(
            f"library asset {asset_id} is refused: only verified + active "
            f"library images may render (got "
            f"{row.get('asset_type')}/{row.get('rights_state')}/"
            f"{row.get('lifecycle_state')})."
        )
    scope_out = is_usable_for(row, purpose)
    if not scope_out.get("allowed"):
        raise ValueError(
            f"library asset {asset_id} is refused for this upload: "
            f"{'; '.join(str(r) for r in scope_out.get('reasons', []))} "
            f"(action: {scope_out.get('required_action')})."
        )


def _write_editorial_data_scene(
    path: Path,
    *,
    font_path: Path,
    display_font_path: Path,
    mode: str,
    data: dict[str, Any],
    palette: dict[str, str],
    is_long: bool,
    scene_number: int,
    bare: bool = False,
) -> None:
    """Draw sourced stat, source, and chart plates; values must come from the reviewed script.

    With bare=True the hook claim / hero numeral is omitted so the video can
    reveal it kinetically (staggered lines, count-up) instead of baking it in.
    """
    from PIL import Image, ImageDraw, ImageFont

    panel_w, panel_h = (1540, 840) if is_long else (1080, 1920)
    scale = 2
    image = Image.new("RGBA", (panel_w * scale, panel_h * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")

    def color(key: str, fallback: str, alpha: int = 255) -> tuple[int, int, int, int]:
        raw = str(palette.get(key, fallback)).lstrip("#")
        return tuple(int(raw[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)

    def text(x: int, y: int, value: str, size: int, fill: tuple[int, int, int, int], *, bold: bool = False, display: bool = False) -> None:
        face = display_font_path if display else (font_path if bold else font_path.with_name("BeVietnamPro-Regular.ttf"))
        font = ImageFont.truetype(str(face), size * scale)
        draw.text((x * scale, y * scale), str(value)[:100], font=font, fill=fill)

    ink, paper = color("ink", "#111721", 248), color("chalk", "#F0EBDD")

    # Kit live-data plates were removed; the 69 authored starters carry the
    # visual system. Kit planning modes fall through to the generic editorial
    # branches below (comparison_duel, player_poster, goal_card aliases and
    # the stat_leader/fixture_card/score_card branch); unmapped modes render
    # the neutral data frame at the end of this function.

    # Owner pack layouts (Canva backgrounds + engine boxes): the default
    # package declares them with pack_bg; backgrounds ship in resources/pack.
    pack_spec = None
    try:
        from apps.pack_import import render_pack_plate

        anchor = font_path.parent
        for candidate in (font_path.parent, *font_path.parents):
            if candidate.name == "template_foundation":
                anchor = candidate.parent
                break
        package_layouts = resolve_template(
            anchor, "allen-knows-ball.shortform-analyst", allow_draft=True
        ).graphic_templates.get("layouts", [])
        pack_spec = next(
            (item for item in package_layouts
             if isinstance(item, dict) and item.get("id") == mode and item.get("pack_bg")),
            None,
        )
    except Exception:
        pack_spec = None
    if pack_spec is not None:
        from pathlib import Path as _Path

        resource_root = font_path.parent.parent / "pack"
        bg_file = next(
            (resource_root / f"{'long' if is_long else 'short'}-{mode}{ext}"
             for ext in (".png", ".jpg", ".jpeg")
             if (resource_root / f"{'long' if is_long else 'short'}-{mode}{ext}").is_file()),
            None,
        )
        if bg_file is None:
            raise ValueError(f"Owner pack background is missing for mode: {mode}")
        from apps.sportskit import KitFonts as _KitFonts

        plate = render_pack_plate(
            _Path(bg_file), pack_spec.get("boxes", []) or [], data,
            _KitFonts(font_path.parent), is_long)
        plate.save(path)
        return

    def rgba(name: str, alpha: int = 255) -> tuple[int, int, int, int]:
        raw = str(palette.get(name, "#F4F1FF")).lstrip("#")
        return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)
    muted, accent = color("muted", "#A9B2AA"), color("signal_lime", "#E4BA57")
    series = [color(f"data_{index}", fallback) for index, fallback in enumerate(("#54C7B8", "#F07862", "#8F83E8", "#E7C45C"), 1)]
    heading = str(data.get("headline") or data.get("title") or "BẰNG CHỨNG TRẬN ĐẤU")
    home = color("team_home", "#55C7B8")
    away = color("team_away", "#F07862")

    if mode == "media_b_roll":
        from PIL import ImageEnhance, ImageOps

        source_path = Path(str(data.get("media_file", "")))
        with Image.open(source_path) as source_image:
            photo = ImageOps.exif_transpose(source_image.convert("RGB"))
        photo = ImageEnhance.Color(photo).enhance(1.06)
        photo = ImageEnhance.Contrast(photo).enhance(1.04)
        # Owner 16/10: illustration lives INSIDE a reserved void, never
        # full-bleed cover (cover-crop upscales coarse photos and eats
        # quality). VOID plate + contained photo below.
        image = Image.new("RGBA", (panel_w * scale, panel_h * scale), (6, 9, 19, 255))
        if is_long:
            fx0, fy0, fw, fh = int(panel_w * 0.12), int(panel_h * 0.14), int(panel_w * 0.76), int(panel_h * 0.60)
            cap_y, cred_y, disc_y, cap_x = int(panel_h * 0.80), panel_h - 116, panel_h - 82, int(panel_w * 0.12)
        else:
            fx0, fy0, fw, fh = 130, 300, 820, 1050
            cap_y, cred_y, disc_y, cap_x = 1390, panel_h - 116, panel_h - 82, 130
        fitted = ImageOps.contain(photo, (fw * scale, fh * scale), method=Image.Resampling.LANCZOS)
        image.alpha_composite(fitted.convert("RGBA"), (fx0 * scale, fy0 * scale))
        draw = ImageDraw.Draw(image, "RGBA")
        caption = str(data.get("media_caption") or "BỐI CẢNH SÂN ĐẤU")
        caption_size = 31 if not is_long else 36
        caption_font = ImageFont.truetype(str(display_font_path), caption_size * scale)
        max_caption_width = (panel_w - 84) * scale
        caption_lines: list[str] = []
        current_line = ""
        for word in caption.split():
            candidate = f"{current_line} {word}".strip()
            if current_line and draw.textbbox((0, 0), candidate, font=caption_font)[2] > max_caption_width:
                caption_lines.append(current_line)
                current_line = word
            else:
                current_line = candidate
        if current_line:
            caption_lines.append(current_line)
        caption_lines = caption_lines[:2]
        for line_index, line in enumerate(caption_lines):
            text(cap_x, cap_y + line_index * (caption_size + 7), line, caption_size, (255,255,255,255), bold=True, display=True)
        creator = str(data.get("media_creator") or "Creator not listed")[:50]
        license_label = str(data.get("media_license") or "License recorded in Asset Library")[:34]
        credit_line = f"ẢNH: {creator} · {license_label}"
        credit_size = 12 if is_long else 11
        credit_font = ImageFont.truetype(str(font_path), credit_size * scale)
        while len(credit_line) > 18 and draw.textbbox((0, 0), credit_line, font=credit_font)[2] > max_caption_width:
            credit_line = credit_line[:-1].rstrip(" ·")
        text(cap_x, cred_y, credit_line, credit_size, (255,255,255,235), bold=True)
        text(cap_x, disc_y, "ẢNH MINH HỌA · KHÔNG PHẢI FOOTAGE TRẬN ĐANG PHÂN TÍCH", 11, (255,255,255,215))
        image.resize((panel_w, panel_h), Image.Resampling.LANCZOS).save(path)
        return

    # Each evidence graphic gets its own visual grammar: a face-off scorecard,
    # a true plotted chart, or a paper source note. Only the channel wordmark,
    # type system, and color tokens remain shared across the three layouts.
    if mode == "statline_scorecard":
        hero = data.get("hero")
        if isinstance(hero, dict) and not data.get("metrics") and str(hero.get("value", "")).strip():
            # San Dem hero: photographic night bed when shipped, else night field.
            grass = font_path.parent.parent / "ai-night-grass-p.jpg"
            if not _photo_bed(image, grass, panel_w, panel_h, scale, darken=95):
                _night_field(image, panel_w, panel_h, scale, ink, rgba("deep_pitch", 255),
                             phase=1.7 + scene_number * 0.7)
            draw = ImageDraw.Draw(image, "RGBA")
            hero_label = str(hero.get("label", ""))[:40] or "CHỈ SỐ QUYẾT ĐỊNH"
            label_font = ImageFont.truetype(str(font_path), _role_size(panel_h, "support")*scale)
            label_bounds = draw.textbbox((0,0),hero_label,font=label_font)
            _accent_line(draw, panel_w/2*scale, 150*scale, hero_label, label_font,
                         paper, rgba("signal_orange", 255))
            hero_value = str(hero.get("value", ""))[:12]
            hero_size = 220 if is_long else 240
            hero_font = ImageFont.truetype(str(display_font_path),hero_size*scale)
            while hero_size > 80 and draw.textbbox((0,0),hero_value,font=hero_font)[2] > (panel_w-140)*scale:
                hero_size -= 12
                hero_font = ImageFont.truetype(str(display_font_path),hero_size*scale)
            if not bare:
                value_bounds = draw.textbbox((0,0),hero_value,font=hero_font)
                value_w = (value_bounds[2]-value_bounds[0])/scale
                value_h = (value_bounds[3]-value_bounds[1])/scale
                numeral_x = (panel_w-value_w)/2*scale
                numeral_y = (panel_h/2-value_h/2-10)*scale
                _ensure_contrast(draw, image,
                                 (numeral_x, numeral_y,
                                  numeral_x+value_w*scale, numeral_y+value_h*scale),
                                 rgba("signal_lime", 255))
                halo = max(value_w, value_h)/2*scale + 30*scale
                _sprite(image, _kit("light_02.png", font_path),
                        (panel_w*scale/2, panel_h*scale*0.52),
                        round(halo*2.6), (255, 179, 0), 150)
                draw.ellipse((panel_w*scale/2-halo, panel_h*scale*0.52-halo,
                              panel_w*scale/2+halo, panel_h*scale*0.52+halo),
                             outline=rgba("signal_lime", 255), width=5*scale)
                draw.ellipse((panel_w*scale/2-halo+10*scale, panel_h*scale*0.52-halo+10*scale,
                              panel_w*scale/2+halo-10*scale, panel_h*scale*0.52+halo-10*scale),
                             outline=rgba("signal_lime", 110), width=2*scale)
                _extrude(draw, (numeral_x, numeral_y), hero_value, hero_font,
                         rgba("signal_lime", 255), depth=6*scale)
                _reflection(image, (numeral_x, numeral_y,
                                    numeral_x+value_w*scale, numeral_y+value_h*scale),
                            gap=12*scale, height=110*scale)
            hero_source = str(data.get("source") or data.get("source_label") or "Nguồn cần xác minh")
            hero_credit = f"{hero_source} · {data.get('date','')}".strip(" ·")
            credit_bounds = draw.textbbox((0,0),hero_credit[:90],font=ImageFont.truetype(str(font_path),13*scale))
            text((panel_w-(credit_bounds[2]-credit_bounds[0])/scale)/2,panel_h-110,hero_credit[:90],_role_size(panel_h, "whisper"),muted)
            _vignette(image)
            image.resize((panel_w,panel_h),Image.Resampling.LANCZOS).save(path)
            return
        # Duel comparison (ESPN grammar): header band with team wedges,
        # filled team halves with records, zone-tinted rows, winner in green.
        draw.rectangle((0, 0, panel_w*scale, panel_h*scale), fill=ink)
        _night_field(image, panel_w, panel_h, scale, ink, rgba("deep_pitch", 255),
                     phase=2.6 + scene_number * 0.7)
        draw = ImageDraw.Draw(image, "RGBA")
        teams=data.get("teams",["ĐỘI A","ĐỘI B"])
        if not isinstance(teams,list) or len(teams)<2: teams=["ĐỘI A","ĐỘI B"]
        def _team_name(item: Any) -> str:
            return str(item.get("name") if isinstance(item, dict) else item)[:24]
        def _team_record(item: Any) -> str:
            record = item.get("record") if isinstance(item, dict) else ""
            return str(record or "")[:16]
        split=panel_w//2
        band_h=86 if is_long else 96
        draw.rectangle((0, 0, panel_w*scale, band_h*scale), fill=(4, 6, 5, 255))
        draw.polygon([(0,0),(90*scale,0),(60*scale,band_h*scale),(0,band_h*scale)], fill=home)
        draw.polygon([(panel_w*scale,0),(panel_w*scale,band_h*scale),
                      ((panel_w-60)*scale,band_h*scale),((panel_w-90)*scale,0)], fill=away)
        band_font=ImageFont.truetype(str(display_font_path), (30 if is_long else 32)*scale)
        band_bounds=draw.textbbox((0,0),heading.replace("*",""),font=band_font)
        _accent_line(draw, panel_w/2*scale, (band_h/2-(band_bounds[3]-band_bounds[1])/2/scale)*scale,
                     heading, band_font, paper, rgba("signal_lime", 255))
        head_y=band_h+(14 if is_long else 18)
        head_h=64 if is_long else 76
        draw.rectangle((0,head_y*scale,split*scale,(head_y+head_h)*scale), fill=home)
        draw.rectangle((split*scale,head_y*scale,panel_w*scale,(head_y+head_h)*scale), fill=away)
        home_name, away_name = _team_name(teams[0]), _team_name(teams[1])
        home_record, away_record = _team_record(teams[0]), _team_record(teams[1])
        team_font=ImageFont.truetype(str(font_path), (19 if is_long else 18)*scale)
        draw.text((24*scale,(head_y+8)*scale), home_name, font=team_font, fill=ink)
        draw.text((24*scale,(head_y+36)*scale), home_record, font=team_font, fill=ink)
        right_name_bounds=draw.textbbox((0,0),away_name,font=team_font)
        draw.text((panel_w*scale-24*scale-(right_name_bounds[2]-right_name_bounds[0]),
                  (head_y+8)*scale), away_name, font=team_font, fill=ink)
        if away_record:
            record_bounds=draw.textbbox((0,0),away_record,font=team_font)
            draw.text((panel_w*scale-24*scale-(record_bounds[2]-record_bounds[0]),
                       (head_y+36)*scale), away_record, font=team_font, fill=ink)
        metrics=data.get("metrics",[])
        metrics=[item for item in metrics[:5] if isinstance(item,dict)] if isinstance(metrics,list) else []
        if not metrics:
            text(48,head_y+head_h+48,"Chưa có số liệu đã xác minh",20,muted,bold=True)
        top=head_y+head_h+(62 if is_long else 74)
        bottom=panel_h-(118 if is_long else 138)
        row_h=min(360,max(1,(bottom-top)//max(1,len(metrics))))
        value_size=min(64 if is_long else 78,max(40,row_h//2))
        number_font=ImageFont.truetype(str(display_font_path),value_size*scale)
        label_size=min(_role_size(panel_h, "support"), max(16, row_h//8))
        for index,item in enumerate(metrics):
            y=top+index*row_h
            if index:
                _ticket_cut(draw, panel_w*scale, y*scale, scale, ink)
            label=str(item.get("label","Chỉ số"))[:28]
            label_font=ImageFont.truetype(str(font_path),label_size*scale)
            label_w=draw.textbbox((0,0),label,font=label_font)[2]/scale
            text((panel_w-label_w)/2,y+row_h*.17,label,label_size,muted,bold=True)
            for center,value,tint in ((panel_w*.24,item.get("home","—"),home),(panel_w*.76,item.get("away","—"),away)):
                value=str(value)[:12]
                value_bounds=draw.textbbox((0,0),value,font=number_font,anchor="lt")
                _extrude(draw,(center*scale-(value_bounds[2]-value_bounds[0])/2,
                               (y+row_h*.62)*scale-(value_bounds[3]-value_bounds[1])/2),
                         value,font=number_font,fill=tint,depth=2*scale)
            # Mirrored strokes read as a direct matchup; their lengths encode
            # only relative magnitudes within this row, with the raw values kept.
            try:
                left_value=max(0.0,float(item.get("home",0))); right_value=max(0.0,float(item.get("away",0)))
                pair_max=max(left_value,right_value,1.0)
                rail_left,rail_right=panel_w*.12,panel_w*.88
                rail_y=y+row_h*.82
                center_x=panel_w/2
                left_len=(center_x-rail_left)*left_value/pair_max
                right_len=(rail_right-center_x)*right_value/pair_max
                left_light=tuple(min(255,component+52) for component in home[:3])+(255,)
                right_light=tuple(min(255,component+52) for component in away[:3])+(255,)
                draw.rounded_rectangle(((center_x-left_len)*scale,(rail_y-2)*scale,center_x*scale,(rail_y+7)*scale),radius=4*scale,fill=home[:3]+(80,))
                draw.rounded_rectangle((center_x*scale,(rail_y-2)*scale,(center_x+right_len)*scale,(rail_y+7)*scale),radius=4*scale,fill=away[:3]+(80,))
                _gradient_rounded(image,((center_x-left_len)*scale,rail_y*scale,center_x*scale,(rail_y+5)*scale),3*scale,home,left_light,axis="horizontal")
                _gradient_rounded(image,(center_x*scale,rail_y*scale,(center_x+right_len)*scale,(rail_y+5)*scale),3*scale,right_light,away,axis="horizontal")
                draw.rounded_rectangle(((center_x-left_len)*scale,rail_y*scale,center_x*scale,(rail_y+5)*scale),radius=3*scale,fill=home)
                draw.rounded_rectangle((center_x*scale,rail_y*scale,(center_x+right_len)*scale,(rail_y+5)*scale),radius=3*scale,fill=away)
            except (TypeError,ValueError):
                pass
        source=str(data.get("source") or data.get("source_label") or "Nguồn cần xác minh")
        credit=f"{source} · {data.get('date','')}".strip(" ·")
        _tick_ruler(draw, 42*scale, (panel_h-96)*scale, (panel_w-84)*scale,
                    color("muted", "#8FA39A"), scale)
        text(42,panel_h-68,credit[:105],12,muted)
        _vignette(image)
        image.resize((panel_w,panel_h),Image.Resampling.LANCZOS).save(path)
        return

    if mode in {"chart_comparison", "chart_timeline"}:
        # San Dem chalkboard lab: night field, floodlit marks, chalk grid.
        _night_field(image, panel_w, panel_h, scale, ink, color("deep_pitch", "#12211B"), phase=0.6)
        draw = ImageDraw.Draw(image, "RGBA")
        dark = color("chalk", "#F4F1FF")
        body_muted = color("muted", "#9A8FBF")
        # Offset registration marks and a compact issue tag give the plot the
        # feel of an editorial analysis sheet without obscuring its evidence.
        draw.rectangle((0,0,panel_w*scale,9*scale),fill=home)
        for i in range(6):
            x=(panel_w-128+i*13)*scale
            draw.line((x,26*scale,x,39*scale),fill=(255,179,0,150),width=2*scale)
        text(48,26,"ALLEN KNOWS BALL  /  DATA PLOT",14,body_muted,bold=True)
        text(44,82,heading,36 if is_long else 32,dark,bold=True,display=True)
        draw.line((44*scale,143*scale,(panel_w-44)*scale,143*scale),fill=home,width=4*scale)
        values=data.get("values",[])
        values=[item for item in values[:6] if isinstance(item,dict)] if isinstance(values,list) else []
        plot_left=310 if is_long else 230
        plot_right=panel_w-(112 if is_long else 95)
        plot_top=220 if is_long else 245
        plot_bottom=panel_h-(160 if is_long else 190)
        chart_type=str(data.get("chart_type") or ("line" if mode=="chart_timeline" else "bar")).lower()
        if chart_type not in {"bar","column","pie","donut","line"}:
            chart_type="bar"
        nums=[]
        for item in values:
            try: nums.append(float(item.get("value",0)))
            except (TypeError,ValueError): nums.append(0.0)
        invalid_part_whole=(chart_type in {"pie","donut"} and (
            data.get("part_to_whole") is not True or len(values)<2 or len(values)>4
            or any(number<0 for number in nums) or sum(nums)<=0
        ))
        if invalid_part_whole:
            chart_type="bar"
        if chart_type=="bar" and values:
            nums=[max(0.0,n) for n in nums]
            high=max(nums,default=1.0) or 1.0
            tick_step=2 if high<=8 else (5 if high<=20 else 10)
            axis_max=max(tick_step,((int(high)+tick_step-1)//tick_step)*tick_step)
            # Labeled grid makes length comparisons interpretable and exposes
            # the zero baseline instead of implying a truncated scale.
            for tick in range(0,axis_max+1,tick_step):
                x=plot_left+(plot_right-plot_left)*tick/axis_max
                draw.line((x*scale,plot_top*scale,x*scale,plot_bottom*scale),fill=(143,163,154,70),width=scale)
                draw.text((x*scale,(plot_bottom+18)*scale),str(tick),font=ImageFont.truetype(str(font_path.with_name("BeVietnamPro-Regular.ttf")),12*scale),fill=body_muted,anchor="mt")
            step=(plot_bottom-plot_top)//max(1,len(values))
            for index,item in enumerate(values):
                y=plot_top+index*step
                label=str(item.get("label",""))[:25]
                text(44,y+step*.22,label,15 if is_long else 14,dark,bold=True)
                bar_y=y+step*.62
                bar_h=22 if is_long else 26
                draw.rounded_rectangle((plot_left*scale,bar_y*scale,plot_right*scale,(bar_y+bar_h)*scale),radius=3*scale,fill=(20,30,26,60))
                width=(plot_right-plot_left)*nums[index]/axis_max
                tint=home
                light=tuple(min(255,component+52) for component in tint[:3])+(255,)
                _gradient_rounded(image,(plot_left*scale,bar_y*scale,(plot_left+max(1,width))*scale,(bar_y+bar_h)*scale),3*scale,light,tint,axis="horizontal")
                draw.ellipse(((plot_left+width-7)*scale,(bar_y-4)*scale,(plot_left+width+7)*scale,(bar_y+bar_h+4)*scale),fill=tint,outline=paper,width=2*scale)
                text(plot_right+15,bar_y-3,str(item.get("value","")),18,tint,bold=True)
        elif chart_type=="column" and values:
            nums=[max(0.0,n) for n in nums]
            high=max(nums,default=1.0) or 1.0
            tick_step=2 if high<=8 else (5 if high<=20 else 10)
            axis_max=max(tick_step,((int(high)+tick_step-1)//tick_step)*tick_step)
            for tick in range(0,axis_max+1,tick_step):
                y=plot_bottom-(plot_bottom-plot_top)*tick/axis_max
                draw.line((plot_left*scale,y*scale,plot_right*scale,y*scale),fill=(143,163,154,80),width=scale)
                draw.text(((plot_left-34)*scale,y*scale),str(tick),font=ImageFont.truetype(str(font_path.with_name("BeVietnamPro-Regular.ttf")),12*scale),fill=body_muted,anchor="rm")
            band=(plot_right-plot_left)/max(1,len(values)); bar_w=min(74,band*.54)
            for index,(item,number) in enumerate(zip(values,nums)):
                center=plot_left+band*(index+.5)
                bar_h=(plot_bottom-plot_top)*number/axis_max
                tint=home
                light=tuple(min(255,component+52) for component in tint[:3])+(255,)
                _gradient_rounded(image,((center-bar_w/2)*scale,(plot_bottom-bar_h)*scale,(center+bar_w/2)*scale,plot_bottom*scale),5*scale,light,tint)
                # Slim contrasting cap makes each mark read as a deliberate
                # plotted value, not a generic rounded UI bar.
                cap_h=min(5,max(2,bar_h*.04))
                draw.line(((center-bar_w/2+5)*scale,(plot_bottom-bar_h+cap_h)*scale,(center+bar_w/2-5)*scale,(plot_bottom-bar_h+cap_h)*scale),fill=accent,width=2*scale)
                halo_r=16*scale
                draw.ellipse(((center*scale)-halo_r,(plot_bottom-bar_h-26)*scale-halo_r,(center*scale)+halo_r,(plot_bottom-bar_h-26)*scale+halo_r),fill=tint[:3]+(46,))
                draw.text((center*scale,(plot_bottom-bar_h-32)*scale),str(item.get("value","")),font=ImageFont.truetype(str(display_font_path),18*scale),fill=dark,anchor="mm")
                label=str(item.get("label", ""))[:14]
                draw.text((center*scale,(plot_bottom+24)*scale),label,font=ImageFont.truetype(str(font_path.with_name("BeVietnamPro-Regular.ttf")),12*scale),fill=body_muted,anchor="mt")
        elif chart_type in {"pie","donut"} and values:
            total=sum(nums)
            radius=min(205 if not is_long else 215,(plot_bottom-plot_top)//2-16)
            cx=int(panel_w*(.39 if is_long else .38)); cy=(plot_top+plot_bottom)//2
            bbox=((cx-radius)*scale,(cy-radius)*scale,(cx+radius)*scale,(cy+radius)*scale)
            angle=-90
            legend_x=int(panel_w*(.64 if is_long else .66))
            legend_top=cy-(len(values)*68)//2
            for index,(item,number) in enumerate(zip(values,nums)):
                sweep=360*number/total
                tint=series[index%len(series)]
                draw.pieslice(bbox,start=angle,end=angle+sweep,fill=tint,outline=paper,width=3*scale)
                pct=number/total*100
                ly=legend_top+index*68
                draw.rounded_rectangle((legend_x*scale,ly*scale,(legend_x+22)*scale,(ly+22)*scale),radius=4*scale,fill=tint)
                text(legend_x+34,ly-1,str(item.get("label",""))[:20],15,dark,bold=True)
                text(legend_x+34,ly+24,f"{item.get('value','')}  ·  {pct:.0f}%",13,body_muted)
                angle+=sweep
            if chart_type=="donut":
                hole=int(radius*.54)
                draw.ellipse(((cx-hole)*scale,(cy-hole)*scale,(cx+hole)*scale,(cy+hole)*scale),fill=color("deep_pitch","#1A0B2E"))
                total_label=f"{total:g}"
                draw.text((cx*scale,(cy-8)*scale),total_label,font=ImageFont.truetype(str(display_font_path),38*scale),fill=dark,anchor="mm")
                draw.text((cx*scale,(cy+34)*scale),str(data.get("unit","TOTAL"))[:14],font=ImageFont.truetype(str(font_path),11*scale),fill=body_muted,anchor="mm")
        elif chart_type=="line" and values:
            low=min(0.0,min(nums)); high=max(nums,default=1.0); high=high if high>low else low+1
            for index in range(5):
                y=plot_top+(plot_bottom-plot_top)*index/4
                draw.line((plot_left*scale,y*scale,plot_right*scale,y*scale),fill=(91,74,138,80),width=scale)
            coords=[]
            for index,value in enumerate(nums):
                x=plot_left+(plot_right-plot_left)*index/max(1,len(nums)-1)
                y=plot_bottom-(value-low)/(high-low)*(plot_bottom-plot_top)
                coords.append((round(x*scale),round(y*scale)))
            if len(coords)>1:
                # A soft underlay reinforces the single chronological arc.
                draw.line([(x,y+7*scale) for x,y in coords],fill=(255,179,0,36),width=10*scale,joint="curve")
                draw.line(coords,fill=home,width=5*scale,joint="curve")
            for index,(point,item) in enumerate(zip(coords,values)):
                x,y=point; radius=9*scale
                draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=home,outline=dark,width=2*scale)
                draw.text((x,y-30*scale),str(item.get("value","")),font=ImageFont.truetype(str(display_font_path),18*scale),fill=dark,anchor="mm")
                text(x/scale-35,plot_bottom+25,str(item.get("label",""))[:15],12,body_muted)
        else:
            text(48,plot_top+35,"Chưa có chuỗi số liệu đã xác minh",20,body_muted,bold=True)
        if invalid_part_whole:
            text(44,174,"Pie/donut cần dữ liệu tỷ trọng cùng thuộc một tổng thể · đang hiển thị dạng thanh an toàn",12,body_muted)
        else:
            type_label={"bar":"BARS","column":"COLUMNS","pie":"PARTS OF A WHOLE","donut":"PARTS OF A WHOLE","line":"TIMELINE"}.get(chart_type,"DATA")
            text(44,174,type_label,12,body_muted,bold=True)
        source=str(data.get("source") or data.get("source_label") or "Nguồn cần gắn nguồn đã duyệt")
        credit=f"NGUỒN  /  {source}  ·  {data.get('date','')}".strip(" ·")
        text(44,panel_h-62,credit[:105],12,body_muted,bold=True)
        _vignette(image)
        image.resize((panel_w,panel_h),Image.Resampling.LANCZOS).save(path)
        return

    if mode=="source_card":
        # San Dem chalkboard strip: painted frame, seal, source voice, URL.
        _night_field(image, panel_w, panel_h, scale, ink, color("deep_pitch", "#12211B"),
                     phase=2.2 + scene_number * 0.7)
        draw = ImageDraw.Draw(image, "RGBA")
        margin = 64
        draw.rounded_rectangle((margin*scale, 150*scale, (panel_w-margin)*scale, (panel_h-150)*scale),
                               radius=8*scale, fill=(13, 20, 17, 245),
                               outline=(232, 228, 218, 220), width=3*scale)
        draw.rounded_rectangle(((margin+10)*scale, 160*scale, (panel_w-margin-10)*scale, (panel_h-160)*scale),
                               radius=6*scale, outline=(232, 228, 218, 90), width=scale)
        source=str(data.get("source") or "Nguồn cần bổ sung")
        date=str(data.get("date") or "Ngày xuất bản cần xác minh")
        claim=str(data.get("claim") or data.get("description") or "Chưa có luận điểm được đối chiếu với nguồn đã duyệt.")
        seal_cx, seal_cy = (margin+110)*scale, 270*scale
        seal_r = 44*scale
        draw.ellipse((seal_cx-seal_r, seal_cy-seal_r, seal_cx+seal_r, seal_cy+seal_r),
                     outline=color("signal_lime", "#FFB300"), width=4*scale)
        draw.ellipse((seal_cx-seal_r+7*scale, seal_cy-seal_r+7*scale,
                      seal_cx+seal_r-7*scale, seal_cy+seal_r-7*scale),
                     outline=color("signal_lime", "#FFB300")[:3]+(120,), width=scale)
        initial = next((ch for ch in source.strip()[:1] if ch.strip()), "A")
        seal_font=ImageFont.truetype(str(display_font_path),44*scale)
        bounds=draw.textbbox((0,0),initial,font=seal_font)
        draw.text((seal_cx-(bounds[2]-bounds[0])/2,seal_cy-(bounds[3]-bounds[1])/2-bounds[1]),
                  initial,font=seal_font,fill=paper)
        text(margin+190,222,"NGUỒN ĐÃ XÁC MINH",15,color("signal_lime", "#B6FF2E"),bold=True)
        _accent_line(draw, panel_w/2*scale, 310*scale, source[:44],
                     ImageFont.truetype(str(font_path),30*scale),
                     paper, rgba("signal_orange", 255), depth=2*scale)
        source_ink = color("muted", "#9A8FBF")
        text(margin+190,378,date[:90],17,source_ink)
        words=textwrap.wrap(claim,width=60 if is_long else 34)
        size=32 if is_long else 30
        line_gap=58 if is_long else 60
        block_top = 510 if is_long else 550
        for index,line_value in enumerate(words[:4]):
            _accent_line(draw, panel_w/2*scale, (block_top+index*line_gap)*scale, line_value,
                         ImageFont.truetype(str(font_path),size), paper,
                         rgba("signal_orange", 255))
        url=str(data.get("url") or "")
        if url:
            draw.line(((margin+40)*scale,(panel_h-270)*scale,(panel_w-margin-40)*scale,(panel_h-270)*scale),fill=(91,74,138,160),width=scale)
            text(margin+40,panel_h-246,url[:90],14,source_ink)
        _vignette(image)
        image.resize((panel_w,panel_h),Image.Resampling.LANCZOS).save(path)
        return

    if mode == "player_card":
        # Poster player card: photo split, brush name overlapping both zones,
        # three stat columns, ticker strip. Portrait must be approved library
        # media; the card degrades to a typographic version without it.
        photo_path = str(data.get("media_file", ""))
        try:
            has_photo = bool(photo_path) and Path(photo_path).is_file()
        except (OSError, ValueError):
            has_photo = False
        if has_photo:
            draw.rectangle((0, 0, panel_w*scale, panel_h*scale), fill=ink)
        else:
            _night_field(image, panel_w, panel_h, scale, ink, rgba("deep_pitch", 255),
                         phase=3.1 + scene_number * 0.7)
        draw = ImageDraw.Draw(image, "RGBA")
        split = round(panel_w * (0.52 if not is_long else 0.44))
        photo_path = str(data.get("media_file", ""))
        if photo_path:
            from PIL import Image as _Image, ImageOps as _ImageOps
            try:
                with _Image.open(photo_path) as source_photo:
                    fitted = _ImageOps.fit(source_photo.convert("RGB"),
                                           (split * scale, panel_h * scale),
                                           method=_Image.Resampling.LANCZOS,
                                           centering=(0.5, 0.3)).convert("RGBA")
                image.alpha_composite(fitted, (0, 0))
            except (OSError, ValueError):
                photo_path = ""
                has_photo = False
        if photo_path:
            draw.line((split*scale, 0, split*scale, panel_h*scale),
                      fill=rgba("signal_lime", 255), width=4*scale)
        brush_size = 104 if not is_long else 92
        name = str(data.get("player_name") or "CẦU THỦ")
        while brush_size > 44:
            try:
                brush = ImageFont.truetype(
                    str(display_font_path.parent / "PermanentMarker-Regular.woff"),
                    brush_size*scale)
            except (OSError, ValueError):
                brush = ImageFont.truetype(str(display_font_path), brush_size*scale)
            bounds = draw.textbbox((0, 0), name[:26], font=brush)
            if (bounds[2] - bounds[0]) <= (panel_w - 60) * scale:
                break
            brush_size -= 8
        surname = name.split()[-1] if name.split() else name
        ticker_font = ImageFont.truetype(str(font_path), 15*scale)
        ticker = ((surname.upper() + "  •  ") * 12)[:120]
        draw.rectangle((0, 0, panel_w*scale, 52*scale), fill=(10, 15, 13, 235))
        draw.text((20*scale, 12*scale), ticker, font=ticker_font, fill=muted)
        name_top = (panel_h*0.30) if photo_path else (panel_h*0.22)
        bounds = draw.textbbox((0, 0), name[:26], font=brush)
        _extrude(draw, ((panel_w/2)*scale-(bounds[2]-bounds[0])/2, name_top*scale),
                 name[:26], brush, paper, depth=3*scale)
        detail = str(data.get("player_detail") or data.get("title") or "")
        if detail:
            text((panel_w/2-140), name_top+118, detail[:44], 15, muted, bold=True)
        stats = [item for item in (data.get("stats") or [])[:3] if isinstance(item, dict)]
        columns = max(1, len(stats)) if stats else 1
        for position, item in enumerate(stats):
            center = panel_w * (0.5 + (position - (len(stats)-1)/2) * (0.62/len(stats)))
            value = str(item.get("value", "—"))[:10]
            stat_font = ImageFont.truetype(str(display_font_path), (72 if is_long else 84)*scale)
            value_bounds = draw.textbbox((0, 0), value, font=stat_font)
            _extrude(draw, (center*scale-(value_bounds[2]-value_bounds[0])/2,
                            (panel_h*0.62)*scale),
                     value, stat_font, rgba("signal_lime", 255), depth=3*scale)
            text(center-70, panel_h*0.62+96, str(item.get("label", ""))[:22], 14, muted, bold=True)
        source = str(data.get("source") or "")
        if source:
            credit = f"{source} · {data.get('date','')}".strip(" ·")
            text(42, panel_h-68, credit[:90], 12, muted)
        _vignette(image)
        image.resize((panel_w, panel_h), Image.Resampling.LANCZOS).save(path)
        return

    # Sports Kit v8 aliases: poster/duel/goal reuse proven Nova plates so
    # typography and provenance stay locked; only genuinely new grammars
    # (leader list, fixtures, score) get dedicated branches below.
    if mode == "comparison_duel":
        return _write_editorial_data_scene(
            path, font_path=font_path, display_font_path=display_font_path,
            mode="statline_scorecard", data=data, palette=palette,
            is_long=is_long, scene_number=scene_number, bare=bare)
    if mode == "player_poster":
        return _write_editorial_data_scene(
            path, font_path=font_path, display_font_path=display_font_path,
            mode="player_card", data=data, palette=palette,
            is_long=is_long, scene_number=scene_number, bare=bare)
    if mode in {"player_poster_side", "player_poster_top", "potm_card", "welcome_card"}:
        return _write_editorial_data_scene(
            path, font_path=font_path, display_font_path=display_font_path,
            mode="player_card", data=data, palette=palette,
            is_long=is_long, scene_number=scene_number, bare=bare)
    if mode == "duel_columns":
        return _write_editorial_data_scene(
            path, font_path=font_path, display_font_path=display_font_path,
            mode="statline_scorecard", data=data, palette=palette,
            is_long=is_long, scene_number=scene_number, bare=bare)
    if mode == "fixture_list":
        list_data = dict(data)
        fixtures = list_data.get("fixtures") or []
        if fixtures and not list_data.get("home"):
            first = fixtures[0] if isinstance(fixtures[0], dict) else {}
            list_data.setdefault("home", first.get("home", "DOI NHA"))
            list_data.setdefault("away", first.get("away", "DOI KHACH"))
        return _write_editorial_data_scene(
            path, font_path=font_path, display_font_path=display_font_path,
            mode="fixture_card", data=list_data, palette=palette,
            is_long=is_long, scene_number=scene_number, bare=bare)
    if mode == "quote_card":
        return _write_editorial_data_scene(
            path, font_path=font_path, display_font_path=display_font_path,
            mode="source_card", data=data, palette=palette,
            is_long=is_long, scene_number=scene_number, bare=bare)
    if mode == "goal_card":
        goal_data = dict(data)
        goal_data["hook_text"] = (data.get("hook_text") or data.get("headline")
                                  or data.get("score") or data.get("title") or "")
        return _write_editorial_data_scene(
            path, font_path=font_path, display_font_path=display_font_path,
            mode="hook_card", data=goal_data, palette=palette,
            is_long=is_long, scene_number=scene_number, bare=bare)

    if mode in {"stat_leader", "fixture_card", "score_card"}:
        from PIL import ImageFont as _Font
        _night_field(image, panel_w, panel_h, scale, ink,
                     rgba("deep_pitch", 255), phase=1.3 + scene_number * 0.7)
        draw = ImageDraw.Draw(image, "RGBA")
        head = str(data.get("headline") or data.get("title") or "MATCH KIT")
        text(48, 60, "ALLEN KNOWS BALL  /  SPORTS KIT", 15, muted, bold=True)
        text(48, 110, head[:60], 34 if is_long else 30, paper, bold=True, display=True)
        draw.line((48*scale, 190*scale, (panel_w-48)*scale, 190*scale),
                  fill=home, width=4*scale)
        if mode == "stat_leader":
            stats = [x for x in (data.get("stats") or [])[:4] if isinstance(x, dict)]
            top = 250
            for i, item in enumerate(stats):
                y = top + i * 210
                label = str(item.get("label", ""))[:24]
                value = str(item.get("value", "--"))[:10]
                text(60, y, label.upper(), 18, muted, bold=True)
                big = _Font.truetype(str(display_font_path), 96*scale)
                _extrude(draw, (60*scale, (y+44)*scale), value, big,
                         rgba("signal_lime", 255), depth=4*scale)
        elif mode == "fixture_card":
            fixtures = [x for x in (data.get("fixtures") or [])[:3] if isinstance(x, dict)]
            top = 250
            for i, item in enumerate(fixtures):
                y = top + i * 230
                draw.rounded_rectangle((48*scale, y*scale,
                                        (panel_w-48)*scale, (y+190)*scale),
                                       radius=8*scale, fill=(13, 20, 17, 245),
                                       outline=(232, 228, 218, 220), width=2*scale)
                left = str(item.get("home", "DOI NHA"))[:20]
                right = str(item.get("away", "DOI KHACH"))[:20]
                when = str(item.get("date", item.get("when", "")))[:44]
                text(80, y+24, f"{left}  V  {right}", 24, paper, bold=True, display=True)
                text(80, y+110, when or "Ngay gio can xac minh", 16, muted)
        else:
            home_t = str(data.get("home", "DOI NHA"))[:20]
            away_t = str(data.get("away", "DOI KHACH"))[:20]
            score = str(data.get("score", "1 - 0"))[:12]
            text(48, 250, f"{home_t}  V  {away_t}", 26, paper, bold=True, display=True)
            big = _Font.truetype(str(display_font_path), 150*scale)
            _extrude(draw, (panel_w/2*scale-160*scale, 380*scale), score, big,
                     paper, depth=5*scale)
            text(48, 640, "FULL TIME", 40, rgba("signal_orange", 255),
                 bold=True, display=True)
        credit = f"{data.get('source','Nguon can xac minh')} - {data.get('date','')}".strip(" - ")[:90]
        text(48, panel_h-110, credit, 13, muted)
        _vignette(image)
        image.resize((panel_w, panel_h), Image.Resampling.LANCZOS).save(path)
        return

    if mode == "hook_card":
        # San Dem opening: photographic night bed when the package ships one,
        # else the procedural field. Floodlit giant claim, ONE amber accent.
        photo = font_path.parent.parent / "ai-night-pitch-p.jpg"
        if not _photo_bed(image, photo, panel_w, panel_h, scale, darken=85):
            _night_field(image, panel_w, panel_h, scale, ink, rgba("deep_pitch", 255),
                         phase=scene_number * 0.7)
        draw = ImageDraw.Draw(image, "RGBA")
        frame = 24 * scale
        draw.rectangle((frame, frame, panel_w*scale-frame, panel_h*scale-frame),
                       outline=rgba("signal_lime", 255), width=5*scale)
        kit = lambda name: _kit(name, font_path)
        _sprite(image, kit("flare_01.png"), (panel_w*0.16*scale, 90*scale),
                300*scale, (255, 190, 90), 190)
        _sprite(image, kit("flare_01.png"), (panel_w*0.84*scale, 90*scale),
                300*scale, (255, 190, 90), 190)
        _sprite(image, kit("smoke_03.png"), (panel_w*0.25*scale, panel_h*0.85*scale),
                420*scale, (200, 210, 205), 70)
        _sprite(image, kit("smoke_03.png"), (panel_w*0.78*scale, panel_h*0.88*scale),
                360*scale, (200, 210, 205), 60)
        hook = " ".join(str(data.get("hook_text") or data.get("headline") or data.get("title") or "").split())[:140]
        if not hook:
            hook = "CÂU HỎI TRẬN ĐẤU"
        # 12.0.0 rule: hook is a short single-line phrase with one emphasized
        # word only. Strip all accent markup, then re-add only the first
        # emphasized word so no beat renders multiple accented words.
        _accent_matches = list(re.finditer(r"\*([^*]+)\*", hook))
        if _accent_matches:
            _first_word = _accent_matches[0].group(1)
            hook = re.sub(r"\*", "", hook)
            hook = hook.replace(_first_word, f"*{_first_word}*", 1)
        else:
            hook = re.sub(r"\*", "", hook)
        max_width = (panel_w - 8 * U) * scale
        hook_size = _role_size(panel_h, "boss")
        hook_font = ImageFont.truetype(str(display_font_path), hook_size*scale)
        hook_lines: list[str] = []
        if not bare:
            phrases = _phrase_lines(hook)
            if len(phrases) > 1:
                hook_lines = phrases[:1]
                hook_size = _role_size(panel_h, "boss")
                hook_font = ImageFont.truetype(str(display_font_path), hook_size*scale)
            else:
                while hook_size >= _role_size(panel_h, "support") * 2:
                    hook_font = ImageFont.truetype(str(display_font_path), hook_size*scale)
                    probe = draw.textbbox((0, 0), hook.replace("*", ""), font=hook_font)[2]
                    if probe <= max_width * 3:
                        break
                    hook_size -= 4
                hook_lines, current = [], ""
                for word in hook.split():
                    candidate = f"{current} {word}".strip()
                    probe = draw.textbbox((0, 0), candidate.replace("*", ""), font=hook_font)[2]
                    if current and probe > max_width:
                        hook_lines.append(current)
                        current = word
                    else:
                        current = candidate
                if current:
                    hook_lines.append(current)
                hook_lines = hook_lines[:1]
                if len(hook_lines) > 1 and len(hook_lines[-1].split()) == 1 and len(hook_lines[-1]) <= 4:
                    hook_lines[-2] = f"{hook_lines[-2]} {hook_lines[-1]}"
                    hook_lines.pop()
            line_h = hook_size + U * 2
            start_y = panel_h / 2 - len(hook_lines[:3]) * line_h / 2
            for row, line_value in enumerate(hook_lines[:3]):
                width = draw.textbbox((0, 0), line_value.replace("*", ""), font=hook_font)[2] / scale
                top = start_y + row * line_h
                _ensure_contrast(draw, image,
                                 ((panel_w - width) / 2 * scale, top * scale,
                                  (panel_w + width) / 2 * scale, (top + line_h) * scale),
                                 paper)
                _accent_line(draw, panel_w / 2 * scale, top * scale,
                             line_value, hook_font, paper,
                             rgba("signal_lime", 255), depth=5*scale)
        _vignette(image)
        image.resize((panel_w, panel_h), Image.Resampling.LANCZOS).save(path)
        return

    heading = str(data.get("headline") or data.get("title") or "BẰNG CHỨNG TRẬN ĐẤU")
    # 12.0.0 safe area: top 9% (173px at 1080x1920). Keep body headings below
    # the exclusion zone so nothing crowds the top edge.
    _safe_top_px = panel_h * 0.09
    _heading_y = max(94, _safe_top_px + 12)
    text(42, _heading_y, heading, 34 if is_long else 30, paper, bold=True, display=True)
    if mode == "statline_scorecard":
        metrics = data.get("metrics", [])
        teams = data.get("teams", ["ĐỘI A", "ĐỘI B"])
        if not isinstance(metrics, list) or not metrics:
            metrics = []
        top = 230 if is_long else 260
        row_h = 118 if is_long else 178
        text(48, top-58, str(teams[0])[:24].upper(), 18, color("team_home", "#55C7B8"), bold=True)
        text(panel_w-250, top-58, str(teams[1])[:24].upper(), 18, color("team_away", "#F07862"), bold=True)
        if not metrics:
            text(48, top+22, "Chưa có số liệu đã xác minh", 20, muted, bold=True)
        for index, item in enumerate(metrics[:5]):
            if not isinstance(item, dict):
                continue
            y = top + index * row_h
            card_h = row_h-16
            draw.rounded_rectangle((44*scale,(y+5)*scale,(panel_w-44)*scale,(y+card_h)*scale),radius=8*scale,fill=color("ink", "#111721", 226),outline=color("pitch_line", "#658576", 210),width=scale)
            draw.rectangle((44*scale,(y+5)*scale,50*scale,(y+card_h)*scale),fill=series[index % len(series)])
            text(66, y+17, str(item.get("label", "Chỉ số")), 17, paper, bold=True)
            number_y = y+50 if is_long else y+54
            number_size = 48 if is_long else 60
            for value_x, value, tint in (
                (panel_w-360, item.get("home", "—"), color("team_home", "#55C7B8")),
                (panel_w-160, item.get("away", "—"), color("team_away", "#F07862")),
            ):
                stat_font = ImageFont.truetype(str(display_font_path), number_size*scale)
                value_text = str(value)[:12]
                bounds = draw.textbbox((0,0),value_text,font=stat_font)
                draw.text(((value_x-(bounds[2]-bounds[0])/2)*scale,(number_y-bounds[1]/scale)*scale),value_text,font=stat_font,fill=tint)
    elif mode == "source_card":
        source = str(data.get("source") or "Nguồn cần bổ sung")
        date = str(data.get("date") or "Ngày xuất bản cần xác minh")
        claim = str(data.get("claim") or data.get("description") or "Chưa có luận điểm được đối chiếu với nguồn đã duyệt.")
        top = 212 if is_long else 244
        text(54, top, "Nguồn được dùng" if data.get("source") else "Nguồn cần bổ sung", 17, accent, bold=True)
        text(54, top+48, source, 23 if is_long else 20, paper, bold=True)
        text(54, top+83, date, 17, muted)
        draw.line((54*scale, (top+122)*scale, (panel_w-54)*scale, (top+122)*scale), fill=color("pitch_line", "#658576", 200), width=2*scale)
        draw.rectangle((54*scale,(top+150)*scale,59*scale,(top+365)*scale),fill=accent)
        words = textwrap.wrap(claim, width=72 if is_long else 38)
        claim_font_size = 22 if is_long else 20
        for index, line_value in enumerate(words[:5]):
            text(78, top+153+index*(39 if is_long else 43), line_value, claim_font_size, paper)
        url = str(data.get("url") or "")
        if url:
            text(54, panel_h-105, url[:95], 13, muted)
    elif mode == "chart_comparison":
        values = data.get("values", [])
        if not isinstance(values, list):
            values = []
        if values:
            labels = [str(item.get("label", ""))[:22] for item in values[:6] if isinstance(item, dict)]
            numbers = []
            for item in values[:6]:
                try:
                    numbers.append(max(0.0, float(item.get("value", 0))))
                except (TypeError, ValueError, AttributeError):
                    numbers.append(0.0)
            max_value = max(numbers, default=1) or 1
            chart_top = 245 if is_long else 300
            chart_height = 360 if is_long else 600
            left = 340 if is_long else 230
            chart_w = panel_w - left - 96
            for index, (label, number) in enumerate(zip(labels, numbers)):
                step = chart_height // max(1, len(labels))
                y = chart_top + index * step
                text(48, y+1, label, 15, paper, bold=True)
                bar_top = y + (44 if is_long else 46)
                bar_h = 18 if is_long else 24
                bar_w = round(chart_w * number / max_value)
                draw.rounded_rectangle((left*scale, bar_top*scale, (left+chart_w)*scale, (bar_top+bar_h)*scale), radius=5*scale, fill=color("pitch_line", "#658576", 72))
                draw.rounded_rectangle((left*scale, bar_top*scale, (left+max(8,bar_w))*scale, (bar_top+bar_h)*scale), radius=5*scale, fill=series[index % len(series)])
                text(left+chart_w+10, bar_top-5, str(values[index].get("value", "")), 20, series[index % len(series)], bold=True)
        else:
            text(48, (245 if is_long else 310)+30, "Chưa có số liệu đã xác minh", 20, muted, bold=True)
    elif mode == "chart_timeline":
        values = data.get("values", [])
        if isinstance(values, list) and values:
            points = values[:6]
            numeric = []
            for item in points:
                try:
                    numeric.append(float(item.get("value", 0)))
                except (TypeError, ValueError, AttributeError):
                    numeric.append(0.0)
            low, high = min(numeric), max(numeric)
            spread = max(1.0, high-low)
            left, right = (150, panel_w-100) if is_long else (100, panel_w-90)
            top, bottom = (270, 610) if is_long else (360, 780)
            for step in range(4):
                gy = top + (bottom-top)*step/3
                draw.line((left*scale, gy*scale, right*scale, gy*scale), fill=color("pitch_line", "#658576", 100), width=scale)
            coords = []
            for index, number in enumerate(numeric):
                x = left if len(numeric) == 1 else left+(right-left)*index/(len(numeric)-1)
                y = bottom-(number-low)/spread*(bottom-top)
                coords.append((round(x*scale), round(y*scale)))
            if len(coords) > 1:
                draw.line(coords, fill=series[0], width=5*scale, joint="curve")
            for index, (point, item) in enumerate(zip(coords, points)):
                x, y = point
                radius = 9*scale
                draw.ellipse((x-radius,y-radius,x+radius,y+radius), fill=series[index % len(series)], outline=paper, width=2*scale)
                text(x//scale-24, y//scale-42, str(item.get("value", "")), 15, paper, bold=True)
                label = str(item.get("label", ""))[:14]
                text(x//scale-34, bottom+22, label, 12, muted)
        else:
            text(48, (300 if is_long else 360), "Chưa có chuỗi số liệu đã xác minh", 20, muted, bold=True)
    source_name = str(data.get("source") or data.get("source_label") or "Nguồn: cần gắn nguồn đã duyệt")
    source_label = f"{source_name} · {data.get('date')}" if data.get("date") else source_name
    # 12.0.0 safe area: bottom 13% (250px at 1080x1920). Keep source above
    # the exclusion zone; right 7% (76px) for the scene counter.
    _safe_bottom_px = panel_h * (1.0 - 0.13)
    _safe_right_px = panel_w * (1.0 - 0.07)
    text(44, min(panel_h - 48, _safe_bottom_px - 20), source_label[:90], 13, muted)
    text(min(panel_w - 155, _safe_right_px - 40), min(panel_h - 48, _safe_bottom_px - 20), f"{scene_number:02d} / DATA", 13, accent, bold=True)
    image.resize((panel_w, panel_h), Image.Resampling.LANCZOS).save(path)


def _write_ball_sprite(path: Path, palette: dict[str, str]) -> None:
    from PIL import Image, ImageDraw, ImageFilter

    ink = str(palette.get("ink", "#101814"))
    chalk = str(palette.get("chalk", "#F4F3E9"))
    glow = Image.new("RGBA", (72, 72), (0,0,0,0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((7,7,65,65), fill=(209,243,106,90))
    glow = glow.filter(ImageFilter.GaussianBlur(8))
    image = Image.new("RGBA", (72, 72), (0, 0, 0, 0))
    image.alpha_composite(glow)
    draw = ImageDraw.Draw(image)
    draw.ellipse((15, 15, 57, 57), fill=chalk, outline=ink, width=3)
    draw.polygon(((36, 24), (43, 30), (40, 39), (32, 39), (29, 30)), fill=ink)
    draw.line((29,30,22,28,20,37,32,39),fill=ink,width=2)
    draw.line((43,30,50,28,52,37,40,39),fill=ink,width=2)
    draw.line((32,39,29,47,36,52,43,47,40,39),fill=ink,width=2)
    image.save(path)


def _write_pass_trail(path: Path, palette: dict[str, str], angle: float) -> tuple[int, int]:
    from PIL import Image, ImageDraw, ImageFilter

    raw = str(palette.get("signal_lime", "#D1F36A")).lstrip("#")
    lime = tuple(int(raw[i:i+2],16) for i in (0,2,4))
    image = Image.new("RGBA", (132, 24), (0,0,0,0))
    draw = ImageDraw.Draw(image)
    for x in range(132):
        alpha = round(180 * (x / 131) ** 1.4)
        draw.line((x,11,x,13), fill=lime+(alpha,))
    image = image.filter(ImageFilter.GaussianBlur(2))
    image = image.rotate(-angle, resample=Image.Resampling.BICUBIC, expand=True)
    image.save(path)
    return image.size


def _write_backdrop(path: Path, *, width: int, height: int, palette: dict[str, str]) -> None:
    """Create a quiet green tonal field so the fixed template has depth without noise."""
    from PIL import Image, ImageDraw, ImageFilter

    def rgb(name: str, fallback: str) -> tuple[int, int, int]:
        value = str(palette.get(name, fallback)).lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

    top = rgb("ink", "#101814")
    middle = rgb("deep_pitch", "#123A2D")
    bottom = tuple(round(component * 0.72) for component in top)
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        blend = y / max(1, height - 1)
        if blend < 0.52:
            a, b, t = top, middle, blend / 0.52
        else:
            a, b, t = middle, bottom, (blend - 0.52) / 0.48
        row = tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))
        for x in range(width):
            pixels[x, y] = row
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    pitch = rgb("pitch_line", "#477565")
    draw.ellipse((width * 0.08, height * 0.18, width * 0.92, height * 0.88), fill=pitch + (22,))
    glow = glow.filter(ImageFilter.GaussianBlur(max(24, round(width * 0.09))))
    composed = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")
    grain = Image.effect_noise((width, height), 24).convert("RGB")
    Image.blend(composed, grain, 0.035).save(path)


def _beat_fades(events: list[Any], start: float, end: float) -> tuple[bool, bool]:
    """Whether a beat requests fade in/out from its overlapping timeline events."""
    fade_in = False
    fade_out = False
    for item in events:
        if not isinstance(item, dict):
            continue
        try:
            item_start = float(item.get("start_seconds", 0))
            item_end = float(item.get("end_seconds", 0))
        except (TypeError, ValueError):
            continue
        if item_end <= start or item_start >= end:
            continue
        if item.get("enter") == "fade":
            fade_in = True
        if item.get("exit") == "fade":
            fade_out = True
    return fade_in, fade_out


# Fixed role presets for Scene Graph overlays. Geometry / font / color come
# from these locked presets (type + role); the overlay payload contributes
# only text + timing — the renderer never computes per-instance layout.
_SG_OVERLAY_PRESETS: dict[str, dict[str, dict[str, Any]]] = {
    "lower_third": {
        None: {
            "wrap": 34, "max_lines": 2, "fs_frac": 0.022,
            "box_dx": 24, "box_dy_from_bottom": 168, "box_h": 118,
            "box_w_dx": 48, "accent_w": 7, "text_dx": 48,
            "text_dy_from_box": 16,
            "color": "chalk", "accent": "signal_lime",
        },
        "name_tag": {
            "wrap": 30, "max_lines": 1, "fs_frac": 0.020,
            "box_dx": 24, "box_dy_from_bottom": 260, "box_h": 70,
            "box_w_dx": 48, "accent_w": 7, "text_dx": 48,
            "text_dy_from_box": 10,
            "color": "chalk", "accent": "signal_lime",
        },
    },
    "caption": {
        None: {
            "wrap": 40, "max_lines": 2, "fs_frac": 0.028,
            "box_dx": 0, "box_dy_from_bottom": 96, "box_h": 0,
            "box_w_dx": 0, "accent_w": 0, "text_dx": 0,
            "text_dy_from_box": 0,
            "color": "chalk", "accent": "signal_lime", "boxborderw": 14,
        },
        "hook": {
            "wrap": 36, "max_lines": 2, "fs_frac": 0.034,
            "box_dx": 0, "box_dy_from_bottom": 96, "box_h": 0,
            "box_w_dx": 0, "accent_w": 0, "text_dx": 0,
            "text_dy_from_box": 0,
            "color": "signal_lime", "accent": "signal_lime", "boxborderw": 14,
        },
    },
}


def _overlay_items(events: list[Any], start: float, end: float, *,
                   kinds: tuple[str, ...] = ("lower_third", "caption"),
                   limit: int = 6) -> list[dict[str, Any]]:
    """Typed on-screen items whose windows overlap a beat, oldest first."""
    picked: list[dict[str, Any]] = []
    for item in events:
        if not isinstance(item, dict) or item.get("item_type") not in kinds:
            continue
        try:
            item_start = float(item.get("start_seconds", 0))
            item_end = float(item.get("end_seconds", 0))
        except (TypeError, ValueError):
            continue
        if item_end <= start or item_start >= end or item_end <= item_start:
            continue
        picked.append(item)
        if len(picked) >= limit:
            break
    picked.sort(key=lambda item: (float(item.get("start_seconds", 0)),
                                  float(item.get("end_seconds", 0))))
    return picked


def _draw_sg_overlay(
    item: dict[str, Any], window: str, *,
    index: int, job: int, work_dir: Path,
    scene_x: float, scene_y: float, panel_w: float, panel_h: float,
    font_path: str, chalk: str, signal_lime: str, ink: str,
) -> list[str]:
    """FFmpeg drawtext/drawbox filters for ONE frozen graph overlay.

    Geometry / font / color come from fixed role presets (type + role);
    the overlay payload contributes only text + timing. Nothing else is
    derived from the payload — no LLM layout, no per-instance layout.
    `index` / `job` keep the intermediate text file unique per overlay.
    """
    otype = str(item.get("type", "")).strip()
    role = str(item.get("role") or "").strip() or None
    if otype not in ("lower_third", "caption"):
        return []
    preset = (_SG_OVERLAY_PRESETS.get(otype, {}).get(role)
              or _SG_OVERLAY_PRESETS.get(otype, {}).get(None))
    if preset is None:
        return []
    text = str(item.get("text", ""))
    lines = textwrap.wrap(text, width=preset["wrap"], break_long_words=False,
                          break_on_hyphens=False)[: preset["max_lines"]]
    text_path = _write_text(
        work_dir / f"sg-overlay-{index}-{job}-{otype}.txt", "\n".join(lines))
    color = {"chalk": chalk, "signal_lime": signal_lime, "ink": ink}[preset["color"]]
    accent = {"chalk": chalk, "signal_lime": signal_lime, "ink": ink}[preset["accent"]]
    box_x = scene_x + preset["box_dx"]
    box_y = scene_y + panel_h - preset["box_dy_from_bottom"]
    # 12.0.0 safe area: keep overlays out of bottom 13% exclusion zone and
    # left 7% exclusion zone. Clamp so box + text stay inside safe bounds.
    safe_bottom = panel_h * (1.0 - 0.13)
    safe_left = panel_w * 0.07
    box_y = min(box_y, safe_bottom - preset["box_h"])
    box_x = max(box_x, safe_left)
    filters: list[str] = []
    if otype == "lower_third":
        filters.append(
            f"drawbox=x={box_x}:y={box_y}:w={panel_w - preset['box_w_dx']}:h={preset['box_h']}:"
            f"color={accent}@0.78:t=fill:enable='{window}'"
        )
        if preset.get("accent_w"):
            filters.append(
                f"drawbox=x={box_x}:y={box_y}:w={preset['accent_w']}:h={preset['box_h']}:"
                f"color={accent}@1:t=fill:enable='{window}'"
            )
        text_y = min(box_y + preset["text_dy_from_box"], safe_bottom - 24)
        text_x = max(box_x + preset["text_dx"], safe_left + 24)
        filters.append(
            f"drawtext=fontfile='{font_path}':textfile='{text_path}':fontcolor={color}:"
            f"fontsize=h*{preset['fs_frac']:.3f}:line_spacing=7:"
            f"x={text_x}:y={text_y}:"
            f"shadowcolor=black@0.6:shadowx=1:shadowy=2:enable='{window}'"
        )
    else:  # caption
        filters.append(
            f"drawtext=fontfile='{font_path}':textfile='{text_path}':fontcolor={color}:"
            f"fontsize=h*{preset['fs_frac']:.3f}:line_spacing=7:text_align=center:"
            f"x='(w-text_w)/2':y={box_y}:"
            f"box=1:boxcolor=black@0.62:boxborderw={preset.get('boxborderw', 14)}:"
            f"enable='{window}'"
        )
    return filters


def _render(
    root: Path,
    run: dict[str, Any],
    *,
    preview: bool,
    visual_only: bool = False,
    output_name: str,
) -> dict[str, Any]:
    ffmpeg = _ffmpeg(root)
    draft = run.get("draft", {})
    content_type = draft.get("content_type", "short")
    template_id = (
        "allen-knows-ball.longform-analyst"
        if content_type == "long"
        else "allen-knows-ball.shortform-analyst"
    )
    # C1 rights gate: fail fast before resolving the template so an
    # ineligible media slot is refused even if the draft/template bundle is
    # incomplete (e.g. missing catalog.json in a temp root).
    legacy_purpose = _render_purpose(run, draft)
    for _seg in draft.get("segments", []):
        _asset_id = _seg.get("media_asset_id")
        if _asset_id:
            _gate_media_for_use(root, _asset_id, legacy_purpose)
    package = resolve_template(
        root,
        template_id,
        version=draft.get("template_version") if draft.get("template_id") == template_id else None,
        allow_draft=True,
    )
    palette = package.design_tokens.get("palette", {})
    color_systems_path = package.root / "color-systems.json"
    if color_systems_path.is_file():
        color_systems = json.loads(color_systems_path.read_text(encoding="utf-8"))
        colorways = color_systems.get("colorways", [])
        chosen = next((item for item in colorways if item.get("id") == draft.get("colorway")), None)
        if chosen:
            palette = {**palette, **chosen.get("tokens", {})}

    def color_token(name: str) -> str:
        raw = str(palette.get(name, "#101814")).lstrip("#")
        return "0x" + raw.upper()

    chalk = color_token("chalk")
    signal_lime = color_token("signal_lime")
    is_long = content_type == "long"
    output_profile = package.manifest.get("output", {})
    width = int(output_profile.get("width", 1920 if is_long else 1080))
    height = int(output_profile.get("height", 1080 if is_long else 1920))
    fps = int(output_profile.get("frame_rate", 30))
    title = str(draft.get("topic") or "Allen Knows Ball")
    if preview:
        duration = 18
        phase_ranges = [(0, 4), (4, 14), (14, 18)]
        title_text = ("LỢI THẾ SÂN NHÀ?" if run.get("run_id") == "2556c12f9ba8" else title[:150])
    else:
        duration = int(draft.get("duration_target_seconds", 0))
        if duration < (480 if is_long else 20) or duration > (1200 if is_long else 90):
            raise ValueError("The script duration is outside the selected template range.")
        segments = draft.get("segments", [])
        if not segments:
            raise ValueError("The reviewed script has no production segments.")
        phase_ranges = [
            (max(0, int(item.get("start_seconds", 0))), min(duration, int(item.get("end_seconds", 0))))
            for item in segments
        ]
        title_text = ("LỢI THẾ SÂN NHÀ?" if run.get("run_id") == "2556c12f9ba8" else title[:150])

    render_dir = root / "runtime/renders" / str(run["run_id"])
    render_dir.mkdir(parents=True, exist_ok=True)
    work_dir = render_dir / "work"
    work_dir.mkdir(exist_ok=True)
    output_path = render_dir / output_name
    font = package.root / "resources/fonts/BeVietnamPro-Bold.ttf"
    if not font.is_file():
        raise RuntimeError("The template's Vietnamese font file is missing.")
    # 12.0.0 channel identity: display and numerals are set in Tektur
    # (design-tokens typography.display/numeral). Be Vietnam Pro stays the
    # body font. Fall back to Barlow Condensed only if the pack ships without
    # Tektur so a missing font never aborts a render.
    tektur_font = package.root / "resources/fonts/Tektur-Medium.ttf"
    latin_font = tektur_font if tektur_font.is_file() else package.root / "resources/fonts/BarlowCondensed-Bold.ttf"
    if not latin_font.is_file():
        raise RuntimeError("The template's Latin display font file is missing.")
    font_path = str(font).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    latin_font_path = str(latin_font).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")

    backdrop_path = work_dir / "editorial-backdrop.png"
    _write_backdrop(backdrop_path, width=width, height=height, palette=palette)

    # Tactical diagrams are separate timed visual assets; the narrative carries
    # the explanation, so no persistent speech subtitles are rendered.
    filters: list[str] = []
    label_path = _write_text(work_dir / "wordmark.txt", "ALLEN KNOWS BALL")
    # Owner 16/10: no persistent corner wordmark over body scenes (channel
    # mark lives in the 0-1.2s ident + end-card; plates carry the badge).
    title_wrap = 38 if not is_long else 66
    wrapped_title = "\n".join(textwrap.wrap(title_text, width=title_wrap, break_long_words=False, break_on_hyphens=False))
    title_path = _write_text(work_dir / "title.txt", wrapped_title)
    title_end = min(duration, 3.2 if preview else (phase_ranges[0][0] + 2.4 if phase_ranges else 2.4))
    # Title waits for the ident sting so frame 0 never stacks three text layers.
    title_start = min(1.2, max(0.0, title_end - 0.5))
    # Opening ident (timeline opening): wordmark sting over frame 0, out by 1.2s.
    ident_end = min(duration, 1.2)
    filters.append(
        f"drawtext=fontfile='{latin_font_path}':textfile='{label_path}':fontcolor={chalk}:"
        f"fontsize=h*0.070:text_align=center:x='(w-text_w)/2':y=h*0.42:"
        f"shadowcolor=black@0.6:shadowx=2:shadowy=3:enable='between(t,0,{ident_end:.3f})'"
    )
    filters.append(
        f"drawtext=fontfile='{latin_font_path}':textfile='{title_path}':fontcolor={chalk}:"
        f"fontsize=h*{0.044 if is_long else 0.024:.3f}:line_spacing=4:text_align=left:"
        f"x='w*0.09-56*(1-min(max(t/0.28,0),1))^2':y=h*0.125:"
        f"shadowcolor=black@0.55:shadowx=1:shadowy=2:"
        f"enable='between(t,{title_start:.3f},{title_end:.3f})'"
    )
    filters.append(
        f"drawbox=x=iw*0.072:y=ih*0.125:w=iw*0.010:h=ih*0.070:color={signal_lime}@1:t=fill:"
        f"enable='between(t,{title_start:.3f},{title_end:.3f})'"
    )
    segments = [] if preview else draft.get("segments", [])
    # Scene Graph mode (workstream 4, flag-gated): beat timings come from
    # the frozen graphs, never from segment math. Validation raises - the
    # renderer never remaps an unknown mode or a count mismatch.
    sg_graphs = _scene_graph_clip(draft, preview, phase_ranges)
    if sg_graphs is not None:
        phase_ranges = [(float(graph["timing"]["start"]), float(graph["timing"]["end"]))
                        for graph in sg_graphs]
    sg_purpose = _render_purpose(run, draft) if sg_graphs is not None else None
    legacy_purpose = _render_purpose(run, draft)
    sg_media_records: dict[int, dict[str, Any]] = {}
    sg_credit_texts: dict[int, str | None] = {}
    fallback_diagrams = _diagram_specs()
    diagram_specs: list[dict[str, Any]] = []
    scene_paths: list[Path] = []
    scene_text_paths: list[Path | None] = []
    trail_paths: list[Path] = []
    selected_modes: list[str] = []
    punch_beats: set[int] = set()
    kinetic_overlays: dict[int, dict[str, Any]] = {}
    scene_x, scene_y = (190, 220) if is_long else (0, 0)
    fx, fy, fw, fh = (505, 138, 865, 560) if is_long else (260, 142, 490, 760)
    for index in range(len(phase_ranges)):
        spec = None
        segment: dict[str, Any] = {}
        if not preview and index < len(segments):
            segment = segments[index]
            spec = segment.get("tactical_diagram")
        if sg_graphs is not None:
            # Frozen mode, verbatim. No silent remap, no timeline-driven
            # mode switch (both are storytelling decisions).
            mode = str(sg_graphs[index].get("mode"))
        else:
            mode = str(segment.get("visual_mode", "tactical_explainer"))
        supported_modes = {"tactical_explainer", "statline_scorecard", "source_card", "chart_comparison", "chart_timeline", "media_b_roll", "hook_card", "player_card", "comparison_duel", "stat_leader", "player_poster", "goal_card", "fixture_card", "score_card", "duel_columns", "player_poster_side", "player_poster_top", "fixture_list", "quote_card", "potm_card", "discipline_card", "welcome_card"}
        if sg_graphs is None and mode not in supported_modes:
            mode = "tactical_explainer"
        # A typed timeline event can select a dedicated data layout when the
        # segment has not explicitly selected a visual mode.
        if sg_graphs is None and not segment.get("visual_mode"):
            event_types = {item.get("item_type") for item in segment.get("timeline_events", []) if isinstance(item, dict)}
            if "stat_card" in event_types:
                mode = "statline_scorecard"
            elif "source_card" in event_types:
                mode = "source_card"
        selected_modes.append(mode)
        beat_graphic = segment.get("graphic_data", {}) if isinstance(segment.get("graphic_data"), dict) else {}
        # Scene Graph mode executes frozen motion only: hook_punch_in and
        # number_pop punch in (numerals stay frozen, no re-layout). Per-beat
        # motion choice and kinetic text re-wraps stay banned.
        if sg_graphs is not None:
            sg_motion = sg_graphs[index].get("motion")
            sg_motion = sg_motion if isinstance(sg_motion, dict) else {}
            if sg_motion.get("enter") == "hook_punch_in" or sg_motion.get("effect") == "number_pop":
                punch_beats.add(index)
        elif mode == "hook_card" or (mode == "statline_scorecard" and isinstance(beat_graphic.get("hero"), dict)):
            punch_beats.add(index)
        hook_text = str(beat_graphic.get("hook_text", "")).strip() if isinstance(beat_graphic, dict) else ""
        hero = beat_graphic.get("hero") if isinstance(beat_graphic, dict) else None
        try:
            from apps.card_selector import STARTERS_SHORT as _STARTERS
            _starter_ok = (sg_graphs is None and not is_long and _STARTERS.get(mode)
                           and not (segment.get("media_asset_id") if isinstance(segment, dict) else None))
        except Exception:
            _starter_ok = False
        # Starter scenes carry their own text: legacy kinetic text overlays
        # below are gated on not _starter_ok so nothing renders twice (owner 16/10).
        # Scene Graph mode skips the legacy kinetic overlays (re-wraps banned)
        # and instead draws frozen overlays from sg_graphs[index]["overlays"]
        # in the scene paint/filter path below.
        if sg_graphs is None and mode == "hook_card" and hook_text and not _starter_ok:
            kinetic_overlays[index] = {"kind": "hook", "text": hook_text}
        elif (sg_graphs is None and mode == "statline_scorecard" and isinstance(hero, dict)
                and str(hero.get("value", "")).strip() and not beat_graphic.get("metrics")
                and not _starter_ok):
            kinetic_overlays[index] = {"kind": "hero", "value": str(hero.get("value", ""))[:12]}
        scene_palette = dict(palette)
        graphic_data = segment.get("graphic_data", {}) if isinstance(segment.get("graphic_data"), dict) else {}
        media_record = None
        if sg_graphs is not None:
            # Frozen media only: planner-approved refs resolve through the
            # verified/active gate plus the upload-intent scope (both raise
            # when denied). The mode stays verbatim - never forced, never
            # dropped.
            frozen_params = sg_graphs[index].get("params")
            frozen_params = frozen_params if isinstance(frozen_params, dict) else {}
            frozen_graphic = frozen_params.get("graphic_data")
            graphic_data = dict(frozen_graphic) if isinstance(frozen_graphic, dict) else {}
            gated_record, gated_credit = _scene_graph_media(root, sg_graphs[index], sg_purpose)
            if gated_record is not None:
                media_record = gated_record
                sg_media_records[index] = gated_record
                sg_credit_texts[index] = gated_credit
        elif not preview and segment.get("media_asset_id"):
            media_record = _library_image_record(root, str(segment["media_asset_id"]))
            # C1 rights gate: the asset must be eligible for this exact upload
            # use, not merely rights-verified. Refuse (raise) instead of
            # silently painting an ineligible asset.
            _gate_media_for_use(root, str(segment["media_asset_id"]), legacy_purpose)
            if mode in {"player_card", "player_poster", "player_poster_side", "player_poster_top",
                            "potm_card", "welcome_card", "score_card", "quote_card"}:
                graphic_data = {
                    **graphic_data,
                    "media_file": str(media_record["path"]),
                    "media_creator": media_record.get("creator"),
                    "media_license": media_record.get("license_type"),
                }
            else:
                mode = "media_b_roll"
                selected_modes[-1] = mode
        elif mode == "media_b_roll" and sg_graphs is None:
            mode = "tactical_explainer"
            selected_modes[-1] = mode
        for role in ("team_home", "team_away"):
            supplied = str(graphic_data.get(f"{role}_color", ""))
            if len(supplied) == 7 and supplied.startswith("#") and all(ch in "0123456789abcdefABCDEF" for ch in supplied[1:]):
                scene_palette[role] = supplied
        if not isinstance(spec, dict):
            spec = fallback_diagrams[index % len(fallback_diagrams)]
        diagram_specs.append(spec)
        scene_path = work_dir / f"tactical-scene-{index}.png"
        scene_text_paths.append(None)
        if sg_graphs is not None:
            # Execute the frozen graph verbatim (absolute layers only).
            returned_text = _write_scene_graph_beat(
                scene_path,
                sg_graphs[index],
                root=root,
                font_path=font,
                display_font_path=latin_font,
                palette=scene_palette,
                is_long=is_long,
                scene_number=index + 1,
                media_record=media_record,
                credit_text=sg_credit_texts.get(index),
                text_path=work_dir / f"tactical-text-{index}.png",
            )
            scene_text_paths[index] = returned_text
        elif mode == "tactical_explainer":
            if is_long:
                starter_card = graphic_data.get("tactical_card", "") if isinstance(graphic_data, dict) else ""
                try:
                    _write_starter_scene(scene_path, str(starter_card))
                except (ValueError, OSError, KeyError):
                    _write_tactical_scene(
                        scene_path,
                        width=width,
                        height=height,
                        font_path=font,
                        display_font_path=latin_font,
                        palette=scene_palette,
                        spec=spec,
                        is_long=is_long,
                        scene_number=index+1,
                        scene_count=len(phase_ranges),
                    )
            else:
                # Short-form: composite the owner pack background declared by
                # graphic-templates.json (pack_bg: short-tactical_explainer.png)
                # instead of the procedural pitch plate, restoring the 12.0.0
                # Cyber Pitch identity. Headline (if supplied) is drawn into the
                # locked box; the renderer never invents layout.
                _write_editorial_data_scene(
                    scene_path,
                    font_path=font,
                    display_font_path=latin_font,
                    mode="tactical_explainer",
                    data=graphic_data,
                    palette=scene_palette,
                    is_long=is_long,
                    scene_number=index+1,
                )
        elif mode == "media_b_roll" and media_record:
            media_metadata = media_record["metadata"]
            media_data = {
                **graphic_data,
                "media_file": str(media_record["path"]),
                "media_caption": segment.get("media_caption") or segment.get("visual"),
                "media_creator": media_record.get("creator"),
                "media_license": media_record.get("license_type"),
                "media_title": media_metadata.get("visual_context_note") or Path(str(media_record["path"])).stem,
            }
            _write_editorial_data_scene(
                scene_path,
                font_path=font,
                display_font_path=latin_font,
                mode=mode,
                data=media_data,
                palette=scene_palette,
                is_long=is_long,
                scene_number=index+1,
            )
        else:
            starter_img = None
            starter_text = None
            try:
                if not is_long and not segment.get("media_asset_id"):
                    from apps.card_selector import STARTERS_SHORT as _SS2
                    from apps.studio_templates.starter_scenes import render_starter_layers as _rsl
                    layers = _rsl(mode, graphic_data, segment.get("evidence_refs", []),
                                  _SS2.get(mode))
                    if layers is not None:
                        starter_img, starter_text = layers
            except Exception:
                starter_img, starter_text = None, None
            if starter_img is not None:
                starter_img.convert("RGB").save(scene_path)
                if starter_text is not None:
                    text_path = work_dir / f"tactical-text-{index}.png"
                    starter_text.save(text_path)
                    scene_text_paths[index] = text_path
            else:
                scene_text_paths[index] = None
                _write_editorial_data_scene(
                    scene_path,
                    font_path=font,
                    display_font_path=latin_font,
                    mode=mode,
                    data=graphic_data,
                    palette=scene_palette,
                    is_long=is_long,
                    scene_number=index+1,
                    bare=index in kinetic_overlays,
                )
        scene_paths.append(scene_path)
        from math import atan2, degrees
        vector = spec.get("pass_vector", {})
        p1, p2 = vector.get("from", [0.18,0.5]), vector.get("to", [0.72,0.35])
        if is_long:
            dx, dy = (float(p2[0])-float(p1[0]))*fw, (float(p2[1])-float(p1[1]))*fh
        else:
            dx, dy = (float(p2[1])-float(p1[1]))*fw, -(float(p2[0])-float(p1[0]))*fh
        trail_path = work_dir / f"pass-trail-{index}.png"
        _write_pass_trail(trail_path, palette, degrees(atan2(dy, dx)))
        trail_paths.append(trail_path)
    ball_sprite = work_dir / "football.png"
    _write_ball_sprite(ball_sprite, palette)
    # Authored ending card (owner 16/10): the prebuilt C-10 end card closes
    # short videos instead of bare background+text. +4s music tail.
    # Scene Graph mode skips it: the ending must arrive as a frozen graph
    # beat - the renderer never appends story beats on its own.
    ending_path = None
    out_duration = duration
    if not preview and not visual_only and not is_long and sg_graphs is None:
        try:
            from pathlib import Path as _P
            from apps.studio_templates.render_starters import render_design as _render_design
            epath = _P(__file__).resolve().parents[0] / "studio_templates" / "C-10.short.json"
            edata = json.loads(epath.read_text(encoding="utf-8"))
            for _c in edata["pages"][0]["children"]:
                if (isinstance(_c, dict) and _c.get("type") == "text"
                        and (_c.get("custom") or {}).get("slot") == "credit"):
                    _c["showInExport"] = False
            ending_path = work_dir / "ending-scene.png"
            _render_design(edata).convert("RGB").save(ending_path)
            out_duration = duration + 4
        except Exception:
            ending_path = None
            out_duration = duration

    for index, (start, end) in enumerate(phase_ranges):
        if end <= start:
            continue
        start = min(max(0, start), duration - 1)
        end = min(max(start + 1, end), duration)
        beat_enable = f"between(t,{start:.3f},{end:.3f})"
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-framerate", str(fps), "-i", str(backdrop_path),
    ]
    audio_path = None
    if not preview and not visual_only:
        voice_name = str(run.get("voice_preview", {}).get("path", ""))
        voice_root = (root / "runtime/voice").resolve()
        audio_path = (voice_root / voice_name).resolve()
        if audio_path.parent != voice_root or not audio_path.is_file():
            raise ValueError("Generate and audit the local voice preview before rendering the full run.")
        command += ["-i", str(audio_path)]
    sound = None
    sound_note = None
    if not preview and not visual_only:
        # Locked soundpack: bed + fixed stingers under the voice. Any pack
        # problem degrades to voice-only with a report note — music never
        # blocks a video.
        try:
            from apps.soundpack.pack import (
                audio_filter,
                plan_stingers,
                resolve_sound,
                sound_enabled,
            )
            draft_for_sound = draft if isinstance(draft, dict) else {}
            if sound_enabled(root):
                resolved = resolve_sound(
                    root,
                    str(draft_for_sound.get("story_form", "")),
                    str(draft_for_sound.get("content_type", "short")),
                    override=run.get("soundpack_override"),
                )
                if resolved.get("enabled"):
                    chapter_starts = [
                        float(event.get("start_seconds", 0) or 0)
                        for event in (draft_for_sound.get("chapter_events", []) or [])
                        if isinstance(event, dict)]
                    planned = plan_stingers(
                        resolved.get("stingers", []), chapter_starts,
                        float(duration),
                        Path(root) / "soundpacks" / "v1" / "tracks")
                    command += ["-stream_loop", "-1", "-i", resolved["bed_file"]]
                    bed_index = 2
                    sting_indices = []
                    for planned_sting in planned:
                        command += ["-i", planned_sting["file"]]
                        sting_indices.append(bed_index + 1 + len(sting_indices))
                    audio_mix = audio_filter(
                        1, bed_index, sting_indices, planned, float(duration),
                        float(resolved.get("mix_volume", 0.1) or 0.1),
                        resolved.get("sidechain") or {})
                    sound = {
                        "pack_version": resolved.get("pack_version"),
                        "bed_id": resolved.get("bed_id"),
                        "bed_file": Path(resolved["bed_file"]).name,
                        "mood": resolved.get("mood", ""),
                        "license": resolved.get("license", ""),
                        "stingers": [{
                            "sting_id": item.get("sting_id"), "at": item.get("at"),
                            "volume": item.get("volume")} for item in planned],
                        "mix": "sidechain-ducked bed + fixed stings, loudnorm I=-14",
                    }
                else:
                    sound_note = str(resolved.get("reason", "soundpack disabled"))
            else:
                sound_note = "SOUNDPACK_ENABLED=false"
        except (ValueError, OSError) as error:
            sound = None
            sound_note = str(error)[:200]
    scene_input_start = 2 if not preview and not visual_only else 1
    if sound is not None:
        scene_input_start += 1 + len(sound["stingers"])
    for scene_path in scene_paths:
        command += ["-loop", "1", "-framerate", str(fps), "-i", str(scene_path)]
    ball_input_start = scene_input_start + len(scene_paths)
    for _ in scene_paths:
        command += ["-loop", "1", "-framerate", str(fps), "-i", str(ball_sprite)]
    trail_input_start = ball_input_start + len(scene_paths)
    for trail_path in trail_paths:
        command += ["-loop", "1", "-framerate", str(fps), "-i", str(trail_path)]
    # Layered starter text: one transparent input per beat that has it.
    text_input_index: dict[int, int] = {}
    next_input = trail_input_start + len(trail_paths)
    for index, text_path in enumerate(scene_text_paths):
        if text_path is None:
            continue
        command += ["-loop", "1", "-framerate", str(fps), "-i", str(text_path)]
        text_input_index[index] = next_input
        next_input += 1
    ending_idx: int | None = None
    if ending_path is not None:
        command += ["-loop", "1", "-framerate", str(fps), "-i", str(ending_path)]
        ending_idx = next_input
        next_input += 1

    # Composite a research-informed Match Dossier tactical plate for each active
    # diagram beat, then animate the ball along its reviewed pass vector.
    chains: list[str] = []
    current = "0:v"
    panel_w, panel_h = (1540, 840) if is_long else (1080, 1920)
    # 12.0.0 safe area: top 9 / bottom 13 / left 7 / right 7 percent.
    # Overlays and on-screen text must stay inside these bounds.
    safe_top = panel_h * 0.09
    safe_bottom = panel_h * (1.0 - 0.13)
    safe_left = panel_w * 0.07
    safe_right = panel_w * (1.0 - 0.07)
    full_segments = draft.get("segments", []) if isinstance(draft.get("segments"), list) else []
    chapter_pool = draft.get("chapter_events", []) if isinstance(draft.get("chapter_events"), list) else []
    fades_used = 0
    overlays_used = 0
    punch_used = 0
    slide_used = 0
    stagger_used = 0
    count_used = 0
    for index, ((start, end), spec) in enumerate(zip(phase_ranges, diagram_specs)):
        if end <= start:
            continue
        scene_label = f"scene{index}"
        scene_idx = scene_input_start + index
        scene_enable = f"gte(t,{start:.3f})*lt(t,{end:.3f})"
        scene_slide = f"18*(1-min(max((t-{start:.3f})/0.24,0),1))^2"
        scene_y_expr = f"{scene_y}+{scene_slide}"
        # Frozen transition: chalk_line_wipe executes as the standard 0.3s
        # slide-in; clean_cut suppresses the slide (hard cut).
        sg_transition = sg_graphs[index].get("transition") if sg_graphs is not None else None
        sg_cut = (isinstance(sg_transition, dict) and sg_transition.get("in") == "clean_cut")
        # 12.0.0: at most two signature transitions per video. Slide-in only
        # on the first two beats; every later beat hard-cuts in.
        _use_slide = (not sg_cut) and (index < 2)
        enter_slide = "0" if (sg_cut or not _use_slide) else f"{panel_w}*max(0,1-(t-{start:.3f})/0.3)"
        beat_events: list[Any] = list(chapter_pool)
        if not preview and index < len(full_segments) and isinstance(full_segments[index], dict):
            beat_events += full_segments[index].get("timeline_events", [])
        fade_in, fade_out = _beat_fades(beat_events, start, end)
        if sg_graphs is not None:
            # Frozen enter only: fade_0_3s fades the beat in and out.
            # Timeline enter/exit flags are not consulted (outside the
            # graph contract).
            sg_enter = sg_graphs[index].get("motion")
            sg_enter = sg_enter.get("enter") if isinstance(sg_enter, dict) else None
            fade_in = fade_out = (sg_enter == "fade_0_3s")
        if fade_in or fade_out:
            fades_used += 1
        scene_source = f"{scene_idx}:v"
        if selected_modes[index] == "media_b_roll":
            media_layer = f"mediamotion{index}"
            media_width, media_height = (1540, 840) if is_long else (1080, 1920)
            media_fades = ""
            if sg_graphs is not None and fade_in:
                media_fades += f",fade=t=in:st={start:.3f}:d=0.45:alpha=1"
            if sg_graphs is not None and fade_out:
                media_fades += f",fade=t=out:st={max(start, end - 0.45):.3f}:d=0.45:alpha=1"
            chains.append(
                f"[{scene_idx}:v]zoompan=z='min(1.035,zoom+0.00002)':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
                f"s={media_width}x{media_height}:fps={fps},format=rgba{media_fades}[{media_layer}]"
            )
            scene_source = media_layer
        else:
            # Ken Burns drift on every static plate so no beat ever sits still.
            # Alternate push-in / pull-out per beat for editorial variety.
            # Nova hook and hero beats punch in faster instead.
            motion_label = f"scenemotion{index}"
            if index in punch_beats:
                zoom_expr = "min(1.12,zoom+0.0012)"
                punch_used += 1
            elif index % 2 == 0:
                zoom_expr = "min(1.07,zoom+0.0004)"
            else:
                zoom_expr = "if(eq(on,0),1.07,max(zoom-0.0004,1.0))"
            motion_chain = (
                f"[{scene_idx}:v]zoompan=z='{zoom_expr}':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
                f"s={panel_w}x{panel_h}:fps={fps},format=rgba"
            )
            fade_chain = ""
            if fade_in:
                fade_chain += f",fade=t=in:st={start:.3f}:d=0.45:alpha=1"
            if fade_out:
                fade_chain += f",fade=t=out:st={max(start, end - 0.45):.3f}:d=0.45:alpha=1"
            chains.append(f"{motion_chain}{fade_chain}[{motion_label}]")
            scene_source = motion_label
        chains.append(
            f"[{current}][{scene_source}]overlay=x='{scene_x}+{enter_slide}':y='{scene_y_expr}':eval=frame:eof_action=pass:format=auto:"
            f"enable='{scene_enable}'[{scene_label}]"
        )
        if not sg_cut and _use_slide:
            slide_used += 1
        # 12.0.0 prohibits glitch / RGB-split / flashing effects. Beats enter
        # with the locked 0.3s slide-in or a clean cut only; no per-entrance
        # flash strips are emitted, so signature transitions stay within the
        # template limit and no prohibited effect reaches the output.
        current = scene_label
        if index in text_input_index:
            # Type entrances after the plate lands: same drift as its
            # background, fade in at +0.6s, out with the beat.
            tidx = text_input_index[index]
            if index in punch_beats:
                tzoom = "min(1.12,zoom+0.0012)"
            elif index % 2 == 0:
                tzoom = "min(1.07,zoom+0.0004)"
            else:
                tzoom = "if(eq(on,0),1.07,max(zoom-0.0004,1.0))"
            tin = min(start + 0.6, end - 1.0)
            chains.append(
                f"[{tidx}:v]zoompan=z='{tzoom}':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
                f"s={panel_w}x{panel_h}:fps={fps},format=rgba,"
                f"fade=t=in:st={tin:.3f}:d=0.45:alpha=1,"
                f"fade=t=out:st={max(start, end - 0.45):.3f}:d=0.45:alpha=1[text{index}]"
            )
            chains.append(
                f"[{current}][text{index}]overlay=x='{scene_x}+{enter_slide}':y='{scene_y_expr}':eval=frame:eof_action=pass:format=auto:"
                f"enable='{scene_enable}'[textlayer{index}]"
            )
            current = f"textlayer{index}"
        # Scene Graph mode skips the authored ball/trail pass: its vector
        # comes from an unfrozen fallback storyboard, not the graph.
        if sg_graphs is not None or selected_modes[index] != "tactical_explainer":
            continue
        vector = spec.get("pass_vector", {})
        start_point = vector.get("from", [0.18, 0.5])
        end_point = vector.get("to", [0.72, 0.35])
        sx, sy = max(0.02, min(0.96, float(start_point[0]))), max(0.02, min(0.96, float(start_point[1])))
        ex, ey = max(0.02, min(0.96, float(end_point[0]))), max(0.02, min(0.96, float(end_point[1])))
        pass_duration = min(0.8, max(0.5, (end - start) * 0.12))
        progress = f"min(max((t-{start:.3f})/{pass_duration:.3f},0),1)"
        eased = f"(({progress})*({progress})*(3-2*({progress})))"
        ball_label = f"ball{index}"
        ball_idx = ball_input_start + index
        if is_long:
            dx, dy = (ex-sx)*fw, (ey-sy)*fh
            ball_x = f"{scene_x+fx-36}+{fw}*({sx:.4f}+({ex-sx:.4f})*{eased})"
            ball_y = f"({scene_y_expr})+{fy-36}+{fh}*({sy:.4f}+({ey-sy:.4f})*{eased})"
        else:
            dx, dy = (ey-sy)*fw, -(ex-sx)*fh
            ball_x = f"{scene_x+fx-36}+{fw}*({sy:.4f}+({ey-sy:.4f})*{eased})"
            ball_y = f"({scene_y_expr})+{fy-36}+{fh}*(1-({sx:.4f}+({ex-sx:.4f})*{eased}))"
        from math import hypot
        vector_length = max(1.0,hypot(dx,dy))
        ux, uy = dx/vector_length, dy/vector_length
        trail_path = trail_paths[index]
        from PIL import Image
        with Image.open(trail_path) as trail_image:
            trail_w, trail_h = trail_image.size
        trail_x = f"({ball_x})+36-({ux:.6f})*56-{trail_w/2:.1f}"
        trail_y = f"({ball_y})+36-({uy:.6f})*56-{trail_h/2:.1f}"
        trail_label = f"trail{index}"
        trail_idx = trail_input_start + index
        chains.append(
            f"[{current}][{trail_idx}:v]overlay=x='{trail_x}':y='{trail_y}':eval=frame:format=auto:"
            f"enable='gte(t,{start:.3f})*lt(t,{start+pass_duration:.3f})'[{trail_label}]"
        )
        current = trail_label
        chains.append(
            f"[{current}][{ball_idx}:v]overlay=x='{ball_x}':"
            f"y='{ball_y}':"
            f"eval=frame:eof_action=pass:format=auto:enable='{scene_enable}'[{ball_label}]"
        )
        current = ball_label
    if ending_idx is not None:
        # Authored ending card closes the video (owner 16/10): full-bleed
        # C-10 plate with a gentle push-in, takeaway/version text drawn
        # over it by the endcard block below.
        chains.append(
            f"[{ending_idx}:v]zoompan=z='min(1.05,zoom+0.0006)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
            f"s={panel_w}x{panel_h}:fps={fps},format=rgba,"
            f"fade=t=in:st={duration:.3f}:d=0.5:alpha=1[endcard]"
        )
        chains.append(
            f"[{current}][endcard]overlay=x=0:y=0:eval=frame:eof_action=pass:format=auto:"
            f"enable='gte(t,{duration:.3f})'[endcarded]"
        )
        current = "endcarded"
    # Typed on-screen items declared in the production timeline. Lower-thirds
    # identify who/what is on screen; captions carry the hook for muted
    # viewers. Both sit above every scene layer.

    for index, (start, end) in enumerate(phase_ranges):
        if end <= start:
            continue
        pool: list[Any] = list(chapter_pool)
        if not preview and index < len(full_segments) and isinstance(full_segments[index], dict):
            pool += full_segments[index].get("timeline_events", [])
        if sg_graphs is not None:
            # Frozen graph overlays only: read from sg_graphs[index]["overlays"],
            # never re-derive composition from timeline_events/segment (the
            # composition is frozen by ws3; the renderer only executes).
            graph_overlays = sg_graphs[index].get("overlays")
            overlay_items = list(graph_overlays) if isinstance(graph_overlays, list) else []
        else:
            overlay_items = _overlay_items(pool, start, end)
        for job, item in enumerate(overlay_items):
            try:
                if sg_graphs is not None:
                    # Overlay thoi gian clip-relative (0 = dau beat): chuyen
                    # sang thoi gian tuyet doi cua mot lan duyet, dong cua so
                    # [timing.start, timing.end]. Khong doc lai
                    # timeline_events/segment de tai suy overlay o che do SG.
                    graph_start = float(sg_graphs[index]["timing"]["start"])
                    graph_end = float(sg_graphs[index]["timing"]["end"])
                    overlay_start = float(item.get("start_seconds", 0))
                    overlay_end = float(item.get("end_seconds", graph_end - graph_start))
                    item_start = max(graph_start, graph_start + overlay_start)
                    item_end = min(graph_end, graph_start + overlay_end)
                else:
                    item_start = max(start, float(item.get("start_seconds", start)))
                    item_end = min(end, float(item.get("end_seconds", end)))
            except (TypeError, ValueError):
                continue
            if item_end <= item_start:
                continue
            raw_text = _normalise(str(item.get("text", "")))
            if not raw_text:
                continue
            window = f"between(t,{item_start:.3f},{item_end:.3f})"
            if sg_graphs is not None:
                # Frozen graph overlay: fixed role preset (type + role); the
                # payload contributes only text + timing — no LLM layout, no
                # per-instance coordinates/font/color/motion.
                filters.extend(
                    _draw_sg_overlay(
                        item, window,
                        index=index, job=job, work_dir=work_dir,
                        scene_x=scene_x, scene_y=scene_y, panel_w=panel_w, panel_h=panel_h,
                        font_path=font_path, chalk=chalk, signal_lime=signal_lime,
                        ink=color_token("ink"),
                    )
                )
            elif item.get("item_type") == "lower_third":
                lines = textwrap.wrap(raw_text, width=34, break_long_words=False,
                                       break_on_hyphens=False)[:2]
                text_path = _write_text(work_dir / f"lower-{index}-{job}.txt", "\n".join(lines))
                box_y = min(scene_y + panel_h - 168, safe_bottom - 118)
                box_x = max(scene_x + 24, safe_left)
                box_w = min(panel_w - 48, safe_right - box_x)
                filters.append(
                    f"drawbox=x={box_x}:y={box_y}:w={box_w}:h=118:"
                    f"color={color_token('ink')}@0.78:t=fill:enable='{window}'"
                )
                filters.append(
                    f"drawbox=x={box_x}:y={box_y}:w=7:h=118:"
                    f"color={signal_lime}@1:t=fill:enable='{window}'"
                )
                filters.append(
                    f"drawtext=fontfile='{font_path}':textfile='{text_path}':fontcolor={chalk}:"
                    f"fontsize=h*0.022:line_spacing=7:"
                    f"x={box_x + 24}:y={min(box_y + 16, safe_bottom - 40)}:"
                    f"shadowcolor=black@0.6:shadowx=1:shadowy=2:enable='{window}'"
                )
            else:
                lines = textwrap.wrap(raw_text, width=40, break_long_words=False,
                                       break_on_hyphens=False)[:2]
                text_path = _write_text(work_dir / f"caption-{index}-{job}.txt", "\n".join(lines))
                filters.append(
                    f"drawtext=fontfile='{font_path}':textfile='{text_path}':fontcolor={chalk}:"
                    f"fontsize=h*0.028:line_spacing=7:text_align=center:"
                    f"x='(w-text_w)/2':y={min(scene_y + panel_h - 96, safe_bottom - 60)}:"
                    f"box=1:boxcolor=black@0.62:boxborderw=14:enable='{window}'"
                )
            overlays_used += 1
        # Impact kinetic type: staggered hook lines and count-up numerals.
        # Plates render bare for these beats so text reveals in motion.
        kin = kinetic_overlays.get(index)
        if kin is not None and not preview and end > start:
            if kin["kind"] == "hook":
                hook_fs = round(panel_h * (0.105 if is_long else 0.061))
                _kin_hook = str(kin["text"])
                _kin_accents = list(re.finditer(r"\*([^*]+)\*", _kin_hook))
                if _kin_accents:
                    _kin_first = _kin_accents[0].group(1)
                    _kin_hook = re.sub(r"\*", "", _kin_hook)
                    _kin_hook = _kin_hook.replace(_kin_first, f"*{_kin_first}*", 1)
                else:
                    _kin_hook = re.sub(r"\*", "", _kin_hook)
                hook_block = _hook_lines(_kin_hook, max_lines=1)[:1]
                for line_no, line_value in enumerate(hook_block):
                    window_start = min(end - 0.2, start + line_no * 0.18)
                    line_path = _write_text(work_dir / f"hook-{index}-{line_no}.txt", line_value)
                    filters.append(
                        f"drawtext=fontfile='{latin_font_path}':textfile='{line_path}':fontcolor={chalk}:"
                        f"fontsize={hook_fs}:line_spacing=6:text_align=center:"
                        f"x='(w-text_w)/2':y={scene_y + panel_h // 2 - len(hook_block) * (hook_fs + 14) // 2 + line_no * (hook_fs + 14)}:"
                        f"shadowcolor=black@0.55:shadowx=1:shadowy=2:enable='between(t,{window_start:.3f},{end:.3f})'"
                    )
                    stagger_used += 1
            elif kin["kind"] == "hero":
                hero_fs = round(panel_h * (0.20 if is_long else 0.158))
                hero_steps = _count_steps(kin["value"])
                for step_no, step_value in enumerate(hero_steps):
                    step_start = start + (end - start) * step_no / len(hero_steps)
                    step_end = start + (end - start) * (step_no + 1) / len(hero_steps)
                    step_path = _write_text(work_dir / f"hero-{index}-{step_no}.txt", step_value)
                    filters.append(
                        f"drawtext=fontfile='{latin_font_path}':textfile='{step_path}':fontcolor={signal_lime}:"
                        f"fontsize={hero_fs}:text_align=center:"
                        f"x='(w-text_w)/2':y={scene_y + panel_h // 2 - 30 - hero_fs // 2}:"
                        f"shadowcolor=black@0.55:shadowx=2:shadowy=3:enable='between(t,{step_start:.3f},{step_end:.3f})'"
                    )
                    count_used += 1
    # Branded end-card closes the arc inside the final seconds: wordmark,
    # channel tagline, loop-callback takeaway, and template version.
    # Owner 16/10: with the authored C-10 ending plate, drop the ink veil
    # and the big wordmark (both baked); takeaway/version/tagline stay.
    end_start = max(0.0, out_duration - (4.0 if ending_path is not None else 2.5))
    tagline = ""
    if isinstance(package.channel, dict):
        tagline = _normalise(str(package.channel.get("tagline", "")))[:120]
    if ending_path is None:
        filters.append(
            f"drawbox=x=0:y=0:w=iw:h=ih:color={color_token('ink')}@0.94:t=fill:"
            f"enable='gte(t,{end_start:.3f})'"
        )
        filters.append(
            f"drawtext=fontfile='{latin_font_path}':textfile='{label_path}':fontcolor={signal_lime}:"
            f"fontsize=h*0.055:text_align=center:x='(w-text_w)/2':y=h*0.40:"
            f"enable='gte(t,{end_start:.3f})'"
        )
    if tagline:
        tagline_path = _write_text(work_dir / "endcard-tagline.txt", tagline)
        filters.append(
            f"drawtext=fontfile='{font_path}':textfile='{tagline_path}':fontcolor={chalk}:"
            f"fontsize=h*0.026:text_align=center:x='(w-text_w)/2':y=h*0.52:"
            f"enable='gte(t,{end_start:.3f})'"
        )
    version_path = _write_text(
        work_dir / "endcard-version.txt",
        f"{template_id}  ·  v{package.manifest.get('version', '?')}",
    )
    takeaway = ""
    if not preview and full_segments and isinstance(full_segments[-1], dict):
        takeaway = _normalise(str(full_segments[-1].get("narration", "")))[:90]
    if takeaway:
        takeaway_path = _write_text(work_dir / "endcard-takeaway.txt", f"“{takeaway}”")
        filters.append(
            f"drawtext=fontfile='{font_path}':textfile='{takeaway_path}':fontcolor={chalk}:"
            f"fontsize=h*0.024:line_spacing=6:text_align=center:x='(w-text_w)/2':y=h*0.30:"
            f"box=1:boxcolor=black@0.55:boxborderw=10:enable='gte(t,{end_start:.3f})'"
        )
    filters.append(
        f"drawtext=fontfile='{latin_font_path}':textfile='{version_path}':fontcolor={chalk}:"
        f"fontsize=h*0.018:text_align=center:x='(w-text_w)/2':y=h*0.60:"
        f"enable='gte(t,{end_start:.3f})'"
    )
    chains.append(f"[{current}]{','.join(filters)}[vout]")
    if sound is not None:
        chains.append(audio_mix[0])
    filter_complex = ";".join(chains)
    command += ["-filter_complex", filter_complex, "-map", "[vout]", "-t", str(out_duration), "-r", str(fps), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
    if preview or visual_only:
        command += ["-an"]
    elif sound is not None:
        # With an authored ending tail, hold the full outro (bed loops on);
        # otherwise stop at the shortest stream as before.
        command += ["-map", audio_mix[1], "-c:a", "aac", "-b:a", "192k"] + ([] if ending_path is not None else ["-shortest"])
    else:
        command += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "192k"] + ([] if ending_path is not None else ["-shortest"])
    command += ["-movflags", "+faststart", str(output_path)]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=7200)
    if result.returncode:
        raise RuntimeError((result.stderr or "FFmpeg render failed.")[-2500:])

    selected_media = []
    # Scene Graph mode attributes the frozen graph assets (already
    # rights-gated at scene-paint time); legacy mode reads the segments.
    sg_media_jobs: list[dict[str, Any]] | None = None
    if sg_graphs is not None:
        from apps.measurement.render_qa import graph_asset_refs as _sg_refs

        sg_media_jobs = []
        for graph in sg_graphs:
            for ref in _sg_refs(graph):
                graphic = (graph.get("params") or {}).get("graphic_data") or {}
                if not isinstance(graphic, dict):
                    graphic = {}
                sg_media_jobs.append({
                    "media_asset_id": ref["asset_id"],
                    "media_caption": graphic.get("media_caption"),
                    "visual": graphic.get("media_caption"),
                })
    for item in (sg_media_jobs if sg_media_jobs is not None else (draft.get("segments", []) if not preview else [])):
        asset_id = str(item.get("media_asset_id", "")) if isinstance(item, dict) else ""
        if not asset_id:
            continue
        record = _library_image_record(root, asset_id)
        selected_media.append({
            "asset_id": asset_id,
            "creator": record.get("creator"),
            "source_url": record.get("source_url"),
            "license": record.get("license_type"),
            "caption": item.get("media_caption") or item.get("visual"),
            "visual_context_note": record["metadata"].get("visual_context_note"),
        })
    checks = [
        {"criterion": "Video file created and playable", "status": "PASS", "detail": "FFmpeg produced an H.264 MP4 and ffprobe confirms its stream metadata."},
        {"criterion": "Target aspect ratio", "status": "PASS", "detail": f"{width}×{height} ({'16:9' if is_long else '9:16'})."},
        {"criterion": "Vietnamese font and diacritics", "status": "NEEDS_REVIEW", "detail": "Barlow Condensed provides Vietnamese headline glyphs; Be Vietnam Pro remains available for dense supporting copy. Glyph rendering not inspected on actual frames — owner eyeball required."},
        {"criterion": "Tactical pitch orientation and authored vectors", "status": "NOT USED" if not any(mode == "tactical_explainer" for mode in selected_modes) else "NEEDS_REVIEW", "detail": "No tactical pitch scene is part of this short-form script." if not any(mode == "tactical_explainer" for mode in selected_modes) else f"The {('landscape' if is_long else 'portrait')} pitch has authored markings and vectors; vector/marking clarity not inspected on actual frames — owner eyeball required."},
        {"criterion": "Template art direction", "status": "NEEDS_REVIEW", "detail": "Touchline Editorial pairs expressive Vietnamese display headlines, condensed chapter numerals, tactile pitch marks, contextual colorways, and distinct portrait/landscape graphic plates. Art direction not inspected on actual frames — owner eyeball required."},
        {"criterion": "Opening / body / ending rhythm", "status": "NEEDS_REVIEW", "detail": "0-1.2s channel ident sting; chapter-led visual beats open on the match hook; takeaway callback leads into the branded end-card with wordmark, tagline, and template version. Rhythm not inspected on actual frames — owner eyeball required."},
        {"criterion": "Visible motion and beat changes", "status": "NEEDS_REVIEW", "detail": f"Slide-in executes on {slide_used} scene plates (at most two signature transitions); alternating Ken Burns push-in/pull-out drift runs underneath; tactical diagrams add one authored pass movement with ball and trail. Motion appearance not inspected on actual frames — owner eyeball required."},
        {"criterion": "Narration subtitles", "status": "NOT USED", "detail": "Subtitles are intentionally omitted; the narration carries the explanation."},
        {"criterion": "Personal voice and speech pacing", "status": "PENDING OWNER AUDIT" if not preview and not visual_only else "NOT ASSESSED", "detail": "TTS preview is muxed as one continuous narration track; naturalness and voice similarity await owner review." if not preview and not visual_only else ("Voice evaluation is intentionally excluded from this benchmark." if visual_only else "This is a silent visual preview.")},
        {"criterion": "Asset Library media", "status": "PASS" if selected_media else ("NOT ASSESSED" if preview else "FAIL"), "detail": f"{len(selected_media)} verified, attributed library images are used as contextual B-roll; they are not footage from the current Premier League matches." if selected_media else ("Media placement is exercised in full runs, not in silent template previews." if preview else "No verified library media is attached to this script.")},
        {"criterion": "Lower-third and caption overlays", "status": "PASS" if overlays_used else "NOT USED", "detail": f"{overlays_used} lower-third/caption overlay(s) rendered in their declared windows." if overlays_used else "No lower-third or caption overlay is declared or rendered."},
        {"criterion": "Script-specific transitions and effects", "status": "PARTIAL", "detail": f"chalk_line_wipe executes as 0.3s slide-in on {slide_used} scene(s); fade in/out executes from timeline enter/exit on {fades_used} beat(s); hook/hero punch-in executes on {punch_used} beat(s); all other beats cut clean. draw/wipe transitions and freeze_and_trace/pitch_grid effects remain unexecuted."},
        {"criterion": "Impact kinetic type: stagger and count-up", "status": "PASS" if (stagger_used or count_used) else "NOT USED", "detail": f"Hook lines stagger across {stagger_used} overlay(s); hero numerals count up across {count_used} step(s)." if (stagger_used or count_used) else "This script uses no kinetic hook or hero-numeral beat."},
        {"criterion": "Nova hook card and hero metric", "status": "PASS" if punch_used else "NOT USED", "detail": f"Hook punch-in / hero pop executes on {punch_used} beat(s)." if punch_used else "This script uses no hook card or hero-metric beat."},
    ]
    probe = _ffprobe(ffmpeg)
    probe_result = subprocess.run(
        [probe, "-v", "error", "-show_entries", "format=duration,size:stream=codec_name,width,height,codec_type", "-of", "json", str(output_path)],
        capture_output=True, text=True, timeout=30,
    )
    if probe_result.returncode:
        raise RuntimeError("FFprobe could not inspect the rendered MP4.")
    metadata = json.loads(probe_result.stdout)
    actual_duration = float(metadata.get("format", {}).get("duration", 0) or 0)
    duration_ok = abs(actual_duration - duration) <= max(1.0, duration * 0.01)
    checks.append({
        "criterion": "Output duration matches target",
        "status": "PASS" if duration_ok else "FAIL",
        "detail": f"Target {duration}s; rendered {actual_duration:.2f}s.",
    })
    video_streams = [item for item in metadata.get("streams", []) if item.get("codec_type") == "video"]
    audio_streams = [item for item in metadata.get("streams", []) if item.get("codec_type") == "audio"]
    audio_ok = preview or visual_only or bool(audio_streams)
    checks.append({
        "criterion": "Expected audio stream",
        "status": "PASS" if audio_ok else "FAIL",
        "detail": "Silent preview is intentional." if preview else ("Narration audio stream is present." if audio_ok else "No audio stream was found."),
    })
    if not preview and not visual_only:
        if sound is not None:
            run["soundpack"] = {**sound, "note": None}
            checks.append({
                "criterion": "Locked soundpack bed and stingers",
                "status": "PASS" if audio_ok else "FAIL",
                "detail": (f"Bed {sound['bed_id']} ({sound['license']}) ducked under voice plus "
                           f"{len(sound['stingers'])} fixed stinger(s); loudnorm I=-14."),
            })
        else:
            run["soundpack"] = {"enabled": False, "note": sound_note}
            checks.append({
                "criterion": "Locked soundpack bed and stingers",
                "status": "NOT USED",
                "detail": f"Voice-only render ({sound_note or 'soundpack off'}).",
            })
    # Scene Graph mode: QA the ACTUAL rendered beats (frozen geometry +
    # rendered pixels + both workstream-1 rights gates). Verdicts are
    # PASS | FAIL | NEEDS_REVIEW with evidence; pixel checks that lack
    # their layer NEEDS_REVIEW instead of passing blind.
    sg_qa: dict[str, Any] | None = None
    if sg_graphs is not None:
        from PIL import Image as _Image

        from apps.measurement.render_qa import qa_clip as _qa_clip

        sg_full: list[Any] = []
        sg_bg: list[Any] = []
        for beat_index, beat_graph in enumerate(sg_graphs):
            try:
                beat_bg = _Image.open(scene_paths[beat_index]).convert("RGBA")
            except (OSError, ValueError):
                sg_full.append(None)
                sg_bg.append(None)
                continue
            beat_text_path = scene_text_paths[beat_index]
            if beat_graph.get("kind") == "starter":
                sg_bg.append(beat_bg.convert("RGB"))
                if beat_text_path is not None and Path(beat_text_path).is_file():
                    try:
                        beat_tx = _Image.open(beat_text_path).convert("RGBA")
                        if beat_tx.size != beat_bg.size:
                            beat_tx = beat_tx.resize(beat_bg.size)
                        sg_full.append(_Image.alpha_composite(beat_bg, beat_tx).convert("RGB"))
                    except (OSError, ValueError):
                        sg_full.append(beat_bg.convert("RGB"))
                else:
                    sg_full.append(beat_bg.convert("RGB"))
            else:
                sg_full.append(beat_bg.convert("RGB"))
                sg_bg.append(None)
        sg_narrations: dict[str, str] = {}
        for seg in (draft.get("segments", []) if isinstance(draft.get("segments"), list) else []):
            if isinstance(seg, dict) and seg.get("segment_id") and isinstance(seg.get("narration"), str):
                sg_narrations[str(seg["segment_id"])] = str(seg["narration"])
        sg_qa = _qa_clip(
            sg_graphs,
            sg_full,
            bg_images=sg_bg,
            narrations=sg_narrations,
            duration_target=float(duration),
            roles=None,
            root=root,
            purpose=sg_purpose,
        )
        checks.extend(sg_qa["checks"])
    if not video_streams:
        raise RuntimeError("The rendered MP4 has no video stream.")
    report = {
        "run_id": run["run_id"],
        "rendered_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "renderer": "ace-ffmpeg-0.9.0",
        "template_id": template_id,
        "template_version": package.manifest["version"],
        "mode": "template_visual_preview" if preview else ("silent_longform_visual_benchmark" if visual_only else "full_script_render"),
        "output": output_path.name,
        "selected_media": selected_media,
        "soundpack": run.get("soundpack"),
        "quality_checks": checks,
        "scene_graph_qa": (
            {"mode": "scene_graph", "verdict": sg_qa["verdict"],
             "ready": sg_qa["ready"],
             "scenes": sg_qa["scenes"], "clip_checks": sg_qa["clip_checks"]}
            if sg_qa is not None else None
        ),
        "ffprobe": metadata,
        "limitations": ([
            "TTS voice naturalness and similarity have not been audited by the owner.",
            "The library images are contextual soccer photographs, not current Premier League match action.",
            "Still photographs use a slow camera push rather than live match motion; this benchmark tests workflow feasibility, not publish-ready aesthetics.",
            "Only fade in/out transitions execute; slide, draw, wipe, and the declared effect set remain unexecuted.",
        ] if not preview and not visual_only else ["This is a silent visual-only benchmark and does not include narration audio."]),
    }
    (render_dir / "render-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "video_url": f"/api/render/{run['run_id']}/{output_path.name}",
        "report": report,
        "rendered": True,
    }


def render_template_preview(root: Path, run_id: str) -> dict[str, Any]:
    if not _safe_run_id(run_id):
        raise ValueError("Production run ID is invalid.")
    path = root / "runtime/runs" / f"{run_id}.json"
    if not path.is_file():
        raise ValueError("Production run was not found.")
    run = json.loads(path.read_text(encoding="utf-8"))
    return _render(root, run, preview=True, output_name="template-preview.mp4")


def render_visual_only_run(root: Path, run_id: str) -> dict[str, Any]:
    """Render a full-length private visual benchmark without invoking TTS."""
    if not _safe_run_id(run_id):
        raise ValueError("Production run ID is invalid.")
    path = root / "runtime/runs" / f"{run_id}.json"
    if not path.is_file():
        raise ValueError("Production run was not found.")
    run = json.loads(path.read_text(encoding="utf-8"))
    draft = run.get("draft", {})
    if draft.get("content_type") != "long":
        raise ValueError("The visual benchmark requires a long-form draft.")
    if not any(isinstance(item, dict) and item.get("media_asset_id") for item in draft.get("segments", [])):
        raise ValueError("Attach at least one selected Asset Library image before rendering the visual benchmark.")
    from apps.card_selector import apply_card_plan

    apply_card_plan(root, run)
    return _render(root, run, preview=False, visual_only=True, output_name="visual-benchmark-silent.mp4")


def _voice_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        rate = wav.getframerate() or 1
        return wav.getnframes() / rate


def _ensure_voice_fits_script(root: Path, run: dict[str, Any]) -> None:
    """Fail loudly instead of silently truncating an overlong narration."""
    from apps.content_workflow import MAX_SPEECH_OVERRUN

    voice_name = str(run.get("voice_preview", {}).get("path", ""))
    voice_root = (root / "runtime/voice").resolve()
    audio_path = (voice_root / voice_name).resolve()
    if audio_path.parent != voice_root or not audio_path.is_file():
        raise ValueError("Generate and audit the local voice preview before rendering the full run.")
    try:
        target = int(run.get("draft", {}).get("duration_target_seconds", 0))
    except (TypeError, ValueError):
        target = 0
    if target <= 0:
        return
    actual = _voice_duration_seconds(audio_path)
    if actual > target * MAX_SPEECH_OVERRUN:
        raise ValueError(
            f"Voice preview runs {actual:.0f}s but the video slot is {target}s; "
            "shorten the narration or regenerate the voice before full rendering."
        )


def render_full_run(root: Path, run_id: str) -> dict[str, Any]:
    if not _safe_run_id(run_id):
        raise ValueError("Production run ID is invalid.")
    path = root / "runtime/runs" / f"{run_id}.json"
    if not path.is_file():
        raise ValueError("Production run was not found.")
    run = json.loads(path.read_text(encoding="utf-8"))
    if not run.get("script_owner_approved"):
        raise ValueError("Approve and verify the script before full rendering.")
    if not run.get("voice_preview_audited"):
        raise ValueError("Listen to and approve the generated voice preview before full rendering.")
    _ensure_voice_fits_script(root, run)
    from apps.card_selector import apply_card_plan

    apply_card_plan(root, run)
    # Scene Graph production path: build + gắn frozen graphs trước khi render.
    # Flag tắt: giữ legacy path byte-identical, không build graphs. Flag bật:
    # build_run_scene_graphs gắn run["draft"]["scene_graphs"]; raise rõ nếu
    # không thể build/validate (fail closed, không rơi về legacy).
    if os.environ.get("ACE_SCENE_GRAPH_RENDER") == "1":
        from apps.scene_graph.pipeline import build_run_scene_graphs
        build_run_scene_graphs(root, run)  # mutate run["draft"]["scene_graphs"]; raise nếu fail
    result = _render(root, run, preview=False, output_name="full-render.mp4")
    run["render"] = {
        "path": "full-render.mp4",
        "rendered_at": result["report"]["rendered_at"],
        "report": "render-report.json",
    }
    run["status"] = "WAITING_FOR_RENDER_AUDIT"
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


# ---------------------------------------------------------------------------
# Scene Graph execution path (workstream 4).
#
# Boundary: the renderer draws frozen Scene Graphs and executes their frozen
# motion vocabulary with the existing primitives. It NEVER decides
# storytelling or layout here: no mode/starter selection, no timeline-driven
# mode switching, no text re-wrapping (hook stagger, count-up, phrase
# balancing), no media auto-attach, no invented ending card. Unknown modes,
# pending (uncleared) assets and unverified media raise loudly instead of
# falling back - fallback decisions belong to the planner + builder
# (apps.scene_graph.builder).
#
# Schema is owned by workstream 3 (apps/scene_graph/schema.py); this path
# consumes it via validate_scene_graph and apps.scene_graph.executor only.
# Media rights call the workstream-1 checks: verified + active library
# records with files inside runtime/assets/library, then is_usable_for()
# against the upload intent (platform/territory from the run's
# distribution destinations; never guessed). Crest slots keep the
# monogram-initials fallback until a licensed file lands
# (apps.sportskit.crests.resolve_crest). Pillow draws the static layers.
#
# Frozen motion executes verbatim with the existing grammar: hook_punch_in
# and number_pop -> fast punch zoom (numerals stay frozen, no re-layout);
# slide_in_right_0_3s -> standard 0.3s slide-in; fade_0_3s -> fade in/out;
# chalk_line_wipe -> 0.3s slide-in; clean_cut -> hard cut (slide
# suppressed). Anything outside this table is a planner/builder gap, and
# QA NEEDS_REVIEWs it instead of the renderer inventing motion.
#
# Gated by ACE_SCENE_GRAPH_RENDER=1 plus draft["scene_graphs"] (one graph
# per segment, validated up front). Default off: legacy behavior is
# byte-identical when the flag is unset.
# ---------------------------------------------------------------------------

SCENE_GRAPH_RENDER_ENV = "ACE_SCENE_GRAPH_RENDER"


def _scene_graph_clip(
    draft: dict[str, Any],
    preview: bool,
    phase_ranges: list[tuple[int, int]],
) -> list[dict[str, Any]] | None:
    """Validate the draft's frozen Scene Graphs, or None for legacy path.

    Flag-off (ACE_SCENE_GRAPH_RENDER != "1") is the ONLY legacy path —
    preview does not gate scene-graph mode. When the flag is "1" and the
    draft carries no frozen scene_graphs, the renderer refuses to fall back
    to legacy and raises ValueError (fail-closed).
    """
    if os.environ.get(SCENE_GRAPH_RENDER_ENV) != "1":
        return None
    graphs = draft.get("scene_graphs")
    if not graphs:
        raise ValueError(
            "ACE_SCENE_GRAPH_RENDER=1 but draft.scene_graphs is missing/empty — refusing legacy fallback."
        )
    if not isinstance(graphs, list):
        raise ValueError("draft scene_graphs must be a list of Scene Graphs.")
    from apps.scene_graph.schema import validate_scene_graph

    checked = [validate_scene_graph(graph) for graph in graphs]
    if len(checked) != len(phase_ranges):
        raise ValueError(
            f"scene_graphs carries {len(checked)} beat(s) but the draft has "
            f"{len(phase_ranges)} segment(s); the planner must emit exactly "
            "one Scene Graph per segment."
        )
    return checked


def _render_purpose(run: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any] | None:
    """Upload intent for the per-purpose media scope check, or None.

    Uses the same normalizer as the card selector
    (``apps.card_selector.normalize_upload_purpose``) so selector and
    renderer see identical platform/territory/commercial/monetization.
    Imported lazily inside the function to avoid a module import cycle.
    Missing platform/territory -> None: the scope gate stays unevaluated
    (QA NEEDS_REVIEWs it) instead of guessing an upload scope.
    """
    from apps.card_selector import normalize_upload_purpose

    return normalize_upload_purpose(run, draft)


def _scene_graph_media(
    root: Path, graph: dict[str, Any], purpose: dict[str, Any] | None = None
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve the media this scene paints: (record, credit_text_override).

    Returns (None, None) for media-free scenes. Every painted asset must be
    planner-approved AND verified/active/with-file; when the upload intent
    is known the workstream-1 scope gate must additionally allow it.
    Anything else raises - no silent drop, no substitution. Monogram
    fallbacks paint no image and need no resolution.
    """
    from apps.measurement.render_qa import graph_asset_refs

    if not isinstance(graph, dict):
        raise ValueError("scene graph media: graph must be an object")
    if graph.get("kind") == "starter":
        return None, None  # frozen design pixels only; portraits unused
    refs = [ref for ref in graph_asset_refs(graph)
            if ref.get("kind") == "library_image"]
    if str(graph.get("mode", "")) != "media_b_roll":
        if refs:
            raise ValueError(
                f"scene graph beat {graph.get('segment_id', '?')} carries media refs "
                "on a non-b-roll primitive the frozen design cannot paint; "
                "the planner must re-freeze the beat."
            )
        return None, None
    if not refs:
        raise ValueError(
            f"scene graph b-roll beat {graph.get('segment_id', '?')} names no "
            "frozen asset; the planner must freeze one - the renderer never "
            "picks media."
        )
    ref = refs[0]
    if ref.get("approval_status") == "pending":
        raise ValueError(
            f"library asset {ref['asset_id']} is frozen as approval_status=pending "
            f"({ref.get('rights_scope')}); the planner did not clear it - "
            "route to human rights review instead of rendering."
        )
    # Full-row probe (same shape QA uses): gate-1 on verified/active/file,
    # then the scope gate on the complete record incl. source_type and any
    # persisted rights_scope_json. Never migrates the user DB.
    from apps.measurement.render_qa import _registry_row

    row, error = _registry_row(Path(root), ref["asset_id"])
    if error is not None and error not in ("", "absent"):
        raise ValueError(
            f"library asset {ref['asset_id']} is unverifiable at render time: "
            f"{error}; refusing to paint it."
        )
    if error == "absent" or row is None:
        raise ValueError(
            f"library asset {ref['asset_id']} does not exist in the registry."
        )
    if row.get("asset_type") != "image" or row.get("rights_state") != "verified" \
            or row.get("lifecycle_state") != "active":
        raise ValueError(
            f"library asset {ref['asset_id']} is {row.get('asset_type')}/"
            f"{row.get('rights_state')}/{row.get('lifecycle_state')} - only "
            "verified + active images may render."
        )
    library_root = (Path(root) / "runtime/assets/library").resolve()
    try:
        image_path = (Path(root) / str(row.get("stored_path") or "")).resolve()
    except Exception:
        raise ValueError(
            f"library asset {ref['asset_id']} has an unresolvable stored_path."
        )
    if library_root not in image_path.parents or not image_path.is_file():
        raise ValueError(
            f"library asset {ref['asset_id']} file is missing or outside "
            "runtime/assets/library."
        )
    try:
        import json as _json

        metadata = _json.loads(row.get("metadata_json") or "{}")
        metadata = metadata if isinstance(metadata, dict) else {}
    except ValueError:
        metadata = {}
    record = {
        "asset_id": ref["asset_id"],
        "path": image_path,
        "source_url": row.get("source_url"),
        "creator": row.get("creator"),
        "license_type": row.get("license_type"),
        "metadata": metadata,
    }
    credit_text: str | None = None
    if purpose is not None:
        from apps.asset_library.rights_scope import is_usable_for

        scope_out = is_usable_for(row, purpose)
        if not scope_out.get("allowed"):
            raise ValueError(
                f"library asset {ref['asset_id']} denied for this upload: "
                f"{'; '.join(str(r) for r in scope_out.get('reasons', []))} "
                f"(action: {scope_out.get('required_action')})."
            )
        credit = (scope_out.get("scope") or {}).get("credit") or {}
        if credit.get("required") and isinstance(credit.get("text"), str) and credit["text"].strip():
            credit_text = credit["text"].strip()[:80]
    return record, credit_text


def _scene_graph_plate(
    root: Path, canvas: dict[str, Any]
) -> tuple[dict[str, str], Path, Path]:
    """Read-only palette + brand fonts for media primitives (released pack)."""
    anchor = Path(__file__).resolve().parents[1]
    is_long = (int(canvas.get("width", 0)), int(canvas.get("height", 0))) == (1920, 1080)
    package_id = ("allen-knows-ball.longform-analyst" if is_long
                  else "allen-knows-ball.shortform-analyst")
    package = resolve_template(anchor, package_id, allow_draft=True)
    palette = package.design_tokens.get("palette", {})
    font = package.root / "resources/fonts/BeVietnamPro-Bold.ttf"
    latin = package.root / "resources/fonts/BarlowCondensed-Bold.ttf"
    if not font.is_file() or not latin.is_file():
        raise RuntimeError("The template's brand font files are missing.")
    return palette, font, latin


def _paint_broll_primitive(
    out: Path,
    graph: dict[str, Any],
    record: dict[str, Any],
    credit_text: str | None,
    palette: dict[str, str],
    font_path: Path,
    display_font_path: Path,
    is_long: bool,
) -> None:
    """Paint the owner-fixed b-roll void (contained photo, never cover)."""
    params = graph.get("params") if isinstance(graph.get("params"), dict) else {}
    params = params if isinstance(params, dict) else {}
    graphic = params.get("graphic_data")
    graphic = dict(graphic) if isinstance(graphic, dict) else {}
    _write_editorial_data_scene(
        out,
        font_path=font_path,
        display_font_path=display_font_path,
        mode="media_b_roll",
        data={
            **graphic,
            "media_file": str(record["path"]),
            "media_caption": graphic.get("media_caption")
            or record["metadata"].get("visual_context_note")
            or "",
            "media_creator": record.get("creator"),
            "media_license": credit_text or record.get("license_type"),
        },
        palette=palette,
        is_long=is_long,
        scene_number=int(graph.get("index", 0)) + 1,
    )


def render_scene_png(
    graph: dict[str, Any],
    path: str | Path,
    *,
    root: str | Path | None = None,
    purpose: dict[str, Any] | None = None,
) -> Path:
    """Render ONE frozen Scene Graph to a PNG (single scene/frame verify).

    Validate -> rights-gate media (planner approval + verified/active/file
    + optional upload-intent scope) -> execute verbatim -> save. Raises on
    invalid graphs, unknown modes, pending assets and unverified/denied
    media. Pillow draws the static layers; no motion, no storytelling.
    """
    from apps.scene_graph import executor as _executor
    from apps.scene_graph.schema import validate_scene_graph

    checked = validate_scene_graph(graph)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if checked.get("kind") == "starter":
        image = _executor.render_scene_graph(checked)
        image.convert("RGB").save(out)
        return out
    if checked.get("mode") != "media_b_roll":
        image = _executor.render_scene_graph(checked)
        image.convert("RGB").save(out)
        return out
    if root is None:
        raise ValueError(
            "scene graph b-roll needs a library root to resolve its "
            "rights-verified image; refusing to render without one."
        )
    record, credit_text = _scene_graph_media(Path(root), checked, purpose)
    if record is None:  # pragma: no cover - _scene_graph_media raises first
        raise ValueError("scene graph b-roll resolved to no media record.")
    canvas = checked.get("canvas", {})
    palette, font, latin = _scene_graph_plate(Path(root), canvas)
    width, height = int(canvas.get("width", 1080)), int(canvas.get("height", 1920))
    _paint_broll_primitive(out, checked, record, credit_text, palette,
                           font, latin, (width, height) == (1920, 1080))
    return out


def _write_scene_graph_beat(
    scene_path: Path,
    graph: dict[str, Any],
    *,
    root: Path,
    font_path: Path,
    display_font_path: Path,
    palette: dict[str, str],
    is_long: bool,
    scene_number: int,
    media_record: dict[str, Any] | None,
    credit_text: str | None,
    text_path: Path,
) -> Path | None:
    """Paint one clip beat from its frozen graph. Returns the text layer path.

    Starter graphs split into background + text layers (type entrances
    after the plate lands); b-roll paints the owner-fixed void from the
    already-gated record; other primitives execute verbatim. Raises on
    missing b-roll media instead of substituting.
    """
    from apps.scene_graph import executor as _executor

    if graph.get("kind") == "starter":
        bg_image, text_image = _executor.render_scene_graph_layers(graph)
        bg_image.convert("RGB").save(scene_path)
        if text_image is not None:
            text_image.save(text_path)
            return text_path
        return None
    if graph.get("mode") == "media_b_roll":
        if media_record is None:
            raise ValueError(
                f"scene graph beat {graph.get('segment_id', '?')} reached paint "
                "with no gated media record; unverified or missing media "
                "blocks the render instead of falling back."
            )
        _paint_broll_primitive(scene_path, graph, media_record, credit_text,
                               palette, font_path, display_font_path, is_long)
        return None
    image = _executor.render_scene_graph(graph)
    image.convert("RGB").save(scene_path)
    return None
