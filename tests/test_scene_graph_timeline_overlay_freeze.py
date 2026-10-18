"""In-memory contract tests: segment.timeline_events -> graph.overlays
(trình freeze overlay/caption).

Contract da chot (KHONG duoc doi):
  - segment.timeline_events[].start_seconds/end_seconds: tuyet doi (tinh tu dau video).
  - segment.start_seconds/end_seconds: tuyet doi (tinh tu dau video).
  - graph.overlays[].start_seconds/end_seconds: beat-relative (0 = dau beat).
  - Chi item_type trong {caption, lower_third} duoc chuyen sang overlay;
    stat_card / media / chapter_card / source_card BO QUA.
  - Overlay phai co text non-empty, start_seconds >= 0,
    end_seconds > start_seconds, end_seconds <= beat_duration.

Chay: python -m pytest tests/test_scene_graph_timeline_overlay_freeze.py -q
KHONG doc/ghi/sua runtime/. KHONG commit/push. KHONG sua builder.py/pipeline.py.
"""

from __future__ import annotations

import copy

import pytest

from apps.scene_graph.builder import build_clip_graphs
from apps.scene_graph.schema import graph_hash, validate_scene_graph


def _event_overlay(item_type="lower_third", text="Noi dung chen",
                   start_seconds=0.0, end_seconds=5.0):
    """Timeline event có thời gian tuyệt đối tính từ đầu video."""
    return {
        "item_type": item_type,
        "text": text,
        "start_seconds": float(start_seconds),
        "end_seconds": float(end_seconds),
    }


def _explicit_overlay(overlay_type="caption", text="Noi dung chen",
                      start_seconds=0.0, end_seconds=5.0):
    """Overlay tường minh đã dùng timebase beat-relative."""
    return {
        "type": overlay_type,
        "text": text,
        "start_seconds": float(start_seconds),
        "end_seconds": float(end_seconds),
    }


def _build(segment_start=0.0, segment_end=5.0, overlays=None,
           timeline_events=None):
    """Build through the production clip path so segment events are frozen."""
    segment = {
        "id": "beat-1",
        "start_seconds": segment_start,
        "end_seconds": segment_end,
    }
    if timeline_events is not None:
        segment["timeline_events"] = timeline_events
    if overlays is not None:
        segment["overlays"] = overlays
    return build_clip_graphs(
        [{
            "segment_id": "beat-1",
            "index": 0,
            "visual_mode": "media_b_roll",
            "starter_id": None,
            "graphic_data": {},
            "evidence": [],
        }],
        segments_by_id={"beat-1": segment},
        content_type="short",
    )[0]


def test_timeline_event_to_overlay_relative_offset():
    # Segment [9.0, 14.0], event [11.0, 14.0] (tuyet doi).
    # Du kien overlay beat-relative: [11-9, 14-9] = [2.0, 5.0].
    graph = _build(
        segment_start=9.0, segment_end=14.0,
        timeline_events=[_event_overlay(item_type="lower_third", text="Lich dau tiep",
                                        start_seconds=11.0, end_seconds=14.0)],
    )
    overlays = graph.get("overlays") or []
    assert len(overlays) == 1
    assert overlays[0]["type"] == "lower_third"
    assert overlays[0]["text"] == "Lich dau tiep"
    assert overlays[0]["start_seconds"] == 2.0  # event_start - segment_start
    assert overlays[0]["end_seconds"] == 5.0


def test_timeline_event_at_beat_start():
    # Event bat dau cung luc voi dau beat -> overlay start_seconds = 0.0.
    graph = _build(
        segment_start=9.0, segment_end=14.0,
        timeline_events=[_event_overlay(item_type="caption", text="Goc beat",
                                        start_seconds=9.0, end_seconds=12.0)],
    )
    overlays = graph.get("overlays") or []
    assert len(overlays) == 1
    assert overlays[0]["start_seconds"] == 0.0
    assert overlays[0]["end_seconds"] == 3.0


def test_timeline_event_ends_at_beat_duration():
    # Event ket thuc cung luc voi cuoi beat -> overlay end_seconds = beat_duration.
    graph = _build(
        segment_start=9.0, segment_end=14.0,
        timeline_events=[_event_overlay(item_type="caption", text="Dau cuoi",
                                        start_seconds=11.0, end_seconds=14.0)],
    )
    overlays = graph.get("overlays") or []
    assert len(overlays) == 1
    beat_duration = 14.0 - 9.0
    assert overlays[0]["start_seconds"] == 2.0
    assert overlays[0]["end_seconds"] == beat_duration == 5.0


def test_unsupported_event_type_not_converted():
    # item_type = stat_card khong duoc chuyen thanh overlay (khong xuat hien
    # trong graph.overlays).
    graph = _build(
        segment_start=9.0, segment_end=14.0,
        timeline_events=[_event_overlay(item_type="stat_card", text="So lieu",
                                        start_seconds=10.0, end_seconds=12.0)],
    )
    overlays = graph.get("overlays") or []
    types = [o.get("type") for o in overlays]
    assert "stat_card" not in types


def test_missing_text_or_bad_timing_not_silently_dropped():
    # Event thiếu text hoặc timing sai phải fail rõ ràng, không bị bỏ âm thầm.
    for event, message in (
        (_event_overlay(item_type="caption", text="", start_seconds=10.0, end_seconds=12.0),
         "text must be a non-empty string"),
        (_event_overlay(item_type="caption", text="X", start_seconds=12.0, end_seconds=10.0),
         "outside beat window"),
    ):
        with pytest.raises(ValueError, match=message):
            _build(segment_start=9.0, segment_end=14.0, timeline_events=[event])


def test_non_list_explicit_overlays_raise_clear_error():
    with pytest.raises(ValueError, match="overlays must be a list"):
        _build(segment_start=9.0, segment_end=14.0, overlays={"type": "caption"},
               timeline_events=[_event_overlay(item_type="caption", text="x",
                                                start_seconds=9.0, end_seconds=11.0)])


def test_explicit_overlay_and_timeline_event_precedence():
    # Segment co overlay ro rang cung voi timeline event caption trung lap:
    # explicit overlay uu tien, su kien khong bi nhan dopp.
    explicit = _explicit_overlay(overlay_type="caption", text="Trich dan",
                                 start_seconds=0.0, end_seconds=2.0)
    event_duplicate = _event_overlay(item_type="caption", text="Trich dan",
                                     start_seconds=9.0, end_seconds=11.0)
    graph = _build(
        segment_start=9.0, segment_end=14.0,
        overlays=[explicit], timeline_events=[event_duplicate],
    )
    overlays = graph.get("overlays") or []
    assert len(overlays) == 1
    assert overlays[0]["text"] == "Trich dan"
    assert overlays[0]["start_seconds"] == 0.0
    assert overlays[0]["end_seconds"] == 2.0


def test_hash_changes_when_overlay_tampered():
    # Them overlay vao graph, sau do tamper text -> graph_hash bi mat.
    graph = _build(
        segment_start=9.0, segment_end=14.0,
        overlays=[_explicit_overlay(overlay_type="lower_third", text="Goc goc",
                                    start_seconds=2.0, end_seconds=5.0)],
    )
    recorded = graph["provenance"]["graph_hash"]
    assert graph_hash(graph) == recorded
    tampered = copy.deepcopy(graph)
    tampered["overlays"][0]["text"] = "da doi sai"
    assert graph_hash(tampered) != recorded
    with pytest.raises(ValueError, match="graph_hash mismatch"):
        validate_scene_graph(tampered)
