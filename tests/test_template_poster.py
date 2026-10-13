"""Template v7.0.0 poster player cards (Canva-pattern anatomy)."""

from pathlib import Path

from template_foundation import resolve_template
from apps.content_workflow import VISUAL_MODES, _clean_segment

ROOT = Path(__file__).resolve().parent.parent


def test_poster_stays_pinned():
    short = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                             version="7.0.0", allow_draft=True)
    assert short.manifest["version"] == "7.0.0"
    assert any("PermanentMarker" in item for item in short.manifest["font_resources"])
    mode_ids = [m["id"] for m in short.visual_modes["modes"]]
    assert "player_card" in mode_ids
    layout_ids = [item["id"] for item in short.graphic_templates["layouts"]]
    assert "player_card" in layout_ids


def test_workflow_accepts_player_card():
    assert "player_card" in VISUAL_MODES
    segment = _clean_segment({
        "narration": "Một vai trò đặc biệt trong đội hình",
        "visual": "Player card",
        "visual_mode": "player_card",
        "graphic_data": {"player_name": "Nguyen Van A",
                         "stats": [{"label": "Ban thang", "value": "19"}]},
        "duration_seconds": 6,
    })
    assert segment is not None and segment["visual_mode"] == "player_card"


def test_player_card_renders_with_and_without_photo(tmp_path):
    from PIL import Image
    from apps.video_renderer import _write_editorial_data_scene
    package = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                               version="7.0.0", allow_draft=True)
    kwargs = dict(
        font_path=package.root / "resources/fonts/BeVietnamPro-Bold.ttf",
        display_font_path=package.root / "resources/fonts/BarlowCondensed-Bold.ttf",
        palette=package.design_tokens["palette"], is_long=False, scene_number=1,
    )
    photo = tmp_path / "player.png"
    Image.new("RGB", (600, 900), (20, 60, 50)).save(photo)
    data = {"player_name": "Nguyen Van A", "player_detail": "Tien dao · #19",
            "stats": [{"label": "Ban thang", "value": "19"},
                      {"label": "Kien tao", "value": "7"},
                      {"label": "Tran", "value": "63"}],
            "source": "Demo", "date": "Demo", "media_file": str(photo)}
    out = tmp_path / "card-photo.png"
    _write_editorial_data_scene(out, mode="player_card", data=data, **kwargs)
    assert out.stat().st_size > 20000
    out2 = tmp_path / "card-nophoto.png"
    data2 = dict(data)
    data2.pop("media_file")
    _write_editorial_data_scene(out2, mode="player_card", data=data2, **kwargs)
    assert out2.stat().st_size > 20000
