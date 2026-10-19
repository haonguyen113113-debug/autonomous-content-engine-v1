"""CC0 kit sprites: floodlight flares, glow, smoke wired into night plates."""

from pathlib import Path

from PIL import Image

from apps.video_renderer import _kit, _sprite

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "template_foundation/templates/allen-knows-ball/12.0.0/resources/kit"


def test_kit_ships_complete():
    for name in ("flare_01.png", "light_02.png", "magic_01.png",
                 "smoke_03.png", "spark_04.png", "star_05.png"):
        path = KIT / name
        assert path.is_file(), name
        with Image.open(path) as sprite:
            assert sprite.size[0] >= 64


def test_sprite_tints_and_skips_missing(tmp_path):
    from PIL import ImageStat
    image = Image.new("RGBA", (200, 200), (10, 15, 13, 255))
    assert _sprite(image, KIT / "flare_01.png", (100, 100), 120, (255, 179, 0), 190) is True
    before = ImageStat.Stat(image).sum
    assert _sprite(image, KIT / "nope.png", (100, 100), 120) is False
    assert ImageStat.Stat(image).sum == before


def test_kit_resolves_beside_fonts():
    from template_foundation import resolve_template
    package = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                               version="12.0.0", allow_draft=True)
    font = package.root / "resources/fonts/BeVietnamPro-Bold.ttf"
    assert _kit("flare_01.png", font).is_file()
