"""In-memory contract tests for scene graph overlays (không đụng runtime).

Contract overlay đã chốt (top-level graph + mirror primitive params):
    {
        "type": "lower_third" | "caption",   # required
        "text": str,                          # required, non-empty
        "start_seconds": float,               # required, >= 0, clip-relative
        "end_seconds": float,                 # required, > start_seconds
        "role": str                           # optional preset role
    }
Validator: type được hỗ trợ; text str không rỗng; start_seconds >= 0;
end_seconds > start_seconds; start_seconds/end_seconds không vượt
beat_duration = timing.end - timing.start (clip-relative so với đầu beat,
0 = đầu beat). Hash (_hash_payload) đã bao phủ toàn bộ graph trừ
graph_hash → overlays tự động được bao phủ; không sửa _hash_payload.
Legacy graph không có khóa "overlays" vẫn validate bình thường.
"""

from __future__ import annotations

import copy

import pytest

from apps.scene_graph.builder import build_scene_graph
from apps.scene_graph.schema import graph_hash, validate_scene_graph


def _overlay(type_="lower_third", text="Cao *Etihad* 19:30", start=1.0, end=4.0,
             role=None):
    item = {
        "type": type_,
        "text": text,
        "start_seconds": start,
        "end_seconds": end,
    }
    if role is not None:
        item["role"] = role
    return item


def _build(overlays=None, graph_start=0.0, graph_end=10.0):
    return build_scene_graph(
        segment_id="beat-1",
        visual_mode="media_b_roll",
        starter_id=None,
        graphic_data={},
        evidence=[],
        content_type="short",
        start_seconds=graph_start,
        end_seconds=graph_end,
        index=0,
        overlays=overlays,
    )


def test_valid_overlay_emits_field_and_params_mirror():
    ov = _overlay()
    graph = _build(overlays=[ov])
    validate_scene_graph(graph)
    assert graph["overlays"] == [ov]
    # Mirror vào params cho primitive graph (top-level first, params fallback).
    assert graph["params"]["overlays"] == [ov]


def test_valid_caption_overlay():
    graph = _build(
        overlays=[_overlay(type_="caption", text="Ngoại hạng Anh", role="hook")]
    )
    validate_scene_graph(graph)
    assert graph["overlays"][0]["role"] == "hook"


def test_hash_covers_overlay_tamper_mismatch():
    graph = _build(overlays=[_overlay()])
    recorded = graph["provenance"]["graph_hash"]
    assert graph_hash(graph) == recorded
    # Tamper overlay -> hash thay đổi và validator chối graph đã bị chỉnh sửa.
    tampered = copy.deepcopy(graph)
    tampered["overlays"][0]["text"] = "da doi sai"
    assert graph_hash(tampered) != recorded
    with pytest.raises(ValueError, match="graph_hash mismatch"):
        validate_scene_graph(tampered)


def test_unsupported_overlay_type_raises():
    with pytest.raises(ValueError, match="type"):
        validate_scene_graph(
            _build(overlays=[_overlay(type_="banner", text="x", start=1.0, end=2.0)])
        )


def test_overlay_text_missing_or_empty_raises():
    # Thiếu khóa text.
    with pytest.raises(ValueError, match="text"):
        validate_scene_graph(
            _build(overlays=[{"type": "caption", "start_seconds": 1.0, "end_seconds": 2.0}])
        )
    # text rỗng.
    with pytest.raises(ValueError, match="text"):
        validate_scene_graph(_build(overlays=[_overlay(text="")]))
    # text chỉ whitespace cũng coi là rỗng.
    with pytest.raises(ValueError, match="text"):
        validate_scene_graph(_build(overlays=[_overlay(text="   ")]))


def test_overlay_negative_start_raises():
    with pytest.raises(ValueError, match="start_seconds"):
        validate_scene_graph(_build(overlays=[_overlay(start=-0.5, end=2.0)]))


