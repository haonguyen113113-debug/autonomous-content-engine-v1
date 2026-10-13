"""Template v1.0.0 Impact: slide, count-up, stagger + probe fixes."""

from pathlib import Path

from template_foundation import resolve_template
from apps.video_renderer import _count_steps, _hook_lines

ROOT = Path(__file__).resolve().parent.parent


def test_impact_resolves_by_default():
    short = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                             version="1.0.0", allow_draft=True)
    long = resolve_template(ROOT, "allen-knows-ball.longform-analyst",
                            version="1.0.0", allow_draft=True)
    assert short.manifest["version"] == "1.0.0"
    assert long.manifest["version"] == "1.0.0"
    assert short.timeline["motion"]["scene_enter"].startswith("slide-in")
    assert short.design_tokens["motion"]["count_up"].startswith("Hero")
    assert "motion_notes" in short.graphic_templates


def test_hook_lines_balance():
    lines = _hook_lines("Ai đang đọc trận đấu hay nhất?")
    assert 1 <= len(lines) <= 3
    assert " ".join(lines) == "Ai đang đọc trận đấu hay nhất?"
    assert _hook_lines("") == ["CÂU HỎI TRẬN ĐẤU"]


def test_count_steps_numeric_and_static():
    assert _count_steps("19") == ["3", "6", "10", "13", "16", "19"]
    assert _count_steps("19")[-1] == "19"
    assert len(_count_steps("19")) == 6
    stepped = _count_steps("2,5 triệu €")
    assert stepped[-1] == "2,5 triệu €" and "," in stepped[0]
    assert _count_steps("—") == ["—"]
    assert _count_steps("") == ["—"]


def test_workflow_prompt_enforces_mode_diversity():
    source = (ROOT / "apps/content_workflow.py").read_text(encoding="utf-8")
    assert "never repeat one mode more than" in source
    assert "hook_card" in source


def test_asset_checks_record_discovery_provenance():
    source = (ROOT / "apps/content_workflow.py").read_text(encoding="utf-8")
    assert "provider_statuses" in source and "discovery_query" in source


def test_bare_plates_render(tmp_path):
    from apps.video_renderer import _write_editorial_data_scene
    package = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                               version="1.0.0", allow_draft=True)
    kwargs = dict(
        font_path=package.root / "resources/fonts/BeVietnamPro-Bold.ttf",
        display_font_path=package.root / "resources/fonts/BarlowCondensed-Bold.ttf",
        palette=package.design_tokens["palette"], is_long=False, scene_number=1,
    )
    hook_bare = tmp_path / "hook-bare.png"
    _write_editorial_data_scene(hook_bare, mode="hook_card",
                                data={"hook_text": "Ai đang đọc trận đấu hay nhất?"},
                                **kwargs, bare=True)
    hero_bare = tmp_path / "hero-bare.png"
    _write_editorial_data_scene(hero_bare, mode="statline_scorecard",
                                data={"hero": {"label": "BÀN", "value": "19"},
                                      "source": "Demo", "date": "Demo"},
                                **kwargs, bare=True)
    assert hook_bare.stat().st_size > 1000 and hero_bare.stat().st_size > 1000
