"""Template v8.0.0 Sports Kit: Nova foundation + 3 owner card sets + Manim atoms."""

from pathlib import Path

from template_foundation import resolve_template
from apps.content_workflow import VISUAL_MODES, _clean_segment

ROOT = Path(__file__).resolve().parent.parent

NEW_MODES = {"comparison_duel", "stat_leader", "player_poster",
             "goal_card", "fixture_card", "score_card"}


def test_sportskit_stays_pinned():
    short = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                             version="8.0.0", allow_draft=True)
    assert short.manifest["version"] == "8.0.0"
    assert "Sports Kit" in short.manifest["description"]
    layout_ids = [item["id"] for item in short.graphic_templates["layouts"]]
    for mode in NEW_MODES | {"hook_card", "player_card", "statline_scorecard"}:
        assert mode in layout_ids
    mode_ids = [m["id"] for m in short.visual_modes["modes"]]
    for mode in NEW_MODES:
        assert mode in mode_ids
    colorways = [c["id"] for c in short.color_systems["colorways"]]
    assert "matchday-red" in colorways and "san-dem" in colorways
    assert "kit_red" in short.design_tokens["palette"]
    assert "manim_atoms" in short.design_tokens["motion"]


def test_longform_resolves_pinned():
    long = resolve_template(ROOT, "allen-knows-ball.longform-analyst",
                            version="8.0.0", allow_draft=True)
    assert long.manifest["version"] == "8.0.0"


def test_workflow_accepts_sportskit_modes():
    assert NEW_MODES <= VISUAL_MODES
    segment = _clean_segment({
        "narration": "Mot nhan dinh cu the ve tran dau toi nay",
        "visual": "Bang ti so doi dau",
        "visual_mode": "comparison_duel",
        "graphic_data": {"metrics": [{"label": "Co hoi", "home": "4", "away": "2"}],
                         "source": "Demo", "date": "Demo"},
        "duration_seconds": 6,
    })
    assert segment is not None and segment["visual_mode"] == "comparison_duel"


def test_manim_atoms_importable():
    from apps.manim_kit import MANIM_MODES
    assert set(MANIM_MODES) == {"comparison_duel", "stat_leader", "player_poster",
                                "goal_card", "fixture_card", "score_card"}
    # v8 atoms were superseded by the v9 Kit set; the rendered proofs stay.
    media = ROOT / "template_foundation/templates/allen-knows-ball/8.0.0/previews/manim"
    rendered = {p.stem for p in media.rglob("*.mp4")}
    assert {"HookCard", "ScoreCard"} <= rendered


def test_pil_plates_for_new_modes(tmp_path):
    from apps.video_renderer import _write_editorial_data_scene
    package = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                               version="8.0.0", allow_draft=True)
    kwargs = dict(
        font_path=package.root / "resources/fonts/BeVietnamPro-Bold.ttf",
        display_font_path=package.root / "resources/fonts/BarlowCondensed-Bold.ttf",
        palette=package.design_tokens["palette"], is_long=False, scene_number=1,
    )
    samples = {
        "comparison_duel": {"headline": "CON SO NOI GI?",
                            "metrics": [{"label": "Co hoi", "home": "4", "away": "2"}],
                            "source": "Demo", "date": "Demo"},
        "stat_leader": {"headline": "THONG KE CHINH",
                        "stats": [{"label": "Ban thang", "value": "19"},
                                  {"label": "Kien tao", "value": "7"}],
                        "source": "Demo", "date": "Demo"},
        "player_poster": {"player_name": "Nguyen Van A",
                          "stats": [{"label": "Ban", "value": "19"}],
                          "source": "Demo", "date": "Demo"},
        "goal_card": {"hook_text": "Ban thang mo ty so tran dau",
                      "source": "Demo", "date": "Demo"},
        "fixture_card": {"headline": "LICH THI DAU",
                         "fixtures": [{"home": "Ha Noi", "away": "Nam Dinh",
                                       "date": "19:15 Hang Day"}],
                         "source": "Demo", "date": "Demo"},
        "score_card": {"home": "Ha Noi", "away": "Nam Dinh", "score": "2 - 0",
                       "source": "Demo", "date": "Demo"},
    }
    for mode, data in samples.items():
        out = tmp_path / f"{mode}.png"
        _write_editorial_data_scene(out, mode=mode, data=data, **kwargs)
        assert out.stat().st_size > 20000, mode
