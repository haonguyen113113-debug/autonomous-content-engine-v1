"""Executor overlay: vẽ overlay theo role preset cố định, chỉ từ graph["overlays"].

Test in-memory, mock hàm vẽ overlay (_apply_overlays), không render video dài.
"""

from __future__ import annotations

import pytest


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


def _overlay_list() -> list[dict]:
    return [
        {"type": "lower_third", "text": "Tin tuc",
         "start_seconds": 0.0, "end_seconds": 9.0},
        {"type": "caption", "text": "Hook mo dau",
         "start_seconds": 0.0, "end_seconds": 5.0, "role": "hook"},
    ]


def _capture_apply(monkeypatch: pytest.MonkeyPatch):
    """Mock hàm vẽ overlay, ghi lại cac lan goi."""
    calls: list = []

    def fake_apply(image, overlays, width, height):
        calls.append((list(overlays), int(width), int(height)))

    monkeypatch.setattr("apps.scene_graph.executor._apply_overlays", fake_apply)
    return calls


def test_executor_draws_overlays_from_graph_spec(monkeypatch):
    from apps.scene_graph.executor import render_scene_graph
    from apps.scene_graph.schema import validate_scene_graph

    graph = _starter_graph(overlays=_overlay_list())
    validate_scene_graph(graph)
    assert graph["overlays"] == _overlay_list()

    calls = _capture_apply(monkeypatch)
    image = render_scene_graph(graph)

    assert image is not None
    assert image.size == (graph["canvas"]["width"], graph["canvas"]["height"])
    # Ham vẽ overlay duoc goi dung 1 lan voi spec chinh la graph["overlays"].
    assert len(calls) == 1
    assert calls[0][0] == graph["overlays"]
    assert calls[0][1] == graph["canvas"]["width"]
    assert calls[0][2] == graph["canvas"]["height"]


def test_executor_without_overlays_still_renders(monkeypatch):
    from apps.scene_graph.executor import render_scene_graph
    from apps.scene_graph.schema import validate_scene_graph

    graph = _starter_graph()  # overlays = None
    validate_scene_graph(graph)
    assert graph["overlays"] is None

    calls = _capture_apply(monkeypatch)
    image = render_scene_graph(graph)

    # Khong goi ham vẽ overlay, anh van render binh thuong.
    assert calls == []
    assert image.size == (1080, 1920)


def test_collect_overlays_top_level_first_params_fallback():
    from apps.scene_graph.executor import _collect_overlays

    top = [{"type": "lower_third", "text": "A", "start_seconds": 0.0,
            "end_seconds": 1.0}]
    params_ = [{"type": "caption", "text": "B", "start_seconds": 0.0,
                "end_seconds": 1.0}]

    # Top-level uu tien (params cu cung khong duoc lay).
    assert _collect_overlays(
        {"overlays": top, "params": {"overlays": params_}}
    ) == top
    # Fallback sang params khi top-level la None.
    assert _collect_overlays(
        {"overlays": None, "params": {"overlays": params_}}
    ) == params_
    # Khong co gi -> None.
    assert _collect_overlays({"overlays": None, "params": {}}) is None
    assert _collect_overlays({}) is None


def test_collect_overlays_ignores_segments_timeline():
    from apps.scene_graph.executor import _collect_overlays

    # Overlay o day duoc luu o segments (timeline), khong o top-level/params:
    # executor KHONG duoc doc we do de suy ra overlay.
    checked = {
        "overlays": None,
        "params": None,
        "segments": {
            "beat-1": [
                {"text": "overlay-only-in-timeline", "accent": False},
            ],
        },
    }
    assert _collect_overlays(checked) is None


def test_executor_reads_graph_overlays_not_timeline(monkeypatch):
    from apps.scene_graph.executor import render_scene_graph
    from apps.scene_graph.schema import validate_scene_graph

    base = _starter_graph()  # khong co overlays o top-level/params
    design = base["design"]
    provenance = dict(base.get("provenance") or {})
    provenance.pop("graph_hash", None)  # ta se bo sung segments -> hash cu khong con dung

    graph = dict(base)
    graph["provenance"] = provenance
    graph["segments"] = {
        "beat-ov-1": [{"text": "overlay-only-in-timeline", "accent": False}],
    }
    validate_scene_graph(graph)
    assert graph["overlays"] is None

    calls = _capture_apply(monkeypatch)
    image = render_scene_graph(graph)

    # Khong doc timeline de suy ra overlay -> khong goi ham vẽ.
    assert calls == []
    assert image.size == (1080, 1920)


def test_overlay_role_resolution_priority():
    from apps.scene_graph.executor import _role_of

    assert _role_of({"role": "hook", "type": "caption"}) == "hook"
    assert _role_of({"type": "lower_third"}) == "lower_third"
    assert _role_of({"type": "caption"}) == "caption"
    assert _role_of({"kind": "hook"}) == "hook"
    with pytest.raises(ValueError, match="thiếu role/type/kind"):
        _role_of({})


def test_unknown_overlay_role_fails_scene_graph_validation():
    from apps.scene_graph.schema import validate_scene_graph

    graph = _starter_graph(overlays=[
        {"type": "lower_third", "text": "Banner",
         "start_seconds": 0.0, "end_seconds": 5.0, "role": "khong_ho_tro"},
    ])
    with pytest.raises(ValueError, match="not supported"):
        validate_scene_graph(graph)


def test_overlay_missing_text_raises_value_error(monkeypatch):
    from apps.scene_graph.executor import render_scene_graph
    from PIL import Image
    from apps.scene_graph.executor import _draw_overlay

    image = Image.new("RGB", (1920, 1080))
    with pytest.raises(ValueError, match="thiếu văn bản"):
        _draw_overlay(image, {"type": "caption", "text": "   "}, 1920, 1080)


def test_executor_accepts_clip_relative_overlay_on_nonzero_beat(monkeypatch):
    """Overlay clip-relative [1,4] tren beat [9,18] duoc executor nhan chinh xuat,
    khong bi bo khoi hoac tu choi vi nham thoi gian tuyet doi voi timing.start."""
    from apps.scene_graph.executor import render_scene_graph
    from apps.scene_graph.schema import validate_scene_graph

    graph = _starter_graph(index=1, overlays=[
        {"type": "caption", "text": "Noi dung chen",
         "start_seconds": 1.0, "end_seconds": 4.0, "role": "hook"}
    ])
    # Timing co start > 0: bo graph_hash cu (se thay doi) va dat lai timing beat.
    provenance = dict(graph.get("provenance") or {})
    provenance.pop("graph_hash", None)
    graph = dict(graph)
    graph["provenance"] = provenance
    graph["timing"] = {"start": 9.0, "end": 18.0}
    validate_scene_graph(graph)
    assert graph["timing"]["start"] == 9.0 and graph["timing"]["end"] == 18.0
    assert graph["overlays"][0]["start_seconds"] == 1.0
    assert graph["overlays"][0]["end_seconds"] == 4.0

    calls = _capture_apply(monkeypatch)
    image = render_scene_graph(graph)

    assert image is not None
    assert image.size == (graph["canvas"]["width"], graph["canvas"]["height"])
    # Executor lay overlay chinh xuat tu graph["overlays"], khong bien doi
    # thoi gian clip-relative thanh absolute va khong tu choi overlay.
    assert len(calls) == 1
    assert calls[0][0] == graph["overlays"]
    assert calls[0][0][0]["start_seconds"] == 1.0
    assert calls[0][0][0]["end_seconds"] == 4.0
    assert calls[0][1] == graph["canvas"]["width"]
    assert calls[0][2] == graph["canvas"]["height"]
