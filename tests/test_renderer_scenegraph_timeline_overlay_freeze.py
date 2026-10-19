"""In-memory tests: beat-relative overlay -> absolute FFmpeg window in Scene Graph render mode.

Contract (không đổi, dùng để viết tests):
- graph.overlays[].start_seconds/end_seconds là beat-relative (0 = đầu beat).
- Renderer (video_renderer.py, lines 2673-2689, đã implement):
    abs_start = graph_start + overlay.start_seconds
    abs_end   = graph_start + overlay.end_seconds
  cửa sổ được đóng vào [graph_start, graph_end] qua
  max(graph_start, ...) / min(graph_end, ...), rồi dùng trong
  FFmpeg filter between(t,abs_start,abs_end).
- Executor (scene_graph/executor.py): chỉ vẽ overlay từ graph, KHÔNG đọc lại
  timeline/segment để tái suy overlay.
- Renderer SG mode: KHÔNG đọc lại segment.timeline_events để tạo overlay —
  chỉ dùng sg_graphs[index]["overlays"].

Mọi test chạy in-memory, không ffmpeg, không network, không đọc/ghi repo runtime/
(root = tmp_path; tất cả hàm ghi file và subprocess bị mock).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _fake_package():
    """Template package giả: đủ attribute để _render tính toán, không đục template pack thật."""
    return SimpleNamespace(
        manifest={"output": {"width": 1080, "height": 1920, "frame_rate": 30}, "version": "12.0.0"},
        design_tokens={"palette": {"chalk": "#FFFFFF", "signal_lime": "#00FF00", "ink": "#101814"}},
        channel={"tagline": ""},
        root=ROOT / "template_foundation" / "templates" / "allen-knows-ball" / "12.0.0",
    )


def _graph(segment_id, start, end, overlays=None, index=0):
    from apps.scene_graph.builder import build_scene_graph

    return build_scene_graph(
        segment_id=segment_id,
        visual_mode="hook_card",
        starter_id="C-03",
        graphic_data={"hook_text": "Etihad leads"},
        evidence=["ESPN 14/10/2026"],
        content_type="short",
        start_seconds=start,
        end_seconds=end,
        index=index,
        overlays=overlays,
    )


def _run(run_id, graphs, segments):
    return {
        "run_id": run_id,
        "script_owner_approved": True,
        "voice_preview_audited": True,
        "status": "READY_TO_RENDER",
        "draft": {
            "content_type": "short",
            "duration_target_seconds": 30,
            "segments": segments,
            "scene_graphs": graphs,
        },
    }


def _install_renderer_mocks(monkeypatch, captured_calls):
    import apps.video_renderer as renderer

    monkeypatch.setenv("ACE_SCENE_GRAPH_RENDER", "1")
    monkeypatch.setattr(renderer, "resolve_template", lambda *a, **k: _fake_package())
    monkeypatch.setattr(renderer, "_ffmpeg", lambda root: "ffmpeg")
    monkeypatch.setattr(renderer, "_ffprobe", lambda ffmpeg: "ffprobe")
    monkeypatch.setattr(renderer, "_write_backdrop", lambda *a, **k: None)
    monkeypatch.setattr(renderer, "_write_text", lambda path, text: str(path))
    monkeypatch.setattr(renderer, "_write_scene_graph_beat", lambda *a, **k: None)
    monkeypatch.setattr(renderer, "_write_pass_trail", lambda *a, **k: None)
    monkeypatch.setattr(renderer, "_write_ball_sprite", lambda *a, **k: None)
    monkeypatch.setattr(renderer, "_render_purpose", lambda run, draft: None)

    def draw_sg_overlay(item, window, *, index, job, work_dir, scene_x, scene_y,
                        panel_w, panel_h, font_path, chalk, signal_lime, ink):
        captured_calls.append({
            "item": dict(item),
            "window": window,
            "index": index,
            "job": job,
        })
        return []

    monkeypatch.setattr(renderer, "_draw_sg_overlay", draw_sg_overlay)

    class _FakeCompletedProcess:
        def __init__(self, returncode=0, stdout=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""

    def _fake_run(*a, **k):
        # ffmpeg (lần đầu) và ffprobe (cuối) đều không chạy thật; probe trả về JSON
        # có stream video + duration 30s khớp duration_target.
        return _FakeCompletedProcess(0, '{"format": {"duration": "30.00"}, "streams": [{"codec_type": "video"}]}')

    monkeypatch.setattr(renderer, "subprocess", MagicMock(run=_fake_run))
    return renderer


def _render_full(tmp_path, monkeypatch, run):
    """Chạy _render thật với mọi phụ trọng bị mock; trả về danh sách các lần gọi _draw_sg_overlay."""
    captured = []
    renderer = _install_renderer_mocks(monkeypatch, captured)
    # preview=False + visual_only=True: bỏ qua đoạn voice/soundpack, giữ segments thực tế.
    # voice_preview.path vẫn bắt buộc phải là file thực (được mock, ffmpeg không chạy thật).
    voice_dir = tmp_path / "runtime" / "voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    (voice_dir / "preview.wav").write_bytes(b"\x00" * 44)
    run["voice_preview"] = {"path": "preview.wav"}

    from apps.video_renderer import _render

    _render(tmp_path, run, preview=False, visual_only=True, output_name="out.mp4")
    return captured


def test_renderer_converts_beat_relative_to_absolute_window(tmp_path, monkeypatch):
    """graph beat [9.0, 18.0], overlay clip-relative [2.0, 5.0] -> absolute [11.0, 14.0]."""
    graph_overlay = _graph(
        "beat-2",
        9.0,
        18.0,
        overlays=[{"type": "caption", "text": "Xin chào Việt Nam",
                   "start_seconds": 2.0, "end_seconds": 5.0}],
        index=1,
    )
    run = _run(
        run_id="aaaaaaaaaaaa",
        graphs=[_graph("beat-1", 0.0, 9.0, index=0), graph_overlay],
        segments=[
            {"start_seconds": 0, "end_seconds": 9},
            {"start_seconds": 9, "end_seconds": 18},
        ],
    )
    captured = _render_full(tmp_path, monkeypatch, run)

    assert len(captured) == 1, captured
    call = captured[0]
    # abs_start = 9.0 + 2.0 = 11.0 ; abs_end = 9.0 + 5.0 = 14.0
    assert call["window"] == "between(t,11.000,14.000)", call
    assert call["item"]["text"] == "Xin chào Việt Nam"
    assert call["item"]["start_seconds"] == 2.0
    assert call["item"]["end_seconds"] == 5.0
    assert call["index"] == 1
    assert call["job"] == 0


def test_renderer_sg_mode_does_not_re_read_segment_timeline_events(tmp_path, monkeypatch):
    """sg_graphs không None -> renderer chỉ dùng sg_graphs[index]["overlays"],
    KHÔNG đọc lại segment.timeline_events để tái suy overlay."""
    graph_overlay = _graph(
        "beat-2",
        9.0,
        18.0,
        overlays=[{"type": "caption", "text": "Xin chào Việt Nam",
                   "start_seconds": 2.0, "end_seconds": 5.0}],
        index=1,
    )
    # segment[1] mang timeline_events với overlay ở thời gian KHÁC (tuyệt đối [10,11]
    # -> clip-relative [1,2]). Nếu renderer đọc lại timeline_events thì window sẽ khác
    # so với graph overlay. Chỉ overlay từ graph được vẽ.
    run = _run(
        run_id="bbbbbbbbbbbb",
        graphs=[_graph("beat-1", 0.0, 9.0, index=0), graph_overlay],
        segments=[
            {"start_seconds": 0, "end_seconds": 9},
            {"start_seconds": 9, "end_seconds": 18,
             "timeline_events": [
                 {"item_type": "caption", "text": "từ timeline_events, KHÔNG được vẽ",
                  "start_seconds": 10.0, "end_seconds": 11.0}
             ]},
        ],
    )
    captured = _render_full(tmp_path, monkeypatch, run)

    assert len(captured) == 1, captured
    call = captured[0]
    assert call["window"] == "between(t,11.000,14.000)"
    assert call["item"]["text"] == "Xin chào Việt Nam"
    assert call["item"]["start_seconds"] == 2.0
    assert call["item"]["end_seconds"] == 5.0
    assert call["index"] == 1
    # Không có lần gọi nào sinh từ timeline_events.
    assert not any("timeline" in str(c["item"].get("text", "")) for c in captured)


def test_overlay_window_clamped_to_beat_rejected_by_schema():
    """overlay end_seconds vượt beat_duration -> schema từ chối (clamp/reject theo schema)."""
    from apps.scene_graph.builder import build_scene_graph
    from apps.scene_graph.schema import validate_scene_graph

    # Beat [9.0, 18.0] -> beat_duration = 9. Overlay kết thúc tại 10 > 9 -> từ chối.
    with pytest.raises(ValueError, match="ends after"):
        validate_scene_graph(
            build_scene_graph(
                segment_id="beat-2", visual_mode="hook_card", starter_id="C-03",
                graphic_data={"hook_text": "x"}, evidence=[], content_type="short",
                start_seconds=9.0, end_seconds=18.0, index=1,
                overlays=[{"type": "caption", "text": "x",
                           "start_seconds": 8.0, "end_seconds": 10.0}],
            )
        )
    # Overlay bắt đầu sau cửa sổ beat (start_seconds = 10 > duration 9) cũng bị từ chối.
    with pytest.raises(ValueError, match="starts after"):
        validate_scene_graph(
            build_scene_graph(
                segment_id="beat-2", visual_mode="hook_card", starter_id="C-03",
                graphic_data={"hook_text": "x"}, evidence=[], content_type="short",
                start_seconds=9.0, end_seconds=18.0, index=1,
                overlays=[{"type": "caption", "text": "x",
                           "start_seconds": 10.0, "end_seconds": 11.0}],
            )
        )


def test_sg_overlay_filter_window_format(tmp_path):
    """FFmpeg filter enable='between(t,11.000,14.000)' được tạo đúng từ graph overlay + timing."""
    from apps.video_renderer import _draw_sg_overlay

    filters = _draw_sg_overlay(
        {"type": "caption", "text": "Xin chào Việt Nam", "start_seconds": 2.0, "end_seconds": 5.0},
        "between(t,11.000,14.000)",
        index=1,
        job=0,
        work_dir=tmp_path,
        scene_x=0,
        scene_y=0,
        panel_w=1080,
        panel_h=1920,
        font_path=str(tmp_path / "f.ttf"),
        chalk="0xFFFFFF",
        signal_lime="0x00FF00",
        ink="0x101814",
    )
    assert any("enable='between(t,11.000,14.000)'" in f for f in filters), filters
    assert any("drawtext" in f and "textfile=" in f for f in filters)
    # Text bị-freeze vào text file, không tái suy từ đâu khác.
    text_file = tmp_path / "sg-overlay-1-0-caption.txt"
    assert text_file.is_file()
    assert text_file.read_text(encoding="utf-8") == "Xin chào Việt Nam"
