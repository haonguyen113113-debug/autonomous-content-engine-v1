import wave

import pytest

from apps.video_renderer import (
    _beat_fades, _beat_zoom_expr, _ensure_voice_fits_script, _overlay_items,
)


def _write_silent_wav(path, seconds, rate=22050):
    frames = int(seconds * rate)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * frames)


def test_voice_fit_gate_blocks_overlong_narration(tmp_path):
    voice_dir = tmp_path / "runtime/voice"
    voice_dir.mkdir(parents=True)
    _write_silent_wav(voice_dir / "long.wav", seconds=60)
    _write_silent_wav(voice_dir / "fine.wav", seconds=45)
    base = {"draft": {"duration_target_seconds": 40}}
    with pytest.raises(ValueError, match="60s.*40s"):
        _ensure_voice_fits_script(
            tmp_path, {**base, "voice_preview": {"path": "long.wav"}})
    _ensure_voice_fits_script(
        tmp_path, {**base, "voice_preview": {"path": "fine.wav"}})
    with pytest.raises(ValueError, match="Generate and audit"):
        _ensure_voice_fits_script(
            tmp_path, {**base, "voice_preview": {"path": "missing.wav"}})


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


# --- per-beat camera drift: `on` counts the whole video ------------------------


def test_beat_zoom_expression_offsets_by_the_beat_start():
    """A beat that starts late must not enter with its drift saturated.

    All plates are fed from t=0 and advanced every frame, so zoompan's `on`
    is a video-wide frame count. Without the offset, beat 2 (7 s -> frame 210)
    starts at zoom 1.004 and hits the 1.0 floor 1.3 s later, freezing its
    plate for the rest of the beat (measured on the R4 gate MP4).
    """
    first = _beat_zoom_expr(1, start=0.0, fps=30, punch=False)
    second = _beat_zoom_expr(1, start=7.0, fps=30, punch=False)
    third = _beat_zoom_expr(2, start=14.0, fps=30, punch=False)

    assert first == "max(1.0,1.025-0.0001*on)"
    assert second == "max(1.0,1.025-0.0001*max(0,on-210))"
    assert third == "min(1.025,1+0.0001*max(0,on-420))"


def test_beat_zoom_expression_keeps_punch_and_media_rates():
    punch = _beat_zoom_expr(0, start=4.0, fps=30, punch=True, end=11.0)
    media = _beat_zoom_expr(0, start=4.0, fps=30, punch=False, media=True)
    assert punch.startswith("min(1.035,1+0.02*min(1,max(0,on-120)/12)")
    assert "max(0,on-120)" in punch
    assert media == "min(1.035,1+0.00002*max(0,on-120))"


def test_punch_ramp_reaches_the_ceiling_at_the_end_of_the_beat():
    """A punch beat must keep drifting for the whole beat, not freeze at 3.3 s.

    The old single-rate ramp hit 1.035 after 100 frames and left the plate
    pixel-identical for the remaining 3.3 s (freezedetect: 3.30-6.60 s).
    """
    expr = _beat_zoom_expr(0, start=0.0, fps=30, punch=True, end=7.0)
    # 0.02 snap over 12 frames + drift over the remaining 198 frames = 1.035.
    drift = float(expr.split("+0.02*min(1,on/12)+")[1].split("*max(0,on-12))")[0])
    assert abs(1.0 + 0.02 + drift * 198 - 1.035) < 0.001
    assert drift * 100 > 0.003  # still visibly moving late in the beat
