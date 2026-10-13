"""Template v3.0.0 Neon Grid: Aperture-grade type, cyberpunk football system."""

from pathlib import Path

from template_foundation import resolve_template
from apps.video_renderer import _accent_split

ROOT = Path(__file__).resolve().parent.parent


def test_neon_resolves_pinned():
    short = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                             version="3.0.0", allow_draft=True)
    assert short.manifest["version"] == "3.0.0"
    palette = short.design_tokens["palette"]
    assert palette["team_home"] == "#00E5FF"
    assert palette["team_away"] == "#FF2FB3"
    import json
    colorways = json.loads((ROOT / "template_foundation/templates/allen-knows-ball/3.0.0/color-systems.json").read_text(encoding="utf-8"))["colorways"]
    assert [c["id"] for c in colorways][0] == "neon-grid"


def test_accent_markup_split():
    assert _accent_split("Hàng thủ *sập đổ* tối nay") == [
        ("Hàng thủ ", False), ("sập đổ", True), (" tối nay", False)]
    assert _accent_split("Không markup") == [("Không markup", False)]


def test_neon_plates_render(tmp_path):
    from apps.video_renderer import _write_editorial_data_scene
    package = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                               version="3.0.0", allow_draft=True)
    kwargs = dict(
        font_path=package.root / "resources/fonts/BeVietnamPro-Bold.ttf",
        display_font_path=package.root / "resources/fonts/BarlowCondensed-Bold.ttf",
        palette=package.design_tokens["palette"], is_long=False, scene_number=2,
    )
    jobs = {
        "hook.png": ("hook_card", {"hook_text": "Hàng thủ *sập đổ* tối nay"}),
        "hero.png": ("statline_scorecard", {"hero": {"label": "BÀN", "value": "19"},
                                            "source": "Demo", "date": "Demo"}),
        "statline.png": ("statline_scorecard", {
            "headline": "Bên nào pressing *rát* hơn?",
            "teams": ["VIE", "MAS"],
            "metrics": [{"label": "Thu hồi", "home": "11", "away": "14"}],
            "source": "Demo", "date": "Demo"}),
        "source.png": ("source_card", {"source": "VNExpress", "date": "07/10/2026",
                                       "claim": "Việt Nam áp đảo đối đầu.",
                                       "url": "https://example.invalid/x"}),
        "chart.png": ("chart_comparison", {
            "chart_type": "bar", "headline": "Pressing *rát*",
            "values": [{"label": "VIE", "value": 6}, {"label": "MAS", "value": 4}],
            "source": "Demo", "date": "Demo"}),
    }
    for name, (mode, data) in jobs.items():
        out = tmp_path / name
        _write_editorial_data_scene(out, mode=mode, data=data, **kwargs)
        assert out.stat().st_size > 2000, name
