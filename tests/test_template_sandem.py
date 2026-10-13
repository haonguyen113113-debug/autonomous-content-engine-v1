"""Template v4.0.0 San Dem: night-football identity, ticket stubs, chalkboards."""

from pathlib import Path

from template_foundation import resolve_template

ROOT = Path(__file__).resolve().parent.parent


def test_sandem_resolves_pinned():
    short = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                             version="4.0.0", allow_draft=True)
    long = resolve_template(ROOT, "allen-knows-ball.longform-analyst",
                            version="4.0.0", allow_draft=True)
    assert short.manifest["version"] == "4.0.0"
    assert long.manifest["version"] == "4.0.0"
    palette = short.design_tokens["palette"]
    assert palette["signal_lime"] == "#FFB300"
    assert palette["team_home"] == "#F5F2E8"
    import json
    colorways = json.loads((ROOT / "template_foundation/templates/allen-knows-ball/4.0.0/color-systems.json").read_text(encoding="utf-8"))["colorways"]
    assert [c["id"] for c in colorways][0] == "san-dem"


def test_older_versions_stay_pinned():
    for version in ("0.9.0", "1.0.0", "2.0.0", "3.0.0"):
        package = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                                   version=version, allow_draft=True)
        assert package.manifest["version"] == version


def test_night_field_stays_dark(tmp_path):
    from PIL import Image, ImageStat
    from apps.video_renderer import _night_field
    image = Image.new("RGBA", (480, 625), (10, 15, 13, 255))
    _night_field(image, 240, 312, 2, (10, 15, 13, 255), (18, 33, 27, 255))
    mean = sum(ImageStat.Stat(image.convert("RGB")).mean) / 3
    # Night bed stays moody but lifted: cones/bokeh are visible accents.
    assert mean < 95


def test_sandem_plates_render(tmp_path):
    from apps.video_renderer import _write_editorial_data_scene
    package = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                               version="4.0.0", allow_draft=True)
    kwargs = dict(
        font_path=package.root / "resources/fonts/BeVietnamPro-Bold.ttf",
        display_font_path=package.root / "resources/fonts/BarlowCondensed-Bold.ttf",
        palette=package.design_tokens["palette"], is_long=False, scene_number=1,
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
