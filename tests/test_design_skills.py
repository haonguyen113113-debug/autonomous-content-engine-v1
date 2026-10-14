"""Design skills install + MR-02 skill-driven redesign."""

from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def _frontmatter(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("<!-- Source: https://")
    assert "\nname: " in text and "\ndescription: " in text
    return text


def test_skills_installed_verbatim_with_licenses():
    for skill in ("frontend-design", "canvas-design"):
        base = ROOT / "skills" / skill
        assert (base / "SKILL.md").is_file()
        assert (base / "LICENSE.txt").is_file()
        _frontmatter(base / "SKILL.md")
    fonts = list((ROOT / "skills/canvas-design/canvas-fonts").glob("*.ttf"))
    assert len(fonts) >= 50
    assert (ROOT / "skills/canvas-design/canvas-fonts/BigShoulders-Bold.ttf").is_file()


def test_redesign_renders_locked_canvas():
    from apps.studio_templates.redesign_mr02_skill import (
        W, H, parse_score, render_redesign,
    )
    assert (W, H) == (1080, 1920)
    assert parse_score("2 - 0") == (2, 0)
    home_win = render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay")
    assert home_win.size == (1080, 1920)
    # Winner coral field on top, ink loser field below the split.
    assert home_win.getpixel((540, 100)) == (224, 112, 95)
    assert home_win.getpixel((540, 1900)) == (22, 27, 44)
    # Away-win mirrors; draw stays full ink.
    away_win = render_redesign("HÀ NỘI", "NAM ĐỊNH", "1 - 2", "V.League", "Tối nay")
    assert away_win.getpixel((540, 100)) == (224, 112, 95)
    drawn = render_redesign("HÀ NỘI", "NAM ĐỊNH", "1 - 1", "V.League", "Tối nay")
    assert drawn.getpixel((540, 100)) == (22, 27, 44)


def test_redesign_stays_in_locked_palette():
    from apps.studio_templates.redesign_mr02_skill import render_redesign

    locked = [(22, 27, 44), (32, 38, 60), (224, 112, 95),
              (244, 242, 236), (90, 107, 140), (139, 150, 176)]
    image = render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay")
    pixels = list(image.getdata())
    step = max(1, len(pixels) // 4000)
    stray = 0
    for px in pixels[::step]:
        rgb = px[:3] if isinstance(px, tuple) else (px, px, px)
        if not any(all(abs(a - b) <= 90 for a, b in zip(rgb, base)) for base in locked):
            stray += 1
    assert stray == 0
