from apps.video_renderer import _beat_fades, _overlay_items


def _event(item_id, item_type, start, end, enter="cut", exit="cut"):
    return {"item_id": item_id, "item_type": item_type,
            "start_seconds": start, "end_seconds": end,
            "enter": enter, "exit": exit,
            "transition_in": "clean_cut", "effect": "none",
            "text": "sample", "evidence_ref": None}


def test_beat_fades_from_overlapping_events():
    events = [_event("a", "caption", 0, 3, enter="fade"),
              _event("b", "caption", 5, 8, exit="fade")]
    assert _beat_fades(events, 0, 10) == (True, True)
    assert _beat_fades(events, 0, 4) == (True, False)
    assert _beat_fades(events, 4, 10) == (False, True)


def test_beat_fades_ignores_outside_and_broken_events():
    events = [_event("a", "caption", 20, 25, enter="fade", exit="fade"),
              {"item_type": "caption"},
              "not-a-dict",
              _event("b", "caption", 0, 2, enter="slide", exit="wipe")]
    assert _beat_fades(events, 0, 10) == (False, False)


def test_overlay_items_select_kinds_windows_and_limit():
    events = [
        _event("cap-1", "caption", 1, 3),
        _event("stat-1", "stat_card", 1, 3),
        _event("lt-1", "lower_third", 4, 6),
        _event("cap-2", "caption", 30, 35),
        _event("lt-2", "lower_third", 2, 9),
    ]
    picked = _overlay_items(events, 0, 10)
    assert [item["item_id"] for item in picked] == ["cap-1", "lt-2", "lt-1"]
    assert _overlay_items(events, 0, 10, limit=2)[0]["item_id"] == "cap-1"
    assert _overlay_items(events, 0, 10, kinds=("caption",))[0]["item_id"] == "cap-1"
    assert _overlay_items(events, 20, 30) == []
