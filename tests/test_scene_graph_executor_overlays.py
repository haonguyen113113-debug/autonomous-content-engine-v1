"""Scene Graph executor keeps free-standing text outside the rendered card."""

from __future__ import annotations

from PIL import ImageChops


def _starter_graph(*, overlays=None, index: int = 0):
    from apps.scene_graph.builder import build_scene_graph

    return build_scene_graph(
        segment_id=f"beat-ov-{index + 1}",
        visual_mode="hook_card",
        starter_id="C-03",
        graphic_data={"hook_text": "Dem ac mong *Etihad*"},
        evidence=["ESPN 14/10/2026"],
        content_type="short",
        start_seconds=0.0,
        end_seconds=9.0,
        index=index,
        overlays=overlays,
    )


def test_executor_does_not_paint_unbound_overlays():
    from apps.scene_graph.executor import render_scene_graph
    from apps.scene_graph.schema import validate_scene_graph

    overlays = [
        {"type": "lower_third", "text": "Tin tuc",
         "start_seconds": 0.0, "end_seconds": 9.0},
        {"type": "caption", "text": "Hook mo dau",
         "start_seconds": 0.0, "end_seconds": 5.0, "role": "hook"},
    ]
    graph = _starter_graph(overlays=overlays)
    base = _starter_graph()
    validate_scene_graph(graph)

    rendered = render_scene_graph(graph)
    without_free_text = render_scene_graph(base)
    assert rendered.size == (1080, 1920)
    assert ImageChops.difference(rendered.convert("RGB"),
                                 without_free_text.convert("RGB")).getbbox() is None


def test_unknown_overlay_role_still_fails_graph_validation():
    import pytest
    from apps.scene_graph.schema import validate_scene_graph

    graph = _starter_graph(overlays=[
        {"type": "lower_third", "text": "Banner",
         "start_seconds": 0.0, "end_seconds": 5.0, "role": "khong_ho_tro"},
    ])
    with pytest.raises(ValueError, match="not supported"):
        validate_scene_graph(graph)
