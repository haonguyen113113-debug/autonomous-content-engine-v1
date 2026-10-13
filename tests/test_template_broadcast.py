"""Template v6.0.0 Broadcast Card: Mixkit-pattern tick rulers, notches, frames."""

from pathlib import Path

from template_foundation import resolve_template
from apps.video_renderer import _notch_rect, _tick_ruler

ROOT = Path(__file__).resolve().parent.parent


def test_broadcast_stays_pinned():
    short = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                             version="6.0.0", allow_draft=True)
    assert short.manifest["version"] == "6.0.0"
    assert "Broadcast Card" in short.manifest["description"]


def test_tick_ruler_and_notch_draw(tmp_path):
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (400, 200), (10, 15, 13, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    _tick_ruler(draw, 20, 100, 360, (255, 179, 0, 255), 1)
    _notch_rect(draw, (20, 120, 200, 180), 12, fill=(20, 30, 26, 255),
                outline=(255, 255, 255, 255), width=2)
    out = tmp_path / "card.png"
    image.save(out)
    assert out.stat().st_size > 500


def test_fullsystem_stays_pinned():
    package = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                               version="5.0.0", allow_draft=True)
    assert package.manifest["version"] == "5.0.0"
