"""Design-system unit tests: roles, breaks, contrast (not effects)."""

from apps.video_renderer import (
    U,
    _contrast_ratio,
    _ensure_contrast,
    _phrase_lines,
    _role_size,
)


def test_three_roles_ordered():
    boss, support, whisper = (_role_size(1250, role) for role in ("boss", "support", "whisper"))
    assert boss > support > whisper > 0
    assert U == 12


def test_phrase_breaks_respect_slash_and_orphans():
    assert _phrase_lines("Hàng thủ sập đổ / tối nay") == ["Hàng thủ sập đổ", "tối nay"]
    lines = _phrase_lines("Việt Nam tranh hạng Ba với Malaysia tối nay")
    assert 1 <= len(lines) <= 3
    assert " ".join(lines) == "Việt Nam tranh hạng Ba với Malaysia tối nay"
    assert _phrase_lines("") == []


def test_contrast_math():
    assert _contrast_ratio((255, 255, 255), (0, 0, 0)) > 20
    assert _contrast_ratio((120, 120, 120), (120, 120, 120)) == 1.0


def test_ensure_contrast_scrims_only_when_needed():
    from PIL import Image, ImageDraw
    bright = Image.new("RGBA", (200, 100), (240, 240, 235, 255))
    assert _ensure_contrast(ImageDraw.Draw(bright), bright, (50, 30, 150, 70), (20, 20, 20, 255)) is False
    pale = Image.new("RGBA", (200, 100), (235, 230, 220, 255))
    assert _ensure_contrast(ImageDraw.Draw(pale), pale, (50, 30, 150, 70), (240, 240, 235, 255)) is True
