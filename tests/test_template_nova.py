"""Nova 0.9.0 acceptance: hook card + hero metric, both aspects."""

from pathlib import Path

from template_foundation import resolve_template
from apps.content_workflow import VISUAL_MODES, _clean_segment

ROOT = Path(__file__).resolve().parent.parent


def _package(template_id):
    package = resolve_template(ROOT, template_id, version="0.9.0", allow_draft=True)
    assert package.manifest["version"] == "0.9.0"
    assert package.catalog_record["path"].endswith("0.9.0")
    return package


def test_nova_resolves_by_default_for_both_aspects():
    short = resolve_template(ROOT, "allen-knows-ball.shortform-analyst", allow_draft=True)
    long = resolve_template(ROOT, "allen-knows-ball.longform-analyst", allow_draft=True)
    assert short.manifest["version"] == "0.9.0"
    assert long.manifest["version"] == "0.9.0"


def test_nova_declares_hook_and_hero():
    for template_id in ("allen-knows-ball.shortform-analyst",
                        "allen-knows-ball.longform-analyst"):
        package = _package(template_id)
        mode_ids = [m["id"] for m in package.visual_modes["modes"]]
        assert "hook_card" in mode_ids
        layout_ids = [item["id"] for item in package.graphic_templates["layouts"]]
        assert "hook_card" in layout_ids
        assert "hook_card" in package.graphic_templates["layout_grammar"]
        statline = next(item for item in package.graphic_templates["layouts"]
                        if item["id"] == "statline_scorecard")
        assert "hero_metric" in statline.get("variants", {})
        assert "hook_card" in package.design_tokens["layout"]


def test_nova_layout_styles_cover_hook_and_hero():
    for version_path in ("templates/allen-knows-ball/0.9.0",
                         "templates/allen-knows-ball/longform-0.9.0"):
        import json
        styles = json.loads((ROOT / "template_foundation" / version_path
                             / "graphic-layout-styles.json").read_text(encoding="utf-8"))
        assert styles["template_version"] == "0.9.0"
        assert "hook_card" in styles["distinct_layouts"]
        assert "hero_variant" in styles["distinct_layouts"]["statline_scorecard"]


def test_workflow_accepts_hook_card_mode():
    assert "hook_card" in VISUAL_MODES
    segment = _clean_segment({
        "narration": "Câu hỏi mở đầu rõ ràng cho video",
        "visual": "Hook card",
        "visual_mode": "hook_card",
        "graphic_data": {"hook_text": "Ai đang đọc trận đấu hay nhất?"},
        "duration_seconds": 5,
    })
    assert segment is not None and segment["visual_mode"] == "hook_card"
    assert segment["graphic_data"]["hook_text"] == "Ai đang đọc trận đấu hay nhất?"


def _scene(package, mode, data, tmp_path, name, is_long):
    from apps.video_renderer import _write_editorial_data_scene
    out = tmp_path / name
    _write_editorial_data_scene(
        out,
        font_path=package.root / "resources/fonts/BeVietnamPro-Bold.ttf",
        display_font_path=package.root / "resources/fonts/BarlowCondensed-Bold.ttf",
        mode=mode, data=data, palette=package.design_tokens["palette"],
        is_long=is_long, scene_number=1,
    )
    return out


def test_hook_plate_renders_and_stays_legible_at_phone_width(tmp_path):
    from PIL import Image
    package = _package("allen-knows-ball.shortform-analyst")
    hook_text = "Ai đang đọc trận đấu hay nhất?"
    assert 5 <= len(hook_text.split()) <= 8
    out = _scene(package, "hook_card", {"hook_text": hook_text}, tmp_path, "hook.png", False)
    with Image.open(out) as plate:
        assert plate.size == (960, 1250)
        phone = plate.resize((350, round(350 * plate.height / plate.width)))
        assert phone.size[0] == 350
        # Ink field with lime rule: top strip must carry the accent color.
        pixels = phone.convert("RGB")
        lime = (232, 199, 90)
        top_row = [pixels.getpixel((x, 2)) for x in range(0, 350, 7)]
        assert any(abs(r - lime[0]) + abs(g - lime[1]) + abs(b - lime[2]) < 90
                   for r, g, b in top_row)


def test_hero_plate_renders_single_numeral_at_3x(tmp_path):
    from PIL import Image
    package = _package("allen-knows-ball.shortform-analyst")
    out = _scene(package, "statline_scorecard", {
        "hero": {"label": "BÀN THẮNG QUYẾT ĐỊNH", "value": "19"},
        "source": "Demo", "date": "Demo",
    }, tmp_path, "hero.png", False)
    with Image.open(out) as plate:
        assert plate.size == (960, 1250)


def test_longform_hook_and_hero_render(tmp_path):
    package = _package("allen-knows-ball.longform-analyst")
    _scene(package, "hook_card", {"hook_text": "Pressing tầm cao có còn hiệu quả?"}, tmp_path, "hook-long.png", True)
    _scene(package, "statline_scorecard", {
        "hero": {"label": "CƠ HỘI RÕ RỆT", "value": "7"},
        "source": "Demo", "date": "Demo",
    }, tmp_path, "hero-long.png", True)
