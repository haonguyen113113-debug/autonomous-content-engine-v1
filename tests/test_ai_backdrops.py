"""AI photographic beds: provenance, fallback, integration."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_ai_backdrop_ships_with_license():
    package_dir = ROOT / "template_foundation/templates/allen-knows-ball/4.0.0"
    photo = package_dir / "resources/ai-night-pitch-p.jpg"
    assert photo.is_file() and photo.stat().st_size > 10000
    import json
    licenses = json.loads((package_dir / "LICENSES.json").read_text(encoding="utf-8"))
    families = [entry.get("family", "") for entry in licenses["third_party_resources"]]
    assert any("AI" in family for family in families)


def test_photo_bed_falls_back_without_photo(tmp_path):
    from PIL import Image
    from apps.video_renderer import _photo_bed
    image = Image.new("RGBA", (200, 200), (10, 15, 13, 255))
    assert _photo_bed(image, tmp_path / "missing.png", 100, 100, 1) is False


def test_hook_uses_photo_bed_when_present(tmp_path):
    from template_foundation import resolve_template
    from apps.video_renderer import _write_editorial_data_scene
    package = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                               version="4.0.0", allow_draft=True)
    out = tmp_path / "hook.png"
    _write_editorial_data_scene(
        out, mode="hook_card", data={"hook_text": "Test *accent* here"},
        font_path=package.root / "resources/fonts/BeVietnamPro-Bold.ttf",
        display_font_path=package.root / "resources/fonts/BarlowCondensed-Bold.ttf",
        palette=package.design_tokens["palette"], is_long=False, scene_number=1)
    assert out.stat().st_size > 20000
