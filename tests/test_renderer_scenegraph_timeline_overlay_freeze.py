"""In-memory tests: reject free-standing copy outside template slots.

Contract:
- Graph may retain clip-relative overlay metadata for audit/provenance.
- Renderer does not paint free-standing overlays without a frozen template
  slot binding; QA reports them as FAIL.

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
    monkeypatch.setattr(renderer, "_render_brand_scene", lambda package, *, content_type, role, output_path: output_path.write_bytes(b"fixed-card"))
    monkeypatch.setattr(renderer, "_render_purpose", lambda run, draft: None)

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
    """Run _render with side effects mocked; return attempted free-standing text draws."""
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


def test_renderer_suppresses_unbound_scene_graph_overlay(tmp_path, monkeypatch):
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

    assert captured == []


def test_renderer_suppresses_graph_and_timeline_copy(tmp_path, monkeypatch):
    """Neither graph overlays nor timeline captions may create renderer text."""
    graph_overlay = _graph(
        "beat-2",
        9.0,
        18.0,
        overlays=[{"type": "caption", "text": "Xin chào Việt Nam",
                   "start_seconds": 2.0, "end_seconds": 5.0}],
        index=1,
    )
    # segment[1] mang timeline_events với overlay ở thời gian KHÁC (tuyệt đối [10,11]
    # -> clip-relative [1,2]). Neither source is template-slot-bound, so neither
    # should be painted.
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

    assert captured == []


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
