"""Sports Kit v9 plates: dedicated PIL renderer built from reference anatomy.

See docs/sport-design-research.md. Every plate is original code; no reference
asset is copied. Values render only from reviewed data with source+date.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any

KIT_MODES = (
    "duel_columns", "stat_leader", "player_poster_side", "player_poster_top",
    "goal_card", "fixture_card", "fixture_list", "score_card", "quote_card",
    "potm_card", "discipline_card", "welcome_card",
)

PALETTE = {
    "kit_red": "#C8102E",
    "kit_dark_red": "#7E0A1E",
    "ink": "#0B0D10",
    "paper": "#F5F1E6",
    "navy": "#0A1A3C",
    "orange": "#E8590C",
    "winner_lime": "#8CFF00",
    "muted": "#9AA3A8",
}


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


class KitFonts:
    def __init__(self, resource_dir: Path) -> None:
        from PIL import ImageFont

        def load(name: str, size: int) -> Any:
            return ImageFont.truetype(str(resource_dir / name), size)

        self._load = load
        self._dir = resource_dir

    def barlow(self, size: int) -> Any:
        return self._load("BarlowCondensed-Bold.ttf", size)

    def barlow_sb(self, size: int) -> Any:
        return self._load("BarlowCondensed-SemiBold.ttf", size)

    def bev(self, size: int) -> Any:
        return self._load("BeVietnamPro-Regular.ttf", size)

    def bev_b(self, size: int) -> Any:
        return self._load("BeVietnamPro-Bold.ttf", size)

    def brush(self, size: int) -> Any:
        try:
            return self._load("PermanentMarker-Regular.woff", size)
        except (OSError, ValueError):
            return self.barlow(size)


def _fit_font(draw: Any, text: str, face: Any, start: int, max_width: int,
              minimum: int = 20) -> Any:
    size = start
    while size > minimum:
        font = face(size) if callable(face) else face
        try:
            width = draw.textbbox((0, 0), text, font=font)[2]
        except (ValueError, TypeError):
            break
        if width <= max_width:
            return font
        size -= 6
    return face(minimum) if callable(face) else face


def _center(draw: Any, cx: int, y: int, text: str, font: Any,
            fill: tuple[int, int, int, int]) -> int:
    width = draw.textbbox((0, 0), text, font=font)[2]
    draw.text((cx - width / 2, y), text, font=font, fill=fill)
    bounds = draw.textbbox((0, 0), text, font=font)
    return bounds[3] - bounds[1]


def _wrap(text: str, width: int) -> list[str]:
    import textwrap

    return textwrap.wrap(" ".join(str(text).split()), width=width)


def _grain(image: Any, density: int = 500) -> None:
    from PIL import ImageDraw as _Draw

    rng = random.Random(11)
    draw = _Draw.Draw(image, "RGBA")
    width, height = image.size
    for _ in range(density):
        x = rng.uniform(0, width)
        y = rng.uniform(0, height)
        draw.point((x, y), fill=(245, 241, 230, 12))


def _vignette(image: Any, strength: int = 50) -> None:
    from PIL import Image as _Image, ImageDraw as _Draw

    width, height = image.size
    layer = _Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay = _Draw.Draw(layer)
    for x in range(width):
        alpha = round(strength * max(0.0, 1.0 - min(x, width - 1 - x) / (width * 0.10)))
        if alpha:
            overlay.line((x, 0, x, height), fill=(0, 0, 0, alpha))
    for y in range(height):
        alpha = round(strength * max(0.0, 1.0 - min(y, height - 1 - y) / (height * 0.10)))
        if alpha:
            overlay.line((0, y, width, y), fill=(0, 0, 0, alpha))
    image.alpha_composite(layer)


def _torn_paste(base: Any, photo: Any, box: tuple[int, int, int, int],
                edge: str = "right", teeth: int = 26, depth: int = 26) -> None:
    """Paste photo into box with one torn edge (jagged mask + light rim)."""
    from PIL import Image as _Image, ImageDraw as _Draw, ImageOps as _Ops

    x1, y1, x2, y2 = box
    width, height = x2 - x1, y2 - y1
    fitted = _Ops.fit(photo.convert("RGB"), (width, height),
                      method=_Image.Resampling.LANCZOS).convert("RGBA")
    mask = _Image.new("L", (width, height), 255)
    painter = _Draw.Draw(mask)
    rng = random.Random(7)
    if edge == "right":
        xs = [width - rng.uniform(4, depth) for _ in range(teeth + 1)]
        poly = [(0, 0)] + [(x, int(i * height / teeth)) for i, x in enumerate(xs)]
        poly += [(0, height)]
        painter.polygon(poly, fill=255)
        painter.polygon([(0, 0), (width, 0), (width, height), (0, height)], fill=0)
        painter.polygon(poly, fill=255)
    elif edge == "bottom":
        ys = [height - rng.uniform(4, depth) for _ in range(teeth + 1)]
        poly = [(0, 0), (width, 0)] + [(int(i * width / teeth), y) for i, y in enumerate(ys)]
        painter.polygon([(0, 0), (width, 0), (width, height), (0, height)], fill=0)
        painter.polygon(poly + [(0, height)], fill=255)
    else:  # left
        xs = [rng.uniform(4, depth) for _ in range(teeth + 1)]
        poly = [(width, 0), (width, height)] + [(x, int(i * height / teeth)) for i, x in enumerate(xs)]
        painter.polygon([(0, 0), (width, 0), (width, height), (0, height)], fill=0)
        painter.polygon(poly, fill=255)
    base.alpha_composite(fitted, (x1, y1), mask)


def _ticker(base: Any, fonts: KitFonts, text: str, *, y: int, angle: float,
            band: tuple[int, int, int], ink_: tuple[int, int, int],
            size: int = 30) -> None:
    from PIL import Image as _Image, ImageDraw as _Draw

    strip = _Image.new("RGBA", (base.width * 2, size * 3), band + (255,))
    painter = _Draw.Draw(strip)
    font = fonts.bev_b(size)
    repeated = ((text.upper() + "  •  ") * 20)[:220]
    painter.text((10, size // 2), repeated, font=font, fill=ink_ + (255,))
    rotated = strip.rotate(angle, expand=True, resample=_Image.Resampling.BICUBIC)
    base.alpha_composite(rotated, (-base.width // 4, y))


def _marquee(draw: Any, fonts: KitFonts, width: int, y: int, text: str,
             fill: tuple[int, int, int, int], size: int = 22) -> None:
    font = fonts.barlow_sb(size)
    repeated = ((text.upper() + "  ") * 30)[:200]
    draw.text((16, y), repeated, font=font, fill=fill)


def _shield(draw: Any, cx: int, cy: int, size: int,
            outline: tuple[int, int, int, int], width: int = 4) -> None:
    w, h = size, int(size * 1.2)
    draw.polygon([
        (cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2),
        (cx + w / 2, cy + h * 0.1), (cx, cy + h / 2), (cx - w / 2, cy + h * 0.1),
    ], outline=outline, width=width)


def _photo_or(device: str, path: str, fallback_color: tuple[int, int, int]) -> Any:
    from PIL import Image as _Image

    try:
        candidate = Path(str(path))
        if candidate.is_file():
            with _Image.open(candidate) as opened:
                return opened.copy()
    except (OSError, ValueError):
        pass
    raise LookupError(device)


def render_plate(mode: str, data: dict[str, Any], fonts: KitFonts,
                 palette: dict[str, str] | None = None,
                 is_long: bool = False) -> Any:
    """Render one Sports Kit plate. Raises LookupError only for photo modes
    without an approved portrait (caller falls back to typographic plate)."""
    from PIL import Image as _Image, ImageDraw as _Draw

    panel_w, panel_h = (1920, 1080) if is_long else (1080, 1920)
    scale = 2
    width, height = panel_w * scale, panel_h * scale

    def color(key: str, fallback: str, alpha: int = 255) -> tuple[int, int, int, int]:
        raw = str((palette or {}).get(key, fallback)).lstrip("#")
        return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16), alpha)

    red = color("kit_red", PALETTE["kit_red"])
    dark_red = color("kit_dark_red", PALETTE["kit_dark_red"])
    ink = color("ink", PALETTE["ink"])
    paper = color("chalk", PALETTE["paper"])
    navy = color("navy", PALETTE["navy"]) if "navy" in (palette or {}) else _hex(PALETTE["navy"]) + (255,)
    orange = color("orange", PALETTE["orange"]) if "orange" in (palette or {}) else _hex(PALETTE["orange"]) + (255,)
    lime = color("winner_lime", PALETTE["winner_lime"]) if "winner_lime" in (palette or {}) else _hex(PALETTE["winner_lime"]) + (255,)
    muted = color("muted", PALETTE["muted"])
    black = (0, 0, 0, 255)

    image = _Image.new("RGBA", (width, height), ink)
    draw = _Draw.Draw(image, "RGBA")
    source = str(data.get("source") or "Nguon can xac minh")[:60]
    date = str(data.get("date") or "")[:40]

    def credit(bottom: int) -> None:
        line = f"NGUON / {source}  •  {date}".strip("  • ")[:90]
        font = fonts.bev(int(22 * scale))
        _center(draw, width / 2, height - bottom, line, font, muted)

    if mode == "duel_columns":
        metrics = [m for m in (data.get("metrics") or [])[:6] if isinstance(m, dict)]
        teams = data.get("teams") or ["DOI A", "DOI B"]

        def _tname(item: Any) -> str:
            return str(item.get("name") if isinstance(item, dict) else item)[:20]

        def _trec(item: Any) -> str:
            rec = item.get("record") if isinstance(item, dict) else ""
            return str(rec or "")[:12]

        head_h = int(300 * scale)
        draw.rectangle((0, 0, width, head_h), fill=ink)
        title = str(data.get("headline") or "SO SANH CHI SO")[:40]
        title_font = _fit_font(draw, title, fonts.barlow, int(120 * scale), width - 80)
        _center(draw, width / 2, int(36 * scale), title, title_font, paper)
        home_n, away_n = _tname(teams[0]), _tname(teams[1])
        home_r, away_r = _trec(teams[0]), _trec(teams[1])
        name_font = fonts.barlow(int(64 * scale))
        _center(draw, width / 4, int(170 * scale), home_n.upper(), name_font, paper)
        _center(draw, width * 3 / 4, int(170 * scale), away_n.upper(), name_font, paper)
        if home_r or away_r:
            rec_font = fonts.bev_b(int(30 * scale))
            _center(draw, width / 4, int(244 * scale), home_r, rec_font, muted)
            _center(draw, width * 3 / 4, int(244 * scale), away_r, rec_font, muted)
        draw.rectangle((0, head_h, width / 2, height), fill=navy)
        draw.rectangle((width / 2, head_h, width, height), fill=orange)
        for side, media_key in ((0, "home_media"), (1, "away_media")):
            try:
                photo = _photo_or("duel flank", data.get(media_key) or "", navy[:3])
                strip_w = int(width * 0.16)
                x = 0 if side == 0 else width - strip_w
                _torn_paste(image, photo, (x, head_h, x + strip_w, height),
                            edge="right" if side == 0 else "left")
            except LookupError:
                pass
        top = head_h + int(30 * scale)
        rows = max(1, len(metrics))
        row_h = (height - top - int(140 * scale)) // rows
        for index, item in enumerate(metrics):
            y = top + index * row_h
            label = str(item.get("label", "Chi so"))[:26]
            _center(draw, width / 2, y, label.upper(), fonts.barlow_sb(int(40 * scale)), paper)
            try:
                left_v = float(str(item.get("home", 0)).replace(",", "."))
                right_v = float(str(item.get("away", 0)).replace(",", "."))
            except (TypeError, ValueError):
                left_v = right_v = 0.0
            if left_v > right_v:
                left_fill, right_fill = lime, paper
            elif right_v > left_v:
                left_fill, right_fill = paper, lime
            else:
                left_fill = right_fill = paper
            num_font = fonts.barlow(int(min(150, row_h // 2) * scale))
            left_t, right_t = str(item.get("home", "-"))[:10], str(item.get("away", "-"))[:10]
            lw = draw.textbbox((0, 0), left_t, font=num_font)[2]
            rw = draw.textbbox((0, 0), right_t, font=num_font)[2]
            draw.text((width / 4 - lw / 2, y + int(52 * scale)), left_t, font=num_font, fill=left_fill)
            draw.text((width * 3 / 4 - rw / 2, y + int(52 * scale)), right_t, font=num_font, fill=right_fill)
            if index:
                draw.line((int(60 * scale), y, width - int(60 * scale), y), fill=paper[:3] + (70,), width=max(2, scale))
        credit(int(70 * scale))

    elif mode == "stat_leader":
        stats = [s for s in (data.get("stats") or [])[:4] if isinstance(s, dict)]
        draw.rectangle((0, 0, width, height), fill=red)
        ghost = str(data.get("ghost") or "%")[:2]
        ghost_font = fonts.barlow(int(900 * scale))
        gw = draw.textbbox((0, 0), ghost, font=ghost_font)[2]
        draw.text((width - gw - int(40 * scale), int(120 * scale)), ghost,
                  font=ghost_font, fill=dark_red)
        try:
            photo = _photo_or("leader cutout", data.get("media_file") or "", red[:3])
            _torn_paste(image, photo, (int(width * 0.52), 0, width, height), edge="left")
        except LookupError:
            pass
        name = str(data.get("player_name") or data.get("headline") or "CAU THU")[:30]
        area_top = int(110 * scale)
        area_bottom = height - int(560 * scale)
        rows = max(1, len(stats))
        slot = (area_bottom - area_top) // rows
        for index, item in enumerate(stats):
            label = str(item.get("label", ""))[:24]
            value = str(item.get("value", "--"))[:8]
            sy = area_top + index * slot
            draw.text((int(70 * scale), sy), label.upper(),
                      font=fonts.bev(int(34 * scale)), fill=paper)
            num_size = min(int(220 * scale), int(slot * 0.58))
            num_font = _fit_font(draw, value, fonts.barlow, num_size, int(width * 0.44))
            draw.text((int(64 * scale), sy + int(52 * scale)), value, font=num_font, fill=black)
        foot_font = fonts.barlow(int(110 * scale))
        _center(draw, width / 2, height - int(320 * scale), "STATS", foot_font, paper)
        pill = str(name.upper())
        pill_font = _fit_font(draw, pill, fonts.bev_b, int(44 * scale), width - int(200 * scale))
        pw = draw.textbbox((0, 0), pill, font=pill_font)[2]
        px, py = (width - pw) / 2 - int(30 * scale), height - int(200 * scale)
        draw.rounded_rectangle((px, py, px + pw + int(60 * scale), py + int(80 * scale)),
                               radius=int(10 * scale), fill=paper)
        draw.text((px + int(30 * scale), py + int(8 * scale)), pill, font=pill_font, fill=ink)
        credit(int(60 * scale))

    elif mode in {"player_poster_side", "player_poster_top"}:
        name = str(data.get("player_name") or "CAU THU")[:30]
        parts = name.split()
        first, surname = (" ".join(parts[:-1]), parts[-1]) if len(parts) > 1 else ("", parts[0] if parts else "")
        field = str(data.get("field") or "kit_red")
        field_fill = {"kit_red": red, "navy": navy, "orange": orange, "paper": paper}.get(field, red)
        on_field = ink if field in {"paper", "orange"} else paper
        on_field_micro = ink if field in {"paper", "orange"} else muted
        detail = str(data.get("player_detail") or data.get("tag") or "")[:30]
        stats = [s for s in (data.get("stats") or [])[:3] if isinstance(s, dict)]
        meta = [(str(m.get("label", ""))[:16], str(m.get("value", ""))[:30])
                for m in (data.get("meta") or [])[:3] if isinstance(m, dict)]
        has_photo = False
        try:
            photo = _photo_or("portrait", data.get("media_file") or "", field_fill[:3])
            has_photo = True
        except LookupError:
            photo = None
        draw.rectangle((0, 0, width, height), fill=field_fill)
        if mode == "player_poster_side":
            split = int(width * 0.46)
            if has_photo:
                _torn_paste(image, photo, (0, 0, split, height), edge="right")
            else:
                draw.rectangle((0, 0, split, height), fill=ink)
                _center(draw, split / 2, height / 2 - 40, "ANH\nDUYET",
                        fonts.barlow(int(90 * scale)), muted)
            _ticker(image, fonts, name, y=int(30 * scale), angle=-8,
                     band=paper[:3], ink_=ink[:3])
            brush_word = surname if len(surname) > 1 else name
            brush_size = int(300 * scale)
            while brush_size > 60:
                brush = fonts.brush(brush_size)
                bw = draw.textbbox((0, 0), brush_word.upper(), font=brush)[2]
                if bw <= width - int(260 * scale):
                    break
                brush_size -= 20
            brush_top = int(300 * scale)
            draw.text((width - bw - int(50 * scale), brush_top), brush_word.upper(),
                      font=brush, fill=black if field != "navy" else lime)
            brush_h = draw.textbbox((0, 0), brush_word.upper(), font=brush)[3]
            if first:
                draw.text((width - int(420 * scale), int(230 * scale)), first.upper(),
                          font=fonts.barlow_sb(int(64 * scale)), fill=on_field)
            if detail:
                tag_font = fonts.bev_b(int(40 * scale))
                tw = draw.textbbox((0, 0), detail, font=tag_font)[2]
                tx = width - tw - int(90 * scale)
                ty = brush_top + brush_h + int(30 * scale)
                draw.rounded_rectangle((tx - 20, ty, tx + tw + 20, ty + int(90 * scale)),
                                       radius=8, fill=paper)
                draw.text((tx, ty + int(8 * scale)), detail, font=tag_font, fill=ink)
            field_left = split + int(50 * scale)
            field_w = width - field_left - int(40 * scale)
            meta_w = int(field_w * 0.46)
            stat_x = field_left + meta_w + int(60 * scale)
            my = int(880 * scale)
            for label, value in meta:
                draw.text((field_left, my), label.upper(), font=fonts.barlow_sb(int(52 * scale)), fill=on_field)
                my += int(70 * scale)
                draw.text((field_left, my), value, font=fonts.bev_b(int(36 * scale)), fill=on_field)
                my += int(150 * scale)
            draw.line((stat_x - int(30 * scale), int(880 * scale),
                       stat_x - int(30 * scale), int(880 * scale) + max(100, my - int(880 * scale) - 60)),
                      fill=on_field, width=max(2, scale))
            stat_rows = max(1, len(stats))
            stat_slot = (height - int(880 * scale) - int(200 * scale)) // stat_rows
            draw.text((stat_x, int(880 * scale)), "STATS", font=fonts.barlow_sb(int(48 * scale)), fill=on_field)
            for index, item in enumerate(stats):
                value = str(item.get("value", "--"))[:8]
                label = str(item.get("label", ""))[:20]
                vy = int(880 * scale) + int(80 * scale) + index * stat_slot
                stat_font = _fit_font(draw, value, fonts.barlow, int(120 * scale), field_w - meta_w - int(120 * scale))
                draw.text((stat_x, vy), value, font=stat_font, fill=on_field)
                stat_h = draw.textbbox((0, 0), value, font=stat_font)[3]
                draw.text((stat_x, vy + stat_h + int(12 * scale)), label.upper(),
                          font=fonts.bev(int(28 * scale)), fill=on_field_micro)
        else:
            photo_h = int(height * 0.38)
            if has_photo:
                _torn_paste(image, photo, (0, 0, width, photo_h), edge="bottom")
            else:
                draw.rectangle((0, 0, width, photo_h), fill=ink)
            _ticker(image, fonts, name, y=int(24 * scale), angle=-6,
                     band=paper[:3], ink_=ink[:3])
            brush_word = surname if len(surname) > 1 else name
            brush = _fit_font(draw, brush_word.upper(), fonts.brush, int(280 * scale), width - int(80 * scale))
            bw = draw.textbbox((0, 0), brush_word.upper(), font=brush)[2]
            draw.text(((width - bw) / 2, photo_h + int(20 * scale)), brush_word.upper(),
                      font=brush, fill=black if field != "navy" else lime)
            if first:
                _center(draw, width / 2, photo_h + int(300 * scale), first.upper(),
                        fonts.barlow_sb(int(60 * scale)), on_field)
            cols_y = photo_h + int(460 * scale)
            for i, (label, value) in enumerate(meta):
                cx = width * (0.2 + 0.3 * i)
                _center(draw, cx, cols_y, label.upper(), fonts.barlow_sb(int(44 * scale)), on_field)
                _center(draw, cx, cols_y + int(64 * scale), value, fonts.bev_b(int(32 * scale)), on_field)
            rule_y = cols_y + int(190 * scale)
            draw.line((int(80 * scale), rule_y, width - int(80 * scale), rule_y), fill=lime if field == "navy" else on_field, width=max(3, scale * 2))
            _center(draw, width / 2, rule_y + int(30 * scale), "STATS", fonts.barlow_sb(int(52 * scale)), on_field)
            stat_y = rule_y + int(140 * scale)
            for i, item in enumerate(stats):
                cx = width * (0.2 + 0.3 * i)
                value = str(item.get("value", "--"))[:8]
                label = str(item.get("label", ""))[:20]
                _center(draw, cx, stat_y, value, fonts.barlow(int(170 * scale)), on_field)
                _center(draw, cx, stat_y + int(210 * scale), label.upper(), fonts.bev(int(30 * scale)), on_field_micro)
        credit(int(60 * scale))

    elif mode == "goal_card":
        draw.rectangle((0, 0, width, height), fill=red)
        word = str(data.get("backdrop") or "GOAL")[:8]
        ghost_font = fonts.barlow(int(560 * scale) if not is_long else int(420 * scale))
        lines = [word[i:i + 2] for i in range(0, len(word), 2)] or [word]
        gy = int(60 * scale)
        for chunk in lines:
            cw = draw.textbbox((0, 0), chunk, font=ghost_font)[2]
            draw.text(((width - cw) / 2, gy), chunk, font=ghost_font, fill=dark_red)
            bounds = draw.textbbox((0, 0), chunk, font=ghost_font)
            gy += (bounds[3] - bounds[1]) - int(60 * scale)
        _marquee(draw, fonts, width, int(30 * scale), "GOAL " * 6, paper[:3] + (200,))
        _marquee(draw, fonts, width, height - int(120 * scale), "GOAL " * 6, paper[:3] + (200,))
        chant = str(data.get("hook_text") or data.get("headline") or "VAO ROI")[:60]
        chant_font = _fit_font(draw, chant.upper(), fonts.barlow, int(150 * scale), width - int(120 * scale))
        chant_h = draw.textbbox((0, 0), chant.upper(), font=chant_font)[3]
        chant_y = gy - chant_h // 2 - int(40 * scale)
        _center(draw, width / 2, chant_y, chant.upper(), chant_font, paper)
        score = str(data.get("score") or "")[:14]
        if score:
            pill_font = fonts.barlow(int(90 * scale))
            pw = draw.textbbox((0, 0), score, font=pill_font)[2]
            px = (width - pw) / 2 - int(40 * scale)
            py = chant_y + chant_h + int(70 * scale)
            draw.rounded_rectangle((px, py, px + pw + int(80 * scale), py + int(140 * scale)),
                                   radius=int(12 * scale), fill=paper)
            draw.text((px + int(40 * scale), py + int(10 * scale)), score, font=pill_font, fill=ink)
        credit(int(60 * scale))

    elif mode == "fixture_card":
        draw.rectangle((0, 0, width, height), fill=red)
        _marquee(draw, fonts, width, int(30 * scale), "NEXT MATCH ", paper[:3] + (200,))
        _marquee(draw, fonts, width, height - int(120 * scale), "NEXT MATCH ", paper[:3] + (200,))
        _center(draw, width / 2, int(280 * scale), "NEXT", fonts.barlow(int(170 * scale)), paper)
        _center(draw, width / 2, int(280 * scale) + int(190 * scale), "MATCH", fonts.barlow(int(170 * scale)), paper)
        cy = height / 2 - int(40 * scale)
        _shield(draw, width / 2 - int(220 * scale), cy, int(150 * scale), paper, width=max(4, scale * 2))
        _shield(draw, width / 2 + int(220 * scale), cy, int(150 * scale), paper, width=max(4, scale * 2))
        _center(draw, width / 2, cy - int(60 * scale), "V", fonts.barlow(int(110 * scale)), paper)
        home = str(data.get("home") or "DOI NHA")[:24]
        away = str(data.get("away") or "DOI KHACH")[:24]
        _center(draw, width / 2, cy + int(180 * scale), f"{home.upper()}  •  {away.upper()}",
                fonts.bev_b(int(40 * scale)), paper)
        when = str(data.get("date") or data.get("when") or "")[:50]
        venue = str(data.get("venue") or data.get("stadium") or "")[:50]
        _center(draw, width / 2, cy + int(280 * scale), when, fonts.bev(int(38 * scale)), paper)
        _center(draw, width / 2, cy + int(350 * scale), venue.upper(), fonts.bev(int(34 * scale)), paper)
        credit(int(160 * scale))

    elif mode == "fixture_list":
        draw.rectangle((0, 0, width, height), fill=red)
        _center(draw, width / 2, int(200 * scale), "UP", fonts.barlow(int(200 * scale)), black)
        _center(draw, width / 2, int(200 * scale) + int(220 * scale), "NEXT >>", fonts.barlow(int(150 * scale)), black)
        fixtures = [f for f in (data.get("fixtures") or [])[:3] if isinstance(f, dict)]
        panel_y = int(760 * scale)
        draw.rounded_rectangle((int(80 * scale), panel_y, width - int(80 * scale), height - int(160 * scale)),
                               radius=int(16 * scale), fill=paper)
        row_y = panel_y + int(60 * scale)
        for item in fixtures:
            _shield(draw, int(220 * scale), row_y + int(70 * scale), int(90 * scale), red, width=max(3, scale))
            _shield(draw, width - int(220 * scale), row_y + int(70 * scale), int(90 * scale), ink, width=max(3, scale))
            when = str(item.get("date") or item.get("when") or "")[:30]
            _center(draw, width / 2, row_y, when.upper(), fonts.bev_b(int(40 * scale)), ink)
            opp = str(item.get("away") or item.get("home") or "")[:26]
            _center(draw, width / 2, row_y + int(70 * scale), opp.upper(), fonts.bev(int(32 * scale)), ink)
            row_y += int(280 * scale)
            if row_y < height - int(260 * scale):
                draw.line((int(140 * scale), row_y - int(40 * scale), width - int(140 * scale), row_y - int(40 * scale)),
                          fill=muted[:3] + (160,), width=max(2, scale))
        credit(int(60 * scale))

    elif mode == "score_card":
        try:
            photo = _photo_or("action", data.get("media_file") or "", ink[:3])
            from PIL import ImageOps as _Ops

            fitted = _Ops.fit(photo.convert("RGB"), (width, height)).convert("RGBA")
            image.alpha_composite(fitted)
            shade = _Image.new("RGBA", (width, height), (0, 0, 0, 0))
            _shade = _Draw.Draw(shade)
            _shade.rectangle((0, 0, width, height), fill=(5, 8, 10, 150))
            image.alpha_composite(shade)
            draw = _Draw.Draw(image, "RGBA")
        except LookupError:
            draw.rectangle((0, 0, width, height), fill=ink)
        home = str(data.get("home") or "DOI NHA")[:16]
        away = str(data.get("away") or "DOI KHACH")[:16]
        score = str(data.get("score") or "1 - 0")[:10]
        bug_y = int(120 * scale)
        _shield(draw, width / 2 - int(330 * scale), bug_y, int(90 * scale), red, width=max(3, scale))
        _shield(draw, width / 2 + int(330 * scale), bug_y, int(90 * scale), paper, width=max(3, scale))
        _center(draw, width / 2, bug_y - int(70 * scale), score, fonts.barlow(int(120 * scale)), paper)
        _center(draw, width / 2, height / 2 + int(120 * scale), "FULL", fonts.barlow(int(230 * scale)), paper)
        _center(draw, width / 2, height / 2 + int(120 * scale) + int(250 * scale), "TIME", fonts.barlow(int(230 * scale)), paper)
        _center(draw, width / 2, height - int(420 * scale), f"{home.upper()}  •  {away.upper()}",
                fonts.bev_b(int(40 * scale)), paper)
        credit(int(140 * scale))

    elif mode == "quote_card":
        try:
            photo = _photo_or("quote bg", data.get("media_file") or "", red[:3])
            from PIL import ImageOps as _Ops, ImageEnhance as _Enh

            fitted = _Ops.fit(photo.convert("RGB"), (width, height)).convert("RGBA")
            duotone = _Enh.Color(fitted).enhance(0.15)
            red_layer = _Image.new("RGBA", (width, height), red)
            image.alpha_composite(_Image.blend(fitted, red_layer, 0.55))
            draw = _Draw.Draw(image, "RGBA")
        except LookupError:
            draw.rectangle((0, 0, width, height), fill=red)
        box_y = height / 2 - int(100 * scale)
        draw.rounded_rectangle((int(90 * scale), box_y, width - int(90 * scale), box_y + int(640 * scale)),
                               radius=int(14 * scale), fill=paper)
        draw.text((int(130 * scale), box_y - int(40 * scale)), "\u201c", font=fonts.barlow(int(200 * scale)), fill=red)
        quote = str(data.get("claim") or data.get("quote") or "")[:220]
        qy = box_y + int(90 * scale)
        for line in _wrap(quote, 30 if not is_long else 60)[:5]:
            draw.text((int(140 * scale), qy), line, font=fonts.bev(int(40 * scale)), fill=ink)
            qy += int(72 * scale)
        who = str(data.get("player_name") or data.get("source") or "")[:40]
        draw.text((int(140 * scale), box_y + int(530 * scale)), who.upper(), font=fonts.bev_b(int(34 * scale)), fill=ink)
        seal_cx, seal_cy, seal_r = width - int(220 * scale), box_y + int(560 * scale), int(70 * scale)
        draw.ellipse((seal_cx - seal_r, seal_cy - seal_r, seal_cx + seal_r, seal_cy + seal_r), fill=red)
        _center(draw, seal_cx, seal_cy - int(40 * scale), "AKB", fonts.barlow(int(52 * scale)), paper)
        credit(int(60 * scale))

    elif mode == "potm_card":
        try:
            photo = _photo_or("potm", data.get("media_file") or "", ink[:3])
            from PIL import ImageOps as _Ops

            fitted = _Ops.fit(photo.convert("RGB"), (width, height)).convert("RGBA")
            image.alpha_composite(fitted)
            shade = _Image.new("RGBA", (width, height), (0, 0, 0, 0))
            _Draw.Draw(shade).rectangle((0, 0, width, height), fill=(5, 5, 8, 170))
            image.alpha_composite(shade)
            draw = _Draw.Draw(image, "RGBA")
        except LookupError:
            draw.rectangle((0, 0, width, height), fill=ink)
        _center(draw, width / 2, height / 2 - int(120 * scale), "POTM", fonts.barlow(int(420 * scale)), red)
        who = str(data.get("player_name") or "CAU THU")[:30]
        pill_font = _fit_font(draw, who.upper(), fonts.bev_b, int(52 * scale), width - int(240 * scale))
        pw = draw.textbbox((0, 0), who.upper(), font=pill_font)[2]
        px = (width - pw) / 2 - int(40 * scale)
        py = height / 2 + int(220 * scale)
        draw.rounded_rectangle((px, py, px + pw + int(80 * scale), py + int(110 * scale)),
                               radius=int(10 * scale), fill=red)
        draw.text((px + int(40 * scale), py + int(14 * scale)), who.upper(), font=pill_font, fill=paper)
        credit(int(140 * scale))

    elif mode == "discipline_card":
        draw.rectangle((0, 0, width, height), fill=red)
        edge_font = fonts.barlow(int(300 * scale))
        draw.text((int(10 * scale), int(120 * scale)), "R", font=edge_font, fill=paper)
        draw.text((int(10 * scale), height - int(520 * scale)), "D", font=edge_font, fill=paper)
        _center(draw, width / 2, int(300 * scale), "RED CARD", fonts.barlow(int(130 * scale)), paper)
        cards = data.get("cards") if isinstance(data.get("cards"), list) else [1]
        cy = int(620 * scale)
        for _ in cards[:3]:
            draw.rounded_rectangle((width / 2 - int(130 * scale), cy, width / 2 + int(130 * scale), cy + int(200 * scale)),
                                   radius=int(10 * scale), fill=paper)
            draw.rounded_rectangle((width / 2 - int(110 * scale), cy + int(20 * scale),
                                    width / 2 + int(110 * scale), cy + int(180 * scale)),
                                   radius=int(8 * scale), fill=red)
            cy += int(260 * scale)
        who = str(data.get("player_name") or "")[:30]
        minute = str(data.get("minute") or "")[:10]
        foot = f"{who.upper()}  {minute}".strip()[:44]
        _center(draw, width / 2, height - int(340 * scale), foot, fonts.bev_b(int(44 * scale)), paper)
        credit(int(160 * scale))

    elif mode == "welcome_card":
        draw.rectangle((0, 0, width, height), fill=red)
        draw.line((0, 0, width, height), fill=dark_red, width=max(6, scale * 4))
        draw.line((width, 0, 0, height), fill=dark_red, width=max(6, scale * 4))
        _center(draw, width / 2, int(220 * scale), "WELCOME", fonts.barlow(int(150 * scale)), paper)
        try:
            photo = _photo_or("welcome", data.get("media_file") or "", red[:3])
            from PIL import ImageOps as _Ops

            side = int(width * 0.7)
            fitted = _Ops.fit(photo.convert("RGB"), (side, side)).convert("RGBA")
            image.alpha_composite(fitted, (int((width - side) / 2), int(height * 0.3)))
            draw = _Draw.Draw(image, "RGBA")
        except LookupError:
            pass
        who = str(data.get("player_name") or "CAU THU MOI")[:30]
        pill_font = _fit_font(draw, who.upper(), fonts.bev_b, int(52 * scale), width - int(240 * scale))
        pw = draw.textbbox((0, 0), who.upper(), font=pill_font)[2]
        px = (width - pw) / 2 - int(40 * scale)
        py = height - int(420 * scale)
        draw.rectangle((px, py, px + pw + int(80 * scale), py + int(110 * scale)), fill=black)
        draw.text((px + int(40 * scale), py + int(14 * scale)), who.upper(), font=pill_font, fill=paper)
        _marquee(draw, fonts, width, height - int(120 * scale), "WELCOME ", paper[:3] + (200,))
        credit(int(60 * scale))

    else:
        raise ValueError(f"Unknown kit mode: {mode}")

    _grain(image)
    _vignette(image)
    return image.resize((panel_w, panel_h), _Image.Resampling.LANCZOS)
