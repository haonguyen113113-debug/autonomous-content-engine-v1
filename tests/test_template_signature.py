"""Template v2.0.0 Signature: faux-3D finish on a new identity."""

from pathlib import Path

from template_foundation import resolve_template
from apps.video_renderer import _extrude, _spotlight, _vignette

ROOT = Path(__file__).resolve().parent.parent


def test_signature_resolves_pinned():
    short = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                             version="2.0.0", allow_draft=True)
    assert short.manifest["version"] == "2.0.0"
    assert "finish" in short.design_tokens["motion"]
    assert "Signature" in short.manifest["description"]


def test_older_versions_stay_pinned():
    for version in ("0.9.0", "1.0.0", "2.0.0"):
        package = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                                   version=version, allow_draft=True)
        assert package.manifest["version"] == version


def test_finish_helpers_run(tmp_path):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGBA", (200, 200), (17, 23, 33, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    _spotlight(image, 100, 100, 80, (232, 199, 90), 60)
    font = ImageFont.load_default()
    _extrude(draw, (50, 90), "19", font, (232, 199, 90, 255), depth=2)
    _vignette(image)
    out = tmp_path / "finish.png"
    image.save(out)
    assert out.stat().st_size > 500


def test_signature_plates_render(tmp_path):
    from apps.video_renderer import _write_editorial_data_scene
    package = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                               version="2.0.0", allow_draft=True)
    kwargs = dict(
        font_path=package.root / "resources/fonts/BeVietnamPro-Bold.ttf",
        display_font_path=package.root / "resources/fonts/BarlowCondensed-Bold.ttf",
        palette=package.design_tokens["palette"], is_long=False, scene_number=1,
    )
    jobs = {
        "hook.png": ("hook_card", {"hook_text": "Ai đang đọc trận đấu hay nhất?"}),
        "hero.png": ("statline_scorecard", {"hero": {"label": "BÀN", "value": "19"},
                                            "source": "Demo", "date": "Demo"}),
        "statline.png": ("statline_scorecard", {
            "headline": "H?", "teams": ["A", "B"],
            "metrics": [{"label": "M", "home": "4", "away": "2"}],
            "source": "Demo", "date": "Demo"}),
        "source.png": ("source_card", {"source": "S", "date": "D",
                                       "claim": "Luận điểm kiểm tra.",
                                       "url": "https://example.invalid/x"}),
    }
    for name, (mode, data) in jobs.items():
        out = tmp_path / name
        _write_editorial_data_scene(out, mode=mode, data=data, **kwargs)
        assert out.stat().st_size > 2000, name
