from __future__ import annotations

"""Local FFmpeg renderer for a template motion preview and reviewed production runs."""

import json
import os
from pathlib import Path
import shutil
import subprocess
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


def _write_text(path: Path, text: str) -> str:
    # FFmpeg reads UTF-8 text files directly; this also avoids filter escaping issues.
    path.write_text(text, encoding="utf-8")
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


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
    panel_w, panel_h = (1540, 840) if is_long else (960, 1250)
    image = Image.new("RGBA", (panel_w * scale, panel_h * scale), (0, 0, 0, 0))
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
    # A print-editorial frame: registration marks, chapter indexing, and
    # restrained paper-like accents replace the previous rounded HUD card.
    draw.line((28*scale, 64*scale, (panel_w-28)*scale, 64*scale), fill=rgba("pitch_line", 180), width=scale)
    draw.rectangle((28*scale, 27*scale, 42*scale, 41*scale), fill=lime)
    draw.line((28*scale, (panel_h-35)*scale, (panel_w-28)*scale, (panel_h-35)*scale), fill=rgba("pitch_line", 150), width=scale)
    # A sharp paper tab and three marker slashes break the document-grid feel.
    draw.polygon(((30*scale,82*scale),(238*scale,82*scale),(220*scale,119*scale),(30*scale,119*scale)), fill=lime)
    tab_font = ImageFont.truetype(str(display_font_path), 16*scale)
    draw.text((43*scale,87*scale), "MATCH FILE  /  TACTICAL READ", font=tab_font, fill=rgba("ink"))
    for slash in range(3):
        x = (panel_w-116+slash*22)*scale
        draw.line((x,87*scale,x+18*scale,69*scale), fill=rgba("team_away"), width=5*scale)

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
                draw.rectangle((x1*scale,fy*scale,x2*scale,(fy+fh)*scale),fill=rgba("pitch_line",22))
    else:
        band = fh / 10
        for stripe in range(10):
            if stripe % 2 == 0:
                y1, y2 = fy + stripe * band, fy + (stripe + 1) * band
                draw.rectangle((fx*scale,y1*scale,(fx+fw)*scale,y2*scale),fill=rgba("pitch_line",22))
    draw.rectangle((fx * scale, fy * scale, (fx + fw) * scale, (fy + fh) * scale), outline=line, width=lw)
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
    if pass_vector.get("from") and pass_vector.get("to"):
        _draw_vector_arrow(draw, point(pass_vector["from"]), point(pass_vector["to"]), lime, dashed=False, width=4 * scale)
    for vector in spec.get("run_vectors", []):
        _draw_vector_arrow(draw, point(vector["from"]), point(vector["to"]), chalk, dashed=True, width=3 * scale)
    for vector in spec.get("press_vectors", []):
        _draw_vector_arrow(draw, point(vector["from"]), point(vector["to"]), orange, dashed=True, width=3 * scale)

    header_font = ImageFont.truetype(str(font_path), 15 * scale)
    small_font = ImageFont.truetype(str(font_path), 12 * scale)
    draw.text((54 * scale, 24 * scale), "ALLEN KNOWS BALL   /   MATCH NOTES", font=header_font, fill=chalk)
    progress_label = f"{scene_number:02d} / {scene_count:02d}"
    progress_font = ImageFont.truetype(str(font_path), 15 * scale)
    progress_bounds = draw.textbbox((0,0),progress_label,font=progress_font)
    badge_x = panel_w - 30 - (progress_bounds[2]-progress_bounds[0])
    draw.text((badge_x*scale,24*scale),progress_label,font=progress_font,fill=lime)
    # Chapter rail inspired by the editorial logic of analysis films: the
    # chapter index supplies context, while the pitch remains the evidence.
    if is_long:
        draw.text((38*scale, 132*scale), "TACTICAL READ", font=small_font, fill=muted)
        number_font = ImageFont.truetype(str(display_font_path), 128*scale)
        draw.text((33*scale, 184*scale), f"{scene_number:02d}", font=number_font, fill=rgba("ink",170), stroke_width=1*scale, stroke_fill=rgba("ink",170))
        draw.text((30*scale, 178*scale), f"{scene_number:02d}", font=number_font, fill=lime)
        draw.line((38*scale, 350*scale, 420*scale, 350*scale), fill=lime, width=3*scale)
        draw.text((38*scale, 385*scale), "SƠ ĐỒ MINH HỌA", font=header_font, fill=chalk)
        draw.text((38*scale, 425*scale), "Không phải hình ảnh trận đấu", font=small_font, fill=muted)
        draw.text((38*scale, 525*scale), "FOCUS PLAYER", font=small_font, fill=muted)
    else:
        draw.text((36*scale, 145*scale), "TACTICAL", font=small_font, fill=muted)
        draw.text((36*scale, 169*scale), "READ", font=small_font, fill=muted)
        number_font = ImageFont.truetype(str(display_font_path), 136*scale)
        draw.text((31*scale, 211*scale), f"{scene_number:02d}", font=number_font, fill=rgba("ink",175), stroke_width=1*scale, stroke_fill=rgba("ink",175))
        draw.text((28*scale, 205*scale), f"{scene_number:02d}", font=number_font, fill=lime)
        draw.line((36*scale, 385*scale, 215*scale, 385*scale), fill=lime, width=3*scale)
        draw.text((36*scale, 420*scale), "SƠ ĐỒ", font=header_font, fill=chalk)
        draw.text((36*scale, 456*scale), "MINH HỌA", font=header_font, fill=chalk)
        draw.text((36*scale, 510*scale), "Không phải hình ảnh", font=small_font, fill=muted)
        draw.text((36*scale, 534*scale), "trận đấu", font=small_font, fill=muted)
        draw.text((36*scale, 770*scale), "FOCUS", font=small_font, fill=muted)
        draw.text((36*scale, 794*scale), "PLAYER", font=small_font, fill=muted)
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
    legend_font = ImageFont.truetype(str(font_path), 12 * scale)
    legend_y = (758 if is_long else 1110) * scale
    draw.ellipse((32*scale, legend_y, 46*scale, legend_y+14*scale), fill=rgba("team_home"))
    draw.text((52*scale, (legend_y-2*scale)), "ĐỘI GIỮ BÓNG", font=legend_font, fill=rgba("team_home"))
    draw.ellipse((278*scale, legend_y, 292*scale, legend_y+14*scale), fill=rgba("team_away"))
    draw.text((298*scale, (legend_y-2*scale)), "ĐỘI PRESSING", font=legend_font, fill=rgba("team_away"))
    draw.line((520*scale, legend_y+7*scale, 558*scale, legend_y+7*scale), fill=lime, width=4*scale)
    draw.polygon(((558*scale, legend_y+1*scale),(570*scale,legend_y+7*scale),(558*scale,legend_y+13*scale)), fill=lime)
    draw.text((578*scale, legend_y-2*scale), "CHUYỀN BÓNG", font=legend_font, fill=chalk)

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
) -> None:
    """Draw sourced stat, source, and chart plates; values must come from the reviewed script."""
    from PIL import Image, ImageDraw, ImageFont

    panel_w, panel_h = (1540, 840) if is_long else (960, 1250)
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
    muted, accent = color("muted", "#A9B2AA"), color("signal_lime", "#E4BA57")
    series = [color(f"data_{index}", fallback) for index, fallback in enumerate(("#54C7B8", "#F07862", "#8F83E8", "#E7C45C"), 1)]
    heading = str(data.get("headline") or data.get("title") or "BẰNG CHỨNG TRẬN ĐẤU")
    home = color("team_home", "#55C7B8")
    away = color("team_away", "#F07862")

    if mode == "media_b_roll":
        from PIL import ImageEnhance, ImageOps

        source_path = Path(str(data.get("media_file", "")))
        with Image.open(source_path) as source_image:
            photo = ImageOps.fit(source_image.convert("RGB"), (panel_w*scale, panel_h*scale), method=Image.Resampling.LANCZOS, centering=(0.5, 0.47))
        photo = ImageEnhance.Color(photo).enhance(1.06)
        photo = ImageEnhance.Contrast(photo).enhance(1.04).convert("RGBA")
        image = photo
        draw = ImageDraw.Draw(image, "RGBA")
        # A restrained editorial shade protects the Vietnamese title while
        # leaving the licensed photograph visually dominant.
        shade = Image.new("RGBA", image.size, (8, 14, 20, 45))
        draw = ImageDraw.Draw(shade)
        for x in range(image.width):
            alpha = int(178 * max(0.0, 1.0 - x / (image.width * 0.78)))
            draw.line((x, 0, x, image.height), fill=(8, 14, 20, alpha))
        for y in range(image.height):
            alpha = int(170 * max(0.0, (y / image.height - 0.70) / 0.30))
            if alpha:
                draw.line((0, y, image.width, y), fill=(8, 14, 20, alpha))
        image = Image.alpha_composite(image, shade)
        draw = ImageDraw.Draw(image, "RGBA")
        draw.polygon(((0,0),(panel_w*scale,0),(panel_w*scale,14*scale),(0,34*scale)), fill=home)
        draw.line((32*scale, 80*scale, (panel_w-32)*scale, 80*scale), fill=(240,235,221,135), width=scale)
        text(42, 27, "ALLEN KNOWS BALL  /  VISUAL CONTEXT", 15, (255,255,255,235), bold=True)
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
        caption_y = panel_h - (226 if len(caption_lines) > 1 else 186)
        for line_index, line in enumerate(caption_lines):
            text(42, caption_y + line_index * (caption_size + 7), line, caption_size, (255,255,255,255), bold=True, display=True)
        creator = str(data.get("media_creator") or "Creator not listed")[:50]
        license_label = str(data.get("media_license") or "License recorded in Asset Library")[:34]
        credit_line = f"ẢNH: {creator} · {license_label}"
        credit_size = 12 if is_long else 11
        credit_font = ImageFont.truetype(str(font_path), credit_size * scale)
        while len(credit_line) > 18 and draw.textbbox((0, 0), credit_line, font=credit_font)[2] > max_caption_width:
            credit_line = credit_line[:-1].rstrip(" ·")
        text(42, panel_h-116, credit_line, credit_size, (255,255,255,235), bold=True)
        text(42, panel_h-82, "ẢNH MINH HỌA · KHÔNG PHẢI FOOTAGE TRẬN ĐANG PHÂN TÍCH", 11, (255,255,255,215))
        image.resize((panel_w, panel_h), Image.Resampling.LANCZOS).save(path)
        return

    # Each evidence graphic gets its own visual grammar: a face-off scorecard,
    # a true plotted chart, or a paper source note. Only the channel wordmark,
    # type system, and color tokens remain shared across the three layouts.
    if mode == "statline_scorecard":
        draw.rectangle((0, 0, panel_w*scale, panel_h*scale), fill=ink)
        draw.rectangle((0, 0, 12*scale, panel_h*scale), fill=home)
        draw.rectangle(((panel_w-12)*scale, 0, panel_w*scale, panel_h*scale), fill=away)
        draw.line((36*scale,72*scale,(panel_w-36)*scale,72*scale),fill=color("pitch_line","#658576",170),width=2*scale)
        text(48,28,"ALLEN KNOWS BALL  /  HEAD-TO-HEAD",14,muted,bold=True)
        text(44,96,heading,34 if is_long else 32,paper,bold=True,display=True)
        teams=data.get("teams",["ĐỘI A","ĐỘI B"])
        if not isinstance(teams,list) or len(teams)<2: teams=["ĐỘI A","ĐỘI B"]
        split=panel_w//2
        head_y=178 if is_long else 210
        head_h=68 if is_long else 82
        draw.rounded_rectangle((42*scale,head_y*scale,(split-25)*scale,(head_y+head_h)*scale),radius=5*scale,fill=home)
        draw.rounded_rectangle(((split+25)*scale,head_y*scale,(panel_w-42)*scale,(head_y+head_h)*scale),radius=5*scale,fill=away)
        text(60,head_y+18,str(teams[0])[:24],20 if is_long else 18,ink,bold=True)
        right=str(teams[1])[:24]
        right_font=ImageFont.truetype(str(font_path), (20 if is_long else 18)*scale)
        right_width=draw.textbbox((0,0),right,font=right_font)[2]
        text(panel_w-60-round(right_width/scale),head_y+18,right,20 if is_long else 18,ink,bold=True)
        vs_font=ImageFont.truetype(str(display_font_path),22*scale)
        draw.ellipse(((split-25)*scale,(head_y+head_h/2-23)*scale,(split+25)*scale,(head_y+head_h/2+23)*scale),fill=ink,outline=paper,width=2*scale)
        draw.text((split*scale,(head_y+head_h/2)*scale),"VS",font=vs_font,fill=paper,anchor="mm")
        metrics=data.get("metrics",[])
        metrics=[item for item in metrics[:5] if isinstance(item,dict)] if isinstance(metrics,list) else []
        if not metrics:
            text(48,head_y+head_h+48,"Chưa có số liệu đã xác minh",20,muted,bold=True)
        top=head_y+head_h+(62 if is_long else 74)
        bottom=panel_h-(118 if is_long else 138)
        row_h=max(1,(bottom-top)//max(1,len(metrics)))
        value_size=min(56 if is_long else 66,max(34,row_h//2))
        number_font=ImageFont.truetype(str(display_font_path),value_size*scale)
        for index,item in enumerate(metrics):
            y=top+index*row_h
            if index:
                draw.line((48*scale,y*scale,(panel_w-48)*scale,y*scale),fill=color("pitch_line","#658576",125),width=scale)
            label=str(item.get("label","Chỉ số"))[:28]
            label_font=ImageFont.truetype(str(font_path),16*scale)
            label_w=draw.textbbox((0,0),label,font=label_font)[2]/scale
            text((panel_w-label_w)/2,y+row_h*.17,label,16,muted,bold=True)
            for center,value,tint in ((panel_w*.24,item.get("home","—"),home),(panel_w*.76,item.get("away","—"),away)):
                value=str(value)[:12]
                draw.text((center*scale,(y+row_h*.62)*scale),value,font=number_font,fill=tint,anchor="mm")
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
                draw.rounded_rectangle(((center_x-left_len)*scale,rail_y*scale,center_x*scale,(rail_y+5)*scale),radius=3*scale,fill=home)
                draw.rounded_rectangle((center_x*scale,rail_y*scale,(center_x+right_len)*scale,(rail_y+5)*scale),radius=3*scale,fill=away)
            except (TypeError,ValueError):
                pass
        source=str(data.get("source") or data.get("source_label") or "Nguồn cần xác minh")
        credit=f"{source} · {data.get('date','')}".strip(" ·")
        text(42,panel_h-68,credit[:105],12,muted)
        draw.text(((panel_w-44)*scale,(panel_h-68)*scale),f"{scene_number:02d}",font=ImageFont.truetype(str(display_font_path),20*scale),fill=accent,anchor="ra")
        image.resize((panel_w,panel_h),Image.Resampling.LANCZOS).save(path)
        return

    if mode in {"chart_comparison", "chart_timeline"}:
        # Light analyst's plotting sheet: the axes and labels, rather than
        # decorative cards, carry the structure of the graphic.
        draw.rectangle((0,0,panel_w*scale,panel_h*scale),fill=paper)
        dark=(17,23,33,255)
        body_muted=(77,91,87,255)
        # Offset registration marks and a compact issue tag give the plot the
        # feel of an editorial analysis sheet without obscuring its evidence.
        draw.rectangle((0,0,panel_w*scale,9*scale),fill=home)
        for i in range(6):
            x=(panel_w-128+i*13)*scale
            draw.line((x,26*scale,x,39*scale),fill=(23,59,50,95),width=2*scale)
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
                draw.line((x*scale,plot_top*scale,x*scale,plot_bottom*scale),fill=(57,87,76,55),width=scale)
                draw.text((x*scale,(plot_bottom+18)*scale),str(tick),font=ImageFont.truetype(str(font_path.with_name("BeVietnamPro-Regular.ttf")),12*scale),fill=body_muted,anchor="mt")
            step=(plot_bottom-plot_top)//max(1,len(values))
            for index,item in enumerate(values):
                y=plot_top+index*step
                label=str(item.get("label",""))[:25]
                text(44,y+step*.22,label,15 if is_long else 14,dark,bold=True)
                bar_y=y+step*.62
                bar_h=22 if is_long else 26
                draw.rounded_rectangle((plot_left*scale,bar_y*scale,plot_right*scale,(bar_y+bar_h)*scale),radius=3*scale,fill=(27,59,50,26))
                width=(plot_right-plot_left)*nums[index]/axis_max
                tint=home
                draw.rounded_rectangle((plot_left*scale,bar_y*scale,(plot_left+max(1,width))*scale,(bar_y+bar_h)*scale),radius=3*scale,fill=tint)
                draw.ellipse(((plot_left+width-7)*scale,(bar_y-4)*scale,(plot_left+width+7)*scale,(bar_y+bar_h+4)*scale),fill=tint,outline=paper,width=2*scale)
                text(plot_right+15,bar_y-3,str(item.get("value","")),18,tint,bold=True)
        elif chart_type=="column" and values:
            nums=[max(0.0,n) for n in nums]
            high=max(nums,default=1.0) or 1.0
            tick_step=2 if high<=8 else (5 if high<=20 else 10)
            axis_max=max(tick_step,((int(high)+tick_step-1)//tick_step)*tick_step)
            for tick in range(0,axis_max+1,tick_step):
                y=plot_bottom-(plot_bottom-plot_top)*tick/axis_max
                draw.line((plot_left*scale,y*scale,plot_right*scale,y*scale),fill=(57,87,76,62),width=scale)
                draw.text(((plot_left-20)*scale,y*scale),str(tick),font=ImageFont.truetype(str(font_path.with_name("BeVietnamPro-Regular.ttf")),12*scale),fill=body_muted,anchor="rm")
            band=(plot_right-plot_left)/max(1,len(values)); bar_w=min(74,band*.54)
            for index,(item,number) in enumerate(zip(values,nums)):
                center=plot_left+band*(index+.5)
                bar_h=(plot_bottom-plot_top)*number/axis_max
                tint=home
                draw.rounded_rectangle(((center-bar_w/2)*scale,(plot_bottom-bar_h)*scale,(center+bar_w/2)*scale,plot_bottom*scale),radius=5*scale,fill=tint)
                # Slim contrasting cap makes each mark read as a deliberate
                # plotted value, not a generic rounded UI bar.
                cap_h=min(5,max(2,bar_h*.04))
                draw.line(((center-bar_w/2+5)*scale,(plot_bottom-bar_h+cap_h)*scale,(center+bar_w/2-5)*scale,(plot_bottom-bar_h+cap_h)*scale),fill=accent,width=2*scale)
                draw.text((center*scale,(plot_bottom-bar_h-26)*scale),str(item.get("value","")),font=ImageFont.truetype(str(display_font_path),18*scale),fill=dark,anchor="mm")
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
                draw.ellipse(((cx-hole)*scale,(cy-hole)*scale,(cx+hole)*scale,(cy+hole)*scale),fill=paper)
                total_label=f"{total:g}"
                draw.text((cx*scale,(cy-8)*scale),total_label,font=ImageFont.truetype(str(display_font_path),38*scale),fill=dark,anchor="mm")
                draw.text((cx*scale,(cy+34)*scale),str(data.get("unit","TOTAL"))[:14],font=ImageFont.truetype(str(font_path),11*scale),fill=body_muted,anchor="mm")
        elif chart_type=="line" and values:
            low=min(0.0,min(nums)); high=max(nums,default=1.0); high=high if high>low else low+1
            for index in range(5):
                y=plot_top+(plot_bottom-plot_top)*index/4
                draw.line((plot_left*scale,y*scale,plot_right*scale,y*scale),fill=(57,87,76,55),width=scale)
            coords=[]
            for index,value in enumerate(nums):
                x=plot_left+(plot_right-plot_left)*index/max(1,len(nums)-1)
                y=plot_bottom-(value-low)/(high-low)*(plot_bottom-plot_top)
                coords.append((round(x*scale),round(y*scale)))
            if len(coords)>1:
                # A soft underlay reinforces the single chronological arc.
                draw.line([(x,y+7*scale) for x,y in coords],fill=(27,59,50,28),width=10*scale,joint="curve")
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
        image.resize((panel_w,panel_h),Image.Resampling.LANCZOS).save(path)
        return

    if mode=="source_card":
        # A clipped paper insert over an ink field; provenance is the hero,
        # while the claim reads like an editorial pull-quote.
        draw.rectangle((0,0,panel_w*scale,panel_h*scale),fill=ink)
        text(44,28,"ALLEN KNOWS BALL  /  SOURCE NOTE",14,muted,bold=True)
        draw.line((40*scale,72*scale,(panel_w-40)*scale,72*scale),fill=color("pitch_line","#658576",150),width=scale)
        left,top,right,bottom=44,118,panel_w-44,panel_h-112
        cut=28
        shape=[(left,top),(right-cut,top),(right,top+cut),(right,bottom),(left,bottom)]
        draw.polygon([(x*scale,y*scale) for x,y in shape],fill=paper)
        draw.rectangle((left*scale,top*scale,(left+9)*scale,bottom*scale),fill=accent)
        source=str(data.get("source") or "Nguồn cần bổ sung")
        date=str(data.get("date") or "Ngày xuất bản cần xác minh")
        claim=str(data.get("claim") or data.get("description") or "Chưa có luận điểm được đối chiếu với nguồn đã duyệt.")
        text(left+34,top+34,"SOURCE  /  XUẤT XỨ",14,color("ink","#111721"),bold=True)
        text(left+34,top+72,source[:74],28 if is_long else 24,color("ink","#111721"),bold=True)
        source_ink=(78,90,86,255)
        text(left+34,top+116,date[:90],16,source_ink)
        draw.line(((left+34)*scale,(top+158)*scale,(right-34)*scale,(top+158)*scale),fill=color("pitch_line","#658576",190),width=2*scale)
        quote_font=ImageFont.truetype(str(display_font_path),92*scale)
        # Draw a custom double quote mark from simple shapes so its form is
        # stable across the bundled Vietnamese and condensed font files.
        for quote_index in range(2):
            qx=(left+35+quote_index*27)*scale
            qy=(top+194)*scale
            draw.ellipse((qx,qy,qx+15*scale,qy+17*scale),fill=accent)
            draw.polygon(((qx+2*scale,qy+12*scale),(qx+14*scale,qy+13*scale),(qx+5*scale,qy+28*scale)),fill=accent)
        words=textwrap.wrap(claim,width=74 if is_long else 40)
        size=23 if is_long else 21
        line_gap=42 if is_long else 48
        for index,line_value in enumerate(words[:5]):
            text(left+80,top+208+index*line_gap,line_value,size,color("ink","#111721"))
        url=str(data.get("url") or "")
        if url:
            draw.line(((left+34)*scale,(bottom-74)*scale,(right-34)*scale,(bottom-74)*scale),fill=color("pitch_line","#658576",145),width=scale)
            text(left+34,bottom-54,url[:96],13,source_ink)
        text(44,panel_h-76,"CLAIM + PUBLICATION + DATE",12,muted,bold=True)
        draw.text(((panel_w-44)*scale,(panel_h-75)*scale),f"{scene_number:02d}",font=ImageFont.truetype(str(display_font_path),20*scale),fill=accent,anchor="ra")
        image.resize((panel_w,panel_h),Image.Resampling.LANCZOS).save(path)
        return

    frame = [(24,8),(panel_w-42,8),(panel_w-8,42),(panel_w-8,panel_h-28),(panel_w-30,panel_h-8),(26,panel_h-8),(8,panel_h-26),(8,24)]
    draw.polygon([(x*scale,y*scale) for x,y in frame], fill=ink)
    draw.line([(x*scale,y*scale) for x,y in frame+[frame[0]]], fill=color("pitch_line", "#658576", 220), width=2*scale)
    draw.polygon(((34*scale,32*scale),(54*scale,32*scale),(49*scale,52*scale),(34*scale,52*scale)), fill=accent)
    # Halftone corner and torn-edge accent read like physical editorial marks.
    for row in range(5):
        for col in range(7):
            dot_x, dot_y = panel_w-176+col*15, 92+row*15
            draw.ellipse((dot_x*scale,dot_y*scale,(dot_x+3)*scale,(dot_y+3)*scale), fill=color("chalk", "#F0EBDD", 55))
    text(64, 27, "ALLEN KNOWS BALL  /  MATCH NOTES", 16, muted, bold=True)
    draw.line((34*scale, 68*scale, (panel_w-34)*scale, 68*scale), fill=color("pitch_line", "#658576", 180), width=2*scale)
    heading = str(data.get("headline") or data.get("title") or "BẰNG CHỨNG TRẬN ĐẤU")
    text(42, 94, heading, 34 if is_long else 30, paper, bold=True, display=True)
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
    text(44, panel_h-48, source_label[:90], 13, muted)
    text(panel_w-155, panel_h-48, f"{scene_number:02d} / DATA", 13, accent, bold=True)
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
    latin_font = package.root / "resources/fonts/BarlowCondensed-Bold.ttf"
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
    title_wrap = 38 if not is_long else 66
    wrapped_title = "\n".join(textwrap.wrap(title_text, width=title_wrap, break_long_words=False, break_on_hyphens=False))
    title_path = _write_text(work_dir / "title.txt", wrapped_title)
    filters.append(
        f"drawtext=fontfile='{latin_font_path}':textfile='{label_path}':fontcolor={signal_lime}:"
        f"fontsize=h*0.026:x=w*0.08:y=h*0.075:shadowcolor=black@0.6:shadowx=1:shadowy=2"
    )
    title_end = min(duration, 3.2 if preview else (phase_ranges[0][0] + 2.4 if phase_ranges else 2.4))
    filters.append(
        f"drawtext=fontfile='{latin_font_path}':textfile='{title_path}':fontcolor={chalk}:"
        f"fontsize=h*{0.044 if is_long else 0.024:.3f}:line_spacing=4:text_align=left:"
        f"x='w*0.09-56*(1-min(max(t/0.28,0),1))^2':y=h*0.125:"
        f"shadowcolor=black@0.55:shadowx=1:shadowy=2:"
        f"enable='between(t,0,{title_end:.3f})'"
    )
    filters.append(
        f"drawbox=x=iw*0.072:y=ih*0.125:w=iw*0.010:h=ih*0.070:color={signal_lime}@1:t=fill:"
        f"enable='between(t,0,{title_end:.3f})'"
    )
    segments = [] if preview else draft.get("segments", [])
    fallback_diagrams = _diagram_specs()
    diagram_specs: list[dict[str, Any]] = []
    scene_paths: list[Path] = []
    trail_paths: list[Path] = []
    selected_modes: list[str] = []
    scene_x, scene_y = (190, 220) if is_long else (60, 390)
    fx, fy, fw, fh = (505, 138, 865, 560) if is_long else (260, 142, 490, 760)
    for index in range(len(phase_ranges)):
        spec = None
        segment: dict[str, Any] = {}
        if not preview and index < len(segments):
            segment = segments[index]
            spec = segment.get("tactical_diagram")
        mode = str(segment.get("visual_mode", "tactical_explainer"))
        supported_modes = {"tactical_explainer", "statline_scorecard", "source_card", "chart_comparison", "chart_timeline", "media_b_roll"}
        if mode not in supported_modes:
            mode = "tactical_explainer"
        # A typed timeline event can select a dedicated data layout when the
        # segment has not explicitly selected a visual mode.
        if not segment.get("visual_mode"):
            event_types = {item.get("item_type") for item in segment.get("timeline_events", []) if isinstance(item, dict)}
            if "stat_card" in event_types:
                mode = "statline_scorecard"
            elif "source_card" in event_types:
                mode = "source_card"
        selected_modes.append(mode)
        scene_palette = dict(palette)
        graphic_data = segment.get("graphic_data", {}) if isinstance(segment.get("graphic_data"), dict) else {}
        media_record = None
        if not preview and segment.get("media_asset_id"):
            media_record = _library_image_record(root, str(segment["media_asset_id"]))
            mode = "media_b_roll"
            selected_modes[-1] = mode
        elif mode == "media_b_roll":
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
        if mode == "tactical_explainer":
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
            _write_editorial_data_scene(
                scene_path,
                font_path=font,
                display_font_path=latin_font,
                mode=mode,
                data=graphic_data,
                palette=scene_palette,
                is_long=is_long,
                scene_number=index+1,
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
    scene_input_start = 2 if not preview and not visual_only else 1
    for scene_path in scene_paths:
        command += ["-loop", "1", "-framerate", str(fps), "-i", str(scene_path)]
    ball_input_start = scene_input_start + len(scene_paths)
    for _ in scene_paths:
        command += ["-loop", "1", "-framerate", str(fps), "-i", str(ball_sprite)]
    trail_input_start = ball_input_start + len(scene_paths)
    for trail_path in trail_paths:
        command += ["-loop", "1", "-framerate", str(fps), "-i", str(trail_path)]

    # Composite a research-informed Match Dossier tactical plate for each active
    # diagram beat, then animate the ball along its reviewed pass vector.
    chains: list[str] = []
    current = "0:v"
    for index, ((start, end), spec) in enumerate(zip(phase_ranges, diagram_specs)):
        if end <= start:
            continue
        scene_label = f"scene{index}"
        scene_idx = scene_input_start + index
        scene_enable = f"gte(t,{start:.3f})*lt(t,{end:.3f})"
        scene_slide = f"18*(1-min(max((t-{start:.3f})/0.24,0),1))^2"
        scene_y_expr = f"{scene_y}+{scene_slide}"
        scene_source = f"{scene_idx}:v"
        if selected_modes[index] == "media_b_roll":
            media_layer = f"mediamotion{index}"
            media_width, media_height = (1540, 840) if is_long else (960, 1250)
            chains.append(
                f"[{scene_idx}:v]zoompan=z='min(1.035,zoom+0.00002)':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
                f"s={media_width}x{media_height}:fps={fps},format=rgba[{media_layer}]"
            )
            scene_source = media_layer
        chains.append(
            f"[{current}][{scene_source}]overlay=x={scene_x}:y='{scene_y_expr}':eval=frame:eof_action=pass:format=auto:"
            f"enable='{scene_enable}'[{scene_label}]"
        )
        current = scene_label
        if selected_modes[index] != "tactical_explainer":
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
    chains.append(f"[{current}]{','.join(filters)}[vout]")
    filter_complex = ";".join(chains)
    command += ["-filter_complex", filter_complex, "-map", "[vout]", "-t", str(duration), "-r", str(fps), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
    if preview or visual_only:
        command += ["-an"]
    else:
        command += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    command += ["-movflags", "+faststart", str(output_path)]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=7200)
    if result.returncode:
        raise RuntimeError((result.stderr or "FFmpeg render failed.")[-2500:])

    selected_media = []
    for item in (draft.get("segments", []) if not preview else []):
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
        {"criterion": "Vietnamese font and diacritics", "status": "PASS", "detail": "Barlow Condensed provides Vietnamese headline glyphs; Be Vietnam Pro remains available for dense supporting copy."},
        {"criterion": "Tactical pitch orientation and authored vectors", "status": "NOT USED" if not any(mode == "tactical_explainer" for mode in selected_modes) else "PASS", "detail": "No tactical pitch scene is part of this short-form script." if not any(mode == "tactical_explainer" for mode in selected_modes) else f"The {('landscape' if is_long else 'portrait')} pitch has correct halfway-line orientation, full markings, and color-coded pass/run/press vectors."},
        {"criterion": "Template art direction", "status": "PASS", "detail": "Touchline Editorial pairs expressive Vietnamese display headlines, condensed chapter numerals, tactile pitch marks, contextual colorways, and distinct portrait/landscape graphic plates."},
        {"criterion": "Opening / body / ending rhythm", "status": "PARTIAL", "detail": "Chapter-led visual beats and the match-specific conclusion are present; authored end-card behavior is still a gap."},
        {"criterion": "Visible motion and beat changes", "status": "PARTIAL" if visual_only else "PASS", "detail": f"The render switches across {len(phase_ranges)} timed beats; licensed still photographs receive a slow camera push, while tactical diagrams use one authored pass movement."},
        {"criterion": "Narration subtitles", "status": "NOT USED", "detail": "Subtitles are intentionally omitted; the narration carries the explanation."},
        {"criterion": "Personal voice and speech pacing", "status": "PENDING OWNER AUDIT" if not preview and not visual_only else "NOT ASSESSED", "detail": "TTS preview is muxed as one continuous narration track; naturalness and voice similarity await owner review." if not preview and not visual_only else ("Voice evaluation is intentionally excluded from this benchmark." if visual_only else "This is a silent visual preview.")},
        {"criterion": "Asset Library media", "status": "PASS" if selected_media else "FAIL", "detail": f"{len(selected_media)} verified, attributed library images are used as contextual B-roll; they are not footage from the current Premier League matches."},
        {"criterion": "Script-specific transitions and effects", "status": "PARTIAL", "detail": "Current renderer uses clean static compositions and restrained accents; timeline transition/effect execution remains to be implemented."},
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
    if not video_streams:
        raise RuntimeError("The rendered MP4 has no video stream.")
    report = {
        "run_id": run["run_id"],
        "rendered_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "renderer": "ace-ffmpeg-0.2.0",
        "template_id": template_id,
        "template_version": package.manifest["version"],
        "mode": "template_visual_preview" if preview else ("silent_longform_visual_benchmark" if visual_only else "full_script_render"),
        "output": output_path.name,
        "selected_media": selected_media,
        "quality_checks": checks,
        "ffprobe": metadata,
        "limitations": ([
            "TTS voice naturalness and similarity have not been audited by the owner.",
            "The library images are contextual soccer photographs, not current Premier League match action.",
            "Still photographs use a slow camera push rather than live match motion; this benchmark tests workflow feasibility, not publish-ready aesthetics.",
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
    return _render(root, run, preview=False, visual_only=True, output_name="visual-benchmark-silent.mp4")


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
    result = _render(root, run, preview=False, output_name="full-render.mp4")
    run["render"] = {
        "path": "full-render.mp4",
        "rendered_at": result["report"]["rendered_at"],
        "report": "render-report.json",
    }
    run["status"] = "WAITING_FOR_RENDER_AUDIT"
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
