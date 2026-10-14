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
    for skill in ("frontend-design", "canvas-design", "theme-factory"):
        base = ROOT / "skills" / skill
        assert (base / "SKILL.md").is_file()
        assert (base / "LICENSE.txt").is_file()
        _frontmatter(base / "SKILL.md")
    assert len(list((ROOT / "skills/theme-factory/themes").glob("*.md"))) == 10
    assert (ROOT / "skills/theme-factory/theme-showcase.pdf").is_file()
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


def _sampled_pixels(image):
    raw = image.convert("RGB").tobytes()
    step = max(1, (len(raw) // 3) // 4000) * 3
    return [tuple(raw[i:i + 3]) for i in range(0, len(raw), step)]


def test_redesign_stays_in_locked_palette():
    from apps.studio_templates.redesign_mr02_skill import render_redesign

    locked = [(22, 27, 44), (32, 38, 60), (224, 112, 95),
              (244, 242, 236), (90, 107, 140), (139, 150, 176)]
    for image in (
            render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay"),
            render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay",
                            depth=True, seed=7),
            render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay",
                            depth="lite", seed=7)):
        stray = 0
        for rgb in _sampled_pixels(image):
            if not any(all(abs(a - b) <= 90 for a, b in zip(rgb, base)) for base in locked):
                stray += 1
        assert stray == 0


def test_depth_pass_is_deterministic_and_visible():
    from apps.studio_templates.redesign_mr02_skill import render_redesign

    flat = render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay")
    first = render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay",
                            depth=True, seed=7)
    second = render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay",
                             depth=True, seed=7)
    assert first.size == (1080, 1920)
    assert first.tobytes() == second.tobytes()
    assert first.tobytes() != flat.tobytes()


def test_depth_lite_differs_from_full():
    from apps.studio_templates.redesign_mr02_skill import render_redesign

    full = render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay",
                           depth=True, seed=7)
    lite = render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay",
                           depth="lite", seed=7)
    assert lite.size == (1080, 1920)
    assert lite.tobytes() != full.tobytes()


def test_detailing_is_deterministic_data_free_and_locked():
    from apps.studio_templates.redesign_mr02_skill import (
        apply_mr02_detailing,
        render_redesign,
    )

    base = render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay",
                           depth="lite", seed=7)
    first = apply_mr02_detailing(base)
    second = apply_mr02_detailing(base)
    assert first.size == (1080, 1920)
    assert first.tobytes() == second.tobytes()
    assert first.tobytes() != base.tobytes()
    # Corner mark lands ink-on-coral; perforation dots land mist-on-ink.
    assert first.getpixel((48, 160)) == (22, 27, 44)
    assert first.getpixel((76, 1748)) == (139, 150, 176)
    locked = [(22, 27, 44), (32, 38, 60), (224, 112, 95),
              (244, 242, 236), (90, 107, 140), (139, 150, 176)]
    raw = first.convert("RGB").tobytes()
    step = max(1, (len(raw) // 3) // 4000) * 3
    stray = sum(
        1 for i in range(0, len(raw), step)
        if not any(all(abs(a - b) <= 90 for a, b in zip(tuple(raw[i:i + 3]), base_color))
                   for base_color in locked))
    assert stray == 0


def test_detail_primitives_catalog_has_no_data_carriers():
    from apps.studio_templates.detailing import detail_report

    assert all(item["carries_data"] is False for item in detail_report())
    assert len(detail_report()) == 7


def test_white_colorways_render_and_pass_contrast():
    from apps.studio_templates.audit_cards import contrast, hex_rgb
    from apps.studio_templates.redesign_mr02_skill import (
        COLORWAYS,
        apply_mr02_detailing,
        render_redesign,
    )

    assert set(COLORWAYS) == {"san-trang", "co-sang"}
    for cw_id, palette in COLORWAYS.items():
        finished = apply_mr02_detailing(
            render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay",
                            depth="lite", seed=7, palette=palette),
            palette=palette)
        assert finished.size == (1080, 1920), cw_id
    white = render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay",
                            palette=COLORWAYS["san-trang"])
    green = render_redesign("HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay",
                            palette=COLORWAYS["co-sang"])
    assert white.size == green.size == (1080, 1920)
    assert white.getpixel((540, 100)) == (244, 242, 236)
    assert white.getpixel((540, 1500)) == (230, 226, 212)
    assert green.getpixel((540, 100)) == (31, 122, 77)
    assert green.getpixel((540, 1900)) == (22, 27, 44)
    ink, paper = hex_rgb("#161B2C"), hex_rgb("#F4F2EC")
    slate, field_green = hex_rgb("#5A6B8C"), hex_rgb("#1F7A4D")
    assert contrast(ink, paper) >= 7.0
    assert contrast(slate, paper) >= 4.5
    assert contrast(paper, field_green) >= 3.0
