"""Smoke test: short-form full render on the Scene Graph production path.

``tmp_path`` is the test root: run JSON, voice WAV, rendered MP4 and the render
report all live under ``tmp_path/runtime/`` (không chạm repo ``runtime/``).
The template package (fonts, design tokens, palette) is resolved from the real
released pack inside the repo via a monkeypatched ``resolve_template`` — chỉ
đọc template từ repo root, mọi GHI/I/O chạy dưới ``tmp_path``.

Production path exercised:
  render_full_run -> apply_card_plan -> build_run_scene_graphs
  (ACE_SCENE_GRAPH_RENDER=1) -> _render (FFmpeg libx264/yuv420p 1080x1920@30,
  20s story + fixed 4s ending card -> ffprobe metadata.

No user runtime/, voice or library assets are touched; the voice is a
synthesized silent WAV. The smoke checks the fixed pack opening/ending scenes
and confirms free-standing overlay copy is not painted.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import wave
from fractions import Fraction
from pathlib import Path

import pytest

from apps.video_renderer import render_full_run

REPO_ROOT = Path(__file__).resolve().parent.parent

HEX64 = re.compile(r"^[0-9a-f]{64}$")

FIXTURE_RUN = {
    "run_id": "a1b2c3d4e5f6",
    "script_owner_approved": True,
    "voice_preview_audited": True,
    "voice_preview": {"path": "preview.wav"},
    "status": "READY_TO_RENDER",
    "draft": {
        "content_type": "short",
        "template_version": "12.0.0",
        "duration_target_seconds": 20,
        "segments": [
            {
                "id": "beat-1",
                "start_seconds": 0,
                "end_seconds": 10,
                "visual_mode": "tactical_explainer",
                "graphic_data": {},
                "overlays": [
                    {"type": "caption", "text": "Xin chào Việt Nam",
                     "start_seconds": 2.0, "end_seconds": 5.0, "role": "hook"}
                ],
                "beat_intent": {
                    "image_goal": "establish_moment",
                    "focus_subject": "opening",
                    "evidence_type": "sourced_stat",
                    "emphasis_level": "hero",
                },
                "evidence_refs": ["ESPN 14/10/2026"],
            },
            {
                "id": "beat-2",
                "start_seconds": 10,
                "end_seconds": 20,
                "visual_mode": "score_card",
                "graphic_data": {
                    "home": "Manchester City",
                    "away": "Paris Saint-Germain",
                    "score": "1-0",
                },
                "overlays": [
                    {"type": "lower_third", "text": "Bối cảnh trận đấu",
                     "start_seconds": 2.0, "end_seconds": 5.0, "role": "name_tag"}
                ],
                "beat_intent": {
                    "image_goal": "show_evidence",
                    "focus_subject": "b-roll",
                    "evidence_type": "none",
                    "emphasis_level": "quiet",
                },
                "evidence_refs": [],
            },
        ],
    },
    "card_plan": {
        "decisions": [
            {"segment_id": "beat-1", "index": 0, "visual_mode": "hook_card",
             "starter_id": None, "media_asset_id": None, "graphic_data": {}},
            {"segment_id": "beat-2", "index": 1, "visual_mode": "score_card",
             "starter_id": None, "media_asset_id": None, "graphic_data": {}},
        ],
    },
}


def _write_silent_wav(path: Path, seconds: float = 1.0, rate: int = 44100) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * int(rate * seconds))


def test_scene_graph_short_render_smoke(tmp_path, monkeypatch):
    # 1. cờ điều khiển (chỉ trong thời gian chạy test qua monkeypatch)
    monkeypatch.setenv("ACE_SCENE_GRAPH_RENDER", "1")
    monkeypatch.setenv("SOUNDPACK_ENABLED", "false")

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("FFmpeg/ffprobe không có sẵn trên PATH; bỏ qua test render thật.")

    run_id = FIXTURE_RUN["run_id"]
    run = json.loads(json.dumps(FIXTURE_RUN))  # deep copy, không tác động original

    # 2. file WAV thật (1 giây im lặng, 1 channel/16-bit/44100 Hz) dưới tmp_path
    # WAV dài bằng duration_target_seconds (20s) để FFmpeg không cắt output
    # theo stream âm thanh ngắn nhất. Vẫn vượt qua _ensure_voice_fits_script
    # (20s <= 20 * 1.25 = 25s).
    voice_dir = tmp_path / "runtime" / "voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    _write_silent_wav(voice_dir / "preview.wav", seconds=20.0)

    # run JSON dưới tmp_path/runtime/runs (không đục runtime/ của repo)
    runs_dir = tmp_path / "runtime" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / f"{run_id}.json").write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")

    # 3. resolve_template trả package thật từ repo root; GỮ root=tmp_path cho I/O
    import template_foundation as _template_foundation
    import apps.video_renderer as _renderer_module

    def _resolve_template(root, template_id, version=None, *, allow_draft=False):
        return _template_foundation.resolve_template(
            REPO_ROOT, template_id, version=version, allow_draft=allow_draft
        )

    monkeypatch.setattr(_renderer_module, "resolve_template", _resolve_template)

    # 4. render thật qua đường production
    result = render_full_run(tmp_path, run_id)
    assert result["rendered"] is True

    mp4 = tmp_path / "runtime" / "renders" / run_id / "full-render.mp4"
    assert mp4.is_file() and mp4.stat().st_size > 0

    # 5. ffprobe metadata (giống cách _render tự tra cứu)
    probe = subprocess.run(
        [ffprobe, "-v", "error",
         "-show_entries", "format=duration,size:stream=codec_name,width,height,codec_type,r_frame_rate,avg_frame_rate",
         "-of", "json", str(mp4)],
        capture_output=True, text=True, timeout=60,
    )
    assert probe.returncode == 0, probe.stderr
    metadata = json.loads(probe.stdout)
    video_streams = [s for s in metadata.get("streams", []) if s.get("codec_type") == "video"]
    assert video_streams, "rendered MP4 không có video stream"
    vs = video_streams[0]
    assert vs.get("codec_name") == "h264", vs
    assert vs.get("width") == 1080, vs
    assert vs.get("height") == 1920, vs
    fps = float(Fraction(vs.get("avg_frame_rate", "0/1")))
    assert abs(fps - 30.0) <= 0.1, vs
    duration = float(metadata.get("format", {}).get("duration", 0) or 0)
    assert abs(duration - 24) <= max(1.0, 24 * 0.01), duration

    # Decode raw RGB frames so the comparison tests pixels, not PNG metadata.
    def _frame_bytes(stamp: str) -> bytes:
        decoded = subprocess.run(
            [ffmpeg, "-v", "error", "-ss", stamp, "-i", str(mp4),
             "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
            capture_output=True, timeout=60,
        )
        assert decoded.returncode == 0, decoded.stderr.decode(errors="replace")
        assert len(decoded.stdout) == 1080 * 1920 * 3, len(decoded.stdout)
        return decoded.stdout

    # 6. Confirm the fixed opening gives way to the first beat, then compare
    #    two points inside that SAME beat to verify bounded card motion.
    opening_frame = _frame_bytes("0.8")
    first_beat_frame = _frame_bytes("1.5")
    assert opening_frame != first_beat_frame, "fixed opening card was not replaced by the body scene"
    frame_3 = _frame_bytes("3.0")
    frame_8 = _frame_bytes("8.0")
    assert frame_3 != frame_8, "same-beat frames are identical; plate may be frozen"
    before_ending = _frame_bytes("19.0")
    ending_frame = _frame_bytes("22.0")
    assert before_ending != ending_frame, "fixed template ending card was not shown"

    # 7. Fixed brand scenes are built from the template pack and free-standing
    #    copy is suppressed; ensure both rendered plates are present.
    work_dir = tmp_path / "runtime" / "renders" / run_id / "work"
    opening = work_dir / "opening-scene.png"
    ending = work_dir / "ending-scene.png"
    assert opening.is_file() and opening.stat().st_size > 0
    assert ending.is_file() and ending.stat().st_size > 0

    # 8. scene graphs đóng băng gắn vào run (đọc lại từ disk vì render_full_run
    #    ghi run JSON sau khi render)
    stored_run = json.loads((runs_dir / f"{run_id}.json").read_text(encoding="utf-8"))
    graphs = stored_run.get("draft", {}).get("scene_graphs")
    assert isinstance(graphs, list) and len(graphs) == 2, graphs
    for graph, (beat_start, beat_end) in zip(graphs, [(0, 10), (10, 20)]):
        assert isinstance(graph.get("overlays"), list) and graph["overlays"], graph
        beat_duration = float(graph["timing"]["end"]) - float(graph["timing"]["start"])
        assert abs(beat_duration - (beat_end - beat_start)) < 1e-9, graph
        for overlay in graph["overlays"]:
            assert isinstance(overlay, dict), overlay
            os_ = float(overlay["start_seconds"])
            oe = float(overlay["end_seconds"])
            assert 0.0 <= os_ < oe <= beat_duration + 1e-9, (overlay, beat_duration)
        assert HEX64.match(str(graph.get("provenance", {}).get("graph_hash", ""))), graph

    # 9. QA fails closed: overlays without a template-slot binding are not painted.
    qa = result["report"]["scene_graph_qa"]
    assert qa is not None, result["report"]
    assert qa["verdict"] == "FAIL", qa
    assert qa["ready"] is False, qa
    clip_checks = qa.get("clip_checks") or []
    overlay_checks = [c for c in clip_checks if c.get("criterion") == "Overlay rendered"]
    assert overlay_checks, clip_checks
    assert all(c["status"] == "FAIL" for c in overlay_checks), overlay_checks
    assert not any(c.get("criterion") == "Overlay rendered" and c.get("status") == "PASS"
                   for c in clip_checks), clip_checks

    # 10. (tùy chọn) render 1 frame của beat-0 ra PNG, không qua FFmpeg
    from apps.video_renderer import render_scene_png

    png = tmp_path / "beat-0.png"
    render_scene_png(graphs[0], png, root=tmp_path, purpose=None)
    assert png.is_file() and png.stat().st_size > 0