def test_overlay_start_ge_end_raises():
    with pytest.raises(ValueError, match="end_seconds"):
        validate_scene_graph(_build(overlays=[_overlay(start=3.0, end=3.0)]))
    with pytest.raises(ValueError, match="end_seconds"):
        validate_scene_graph(_build(overlays=[_overlay(start=5.0, end=2.0)]))


def test_overlay_role_must_be_string():
    with pytest.raises(ValueError, match="role"):
        validate_scene_graph(_build(overlays=[_overlay(role=123)]))


def test_overlay_role_must_be_supported_for_type():
    with pytest.raises(ValueError, match="not supported"):
        validate_scene_graph(_build(overlays=[_overlay(type_="caption", role="name_tag")]))


@pytest.mark.parametrize("key, value", [
    ("x", 120),
    ("font_size", 48),
    ("color", "#fff"),
    ("motion", "slide"),
])
def test_overlay_rejects_uncontracted_layout_or_style_keys(key, value):
    overlay = _overlay()
    overlay[key] = value
    with pytest.raises(ValueError, match="unsupported keys"):
        validate_scene_graph(_build(overlays=[overlay]))


def test_overlay_outside_beat_timing_raises():
    # Kết thúc vượt cửa sổ beat [0, 5] (duration 5): end=6 > 5.
    with pytest.raises(ValueError, match="ends after"):
        validate_scene_graph(_build(overlays=[_overlay(start=4.0, end=6.0)],
                                      graph_end=5.0))
    # Clip-relative [4, 6] trên beat [5, 10] (duration 5): end=6 > 5.
    with pytest.raises(ValueError, match="ends after"):
        validate_scene_graph(_build(overlays=[_overlay(start=4.0, end=6.0)],
                                      graph_start=5.0, graph_end=10.0))
    # start_seconds âm vi phạm cả clip-relative >= 0.
    with pytest.raises(ValueError, match="start_seconds"):
        validate_scene_graph(_build(overlays=[_overlay(start=-1.0, end=2.0)]))


def test_overlay_clip_relative_passes_with_nonzero_beat_start():
    # Beat [9.0, 18.0] (duration 9), overlay clip-relative [1.0, 4.0]
    # -> HỢP LỆ: không bị chối vì "starts before timing.start" (timebase
    # tuyệt đối); 1.0 <= 9 và 4.0 <= 9.
    graph = _build(overlays=[_overlay(start=1.0, end=4.0)],
                   graph_start=9.0, graph_end=18.0)
    validate_scene_graph(graph)
    assert graph["overlays"][0]["start_seconds"] == 1.0


def test_overlay_within_beat_timing_valid():
    # Giọt cửa sổ [0, 10] là hợp lệ (khả dụng cả hai đầu).
    for ov in (_overlay(start=0.0, end=2.0), _overlay(start=2.0, end=10.0),
               _overlay(start=0.0, end=10.0)):
        graph = _build(overlays=[ov])
        validate_scene_graph(graph)


def test_empty_overlays_list_validates():
    graph = _build(overlays=[])
    validate_scene_graph(graph)
    assert graph["overlays"] == []


def test_legacy_graph_without_overlays_validates():
    graph = _build(overlays=None)
    validate_scene_graph(graph)
    assert graph["overlays"] is None
    # Legacy graph chắc chắn không có khóa "overlays" -> vẫn validate.
    legacy = copy.deepcopy(graph)
    legacy.pop("overlays", None)
    legacy["provenance"] = {
        k: v for k, v in legacy["provenance"].items() if k != "graph_hash"
    }
    validate_scene_graph(legacy)


def test_hash_stable_same_input():
    overlays = [
        _overlay(),
        _overlay(type_="caption", text="second", start=5.0, end=7.0, role="hook"),
    ]
    first = graph_hash(_build(overlays=overlays))
    second = graph_hash(_build(overlays=copy.deepcopy(overlays)))
    assert first == second
