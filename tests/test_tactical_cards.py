"""Renderer hook for authored Sprint 2 tactical plates (long-form)."""

from pathlib import Path

import pytest

from apps.card_selector import select_cards
from apps.video_renderer import _write_starter_scene


def _seg(narration, mode="tactical_explainer", data=None, **extra):
    segment = {"id": extra.pop("id", "beat-x"), "narration": narration,
               "visual": extra.pop("visual", ""), "visual_mode": mode,
               "graphic_data": data or {}, "duration_seconds": 6}
    segment.update(extra)
    return segment


def test_starter_scene_renders_sprint2_plates(tmp_path):
    from PIL import Image

    for card in ("TA-04", "TA-08"):
        out = tmp_path / f"{card}.png"
        _write_starter_scene(out, card)
        with Image.open(out) as image:
            assert image.size == (1920, 1080)
        assert out.stat().st_size > 10_000


def test_starter_scene_rejects_unknown_ids(tmp_path):
    for bad in ("nope-missing", "C-07", "TA-99", "", "../evil"):
        with pytest.raises(ValueError):
            _write_starter_scene(tmp_path / "x.png", bad)


def test_selector_sets_tactical_card_for_long_pressing():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Cau hoi chien thuat"}, id="beat-1"),
        _seg("Doi hinh pressing tam cao", mode="tactical_explainer", id="beat-2"),
    ], content_type="long")
    second = out["decisions"][1]
    assert second["starter_id"] == "TA-06"
    assert second["graphic_data"]["tactical_card"] == "TA-06"


def test_selector_sets_no_tactical_card_for_short():
    out = select_cards([
        _seg("So do chien thuat", mode="tactical_explainer", id="beat-1"),
    ], content_type="short")
    for decision in out["decisions"]:
        assert "tactical_card" not in decision["graphic_data"]


def test_selector_sets_no_tactical_card_for_chart_modes():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Cau hoi chien thuat"}, id="beat-1"),
        _seg("Bang chung so", mode="chart_comparison",
             data={"values": [{"label": "X", "value": 3}]}, id="beat-2"),
    ], content_type="long")
    second = out["decisions"][1]
    assert second["starter_id"] == "TA-16"
    assert "tactical_card" not in second["graphic_data"]
