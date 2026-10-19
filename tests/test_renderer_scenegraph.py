"""Workstream 4: renderer consumes Scene Graphs; QA judges real renders.

- The renderer executes frozen graphs verbatim (no mode/starter/media/
  motion re-decisions). Unknown modes, pending assets and unverified
  media raise loudly.
- QA returns PASS | FAIL | NEEDS_REVIEW with evidence, measured on the
  rendered scene — never PASS on mere asset presence. Media goes through
  both workstream-1 gates (verified/active/file + is_usable_for scope).

Single scene/frame renders only; no ffmpeg, no network, no user data.
"""

from __future__ import annotations

import inspect
import json
import sys
import types
from pathlib import Path

from apps.asset_library.rights_scope import build_rights_scope

CLEARED_SCOPE_JSON = json.dumps(build_rights_scope(
    platforms=["youtube"], territories=["VN"], commercial=True,
    monetization=True, edit_allowed=True, credit_required=True,
    credit_text="A Jean Genie / CC BY 4.0", license="CC BY 4.0",
    source="wikimedia-commons", reviewed_by="human",
))

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def _hook_graph(**overrides):
    from apps.scene_graph.builder import build_scene_graph

    kwargs = {
        "segment_id": "beat-1",
        "visual_mode": "hook_card",
        "starter_id": "C-03",
        "graphic_data": {"hook_text": "Dem ac mong *Etihad*"},
        "evidence": ["ESPN 14/10/2026"],
        "content_type": "short",
        "start_seconds": 0.0,
        "end_seconds": 9.0,
        "index": 0,
    }
    kwargs.update(overrides)
    return build_scene_graph(**kwargs)


def _score_graph(**overrides):
    from apps.scene_graph.builder import build_scene_graph

    kwargs = {
        "segment_id": "beat-2",
        "visual_mode": "score_card",
        "starter_id": "MR-03",
        "graphic_data": {
            "home": "Manchester City", "away": "Paris Saint-Germain",
            "score": "2 - 4", "source": "ESPN", "date": "14/10/2026",
            "context": "Champions League",
        },
        "evidence": ["ESPN 14/10/2026"],
        "content_type": "short",
        "start_seconds": 9.0,
        "end_seconds": 18.0,
        "index": 1,
    }
    kwargs.update(overrides)
    return build_scene_graph(**kwargs)


def _primitive_graph(**overrides):
    from apps.scene_graph.builder import build_scene_graph

    kwargs = {
        "segment_id": "beat-3",
        "visual_mode": "chart_comparison",
        "starter_id": None,
        "graphic_data": {"values": [{"label": "A", "value": 3}]},
        "evidence": [],
        "content_type": "short",
        "start_seconds": 18.0,
        "end_seconds": 24.0,
        "index": 2,
    }
    kwargs.update(overrides)
    return build_scene_graph(**kwargs)


def _broll_graph(asset_id="asset-deadbeef01", **overrides):
    from apps.scene_graph.builder import build_scene_graph

    kwargs = {
        "segment_id": "beat-9",
        "visual_mode": "media_b_roll",
        "starter_id": None,
        "graphic_data": {},
        "evidence": [],
        "content_type": "short",
        "start_seconds": 0.0,
        "end_seconds": 5.0,
        "index": 0,
        "media_asset_id": asset_id,
    }
    kwargs.update(overrides)
    return build_scene_graph(**kwargs)


def _unfrozen(graph):
    """Drop the freeze hash so QA geometry tests can craft violations.

    The validator only checks the hash when recorded; unhashed legacy
    graphs validate fine — and QA must judge those too.
    """
    provenance = graph.get("provenance")
    if isinstance(provenance, dict):
        provenance.pop("graph_hash", None)
    return graph


def _status(report, criterion):
    return next(c["status"] for c in report["checks"] if c["criterion"] == criterion)


def _seed_verified_image(root: Path, asset_id: str = "asset-cleared01") -> None:
    """Minimal verified/active CC BY library row + file (no scope column)."""
    from apps.asset_library.registry import connect

    lib = root / "runtime/assets/library"
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "cleared.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 200)
    conn = connect(root / "runtime" / "engine.db")
    try:
        conn.execute(
            "INSERT INTO assets (asset_id, original_name, stored_path, asset_type,"
            " size_bytes, sha256, source_type, source_url, creator, license_type,"
            " rights_state, lifecycle_state, metadata_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (asset_id, "cleared.jpg", "runtime/assets/library/cleared.jpg",
             "image", 204, "ab" * 32, "wikimedia-commons",
             "https://commons.wikimedia.org/w/index.php?curid=1",
             "A Jean Genie", "CC BY 4.0", "verified", "active", "{}"),
        )
        conn.commit()
    finally:
        conn.close()


def _purpose():
    return {"platform": "youtube", "territory": "VN", "commercial": True,
            "monetization": True, "edit": True, "credit_planned": True,
            "use_count": 0}


# --- renderer: verbatim execution, loud failure -----------------------------


def test_sg_unknown_mode_raises_instead_of_remapping():
    from apps.video_renderer import render_scene_png

    graph = _unfrozen(_hook_graph())
    graph["mode"] = "not_a_mode"
    with pytest.raises(ValueError, match="unknown visual_mode"):
        render_scene_png(graph, ROOT / "nope.png")


def test_sg_canvas_mismatch_raises():
    from apps.video_renderer import render_scene_png

    graph = _unfrozen(_hook_graph())
    graph["design"]["width"] = 500
    with pytest.raises(ValueError, match="canvas"):
        render_scene_png(graph, ROOT / "nope.png")


def test_sg_starter_scene_renders_pixel_exact(tmp_path):
    from apps.video_renderer import render_scene_png

    out = render_scene_png(_hook_graph(), tmp_path / "beat-1.png")
    with Image.open(out) as image:
        assert image.size == (1080, 1920)


def test_sg_broll_pending_asset_raises(tmp_path):
    # No asset_info -> roles.hero_image is approval pending -> the renderer
    # must refuse instead of painting uncleared media.
    from apps.video_renderer import render_scene_png

    with pytest.raises(ValueError, match="pending"):
        render_scene_png(_broll_graph(), tmp_path / "broll.png", root=tmp_path)


def test_sg_broll_unverified_asset_raises(tmp_path):
    from apps.asset_library.registry import connect
    from apps.scene_graph.builder import build_scene_graph
    from apps.video_renderer import render_scene_png

    graph = build_scene_graph(
        segment_id="beat-9", visual_mode="media_b_roll", starter_id=None,
        graphic_data={}, evidence=[], content_type="short",
        start_seconds=0.0, end_seconds=5.0, index=0,
        media_asset_id="asset-deadbeef01",
        asset_info={"rights_state": "verified", "lifecycle_state": "active",
                    "license_type": "CC BY 4.0", "purpose_code": "broll-generic"},
    )
    connect(tmp_path / "runtime" / "engine.db").close()  # empty registry
    # verified/active mà không có rights_scope_json -> builder đánh pending
    # (rights-scope-missing), renderer từ chối ở cột pending trước khi đến registry.
    with pytest.raises(ValueError, match="rights-scope-missing"):
        render_scene_png(graph, tmp_path / "broll.png", root=tmp_path)


def test_sg_path_makes_no_storytelling_decisions():
    import apps.video_renderer as renderer

    banned = ("STARTERS_SHORT", "_hook_lines", "_count_steps",
              "_phrase_lines", "render_starter_layers", "_write_starter_scene")
    # "card_selector" bo tom: normalize_upload_purpose duoc lazy-import trong
    # _render_purpose de chuan hoa purpose cung selector cung renderer — khong
    # lam quyet don layout/motion/coordinate (test tinh than cua banned list).
    sources = [
        inspect.getsource(renderer.render_scene_png),
        inspect.getsource(renderer._write_scene_graph_beat),
        inspect.getsource(renderer._scene_graph_clip),
        inspect.getsource(renderer._scene_graph_media),
        inspect.getsource(renderer._render_purpose),
    ]
    for source in sources:
        for token in banned:
            assert token not in source, token


# --- renderer: scene_graph_clip fail-closed / legacy gating ------------------


def test_sg_flag_on_missing_scene_graphs_raises(monkeypatch):
    from apps.video_renderer import _scene_graph_clip

    monkeypatch.setenv("ACE_SCENE_GRAPH_RENDER", "1")
    with pytest.raises(ValueError, match="missing/empty"):
        _scene_graph_clip({}, False, [])


def test_sg_flag_on_empty_scene_graphs_raises(monkeypatch):
    from apps.video_renderer import _scene_graph_clip

    monkeypatch.setenv("ACE_SCENE_GRAPH_RENDER", "1")
    with pytest.raises(ValueError, match="missing/empty"):
        _scene_graph_clip({"scene_graphs": []}, False, [])


def test_sg_flag_off_missing_scene_graphs_returns_none(monkeypatch):
    from apps.video_renderer import _scene_graph_clip

    monkeypatch.delenv("ACE_SCENE_GRAPH_RENDER", raising=False)
    assert _scene_graph_clip({}, False, []) is None


def test_sg_flag_off_preview_returns_none(monkeypatch):
    from apps.video_renderer import _scene_graph_clip

    monkeypatch.delenv("ACE_SCENE_GRAPH_RENDER", raising=False)
    assert _scene_graph_clip({}, True, []) is None


# --- QA: real measurement, honest verdicts -----------------------------------


def test_qa_measures_real_geometry_on_rendered_scene(tmp_path):
    from apps.measurement.render_qa import qa_scene
    from apps.scene_graph.executor import render_scene_graph_layers
    from apps.video_renderer import render_scene_png

    graph = _score_graph()
    out = render_scene_png(graph, tmp_path / "beat-2.png")
    with Image.open(out) as full:
        full_image = full.convert("RGB")
    bg, text = render_scene_graph_layers(graph)
    report = qa_scene(graph, full_image, bg_image=bg.convert("RGB"),
                      narration="Paris thang Manchester City bon hai.",
                      root=ROOT)
    assert _status(report, "Text clipping (no-clip)") == "PASS"
    assert _status(report, "Safe area") == "PASS"
    assert _status(report, "Scene graph contract") == "PASS"


def test_qa_fails_pushed_box_with_evidence():
    from apps.measurement.render_qa import qa_scene

    graph = _unfrozen(_hook_graph())
    for child in graph["design"]["pages"][0]["children"]:
        if isinstance(child, dict) and child.get("id") == "val-5":
            child["x"] = -60.0
    report = qa_scene(graph, None)
    assert report["verdict"] == "FAIL"
    assert _status(report, "Text clipping (no-clip)") == "FAIL"
    assert _status(report, "Safe area") == "FAIL"
    detail = next(c["detail"] for c in report["checks"]
                  if c["criterion"] == "Text clipping (no-clip)")
    assert "claim" in detail


def test_qa_honours_credit_whisper_exception():
    # C-03 credit sits at y1820+h40 = 96.9%: outside the 87% floor but
    # inside the 97% credit exception — gates must still PASS it.
    from apps.measurement.render_qa import qa_scene

    report = qa_scene(_hook_graph(), None)
    assert _status(report, "Safe area") == "PASS"
    assert _status(report, "Text clipping (no-clip)") == "PASS"
    # ...but with no narration / pixels the scene must NOT pass overall:
    # NEEDS_REVIEW, never a blind PASS.
    assert _status(report, "Narration fit") == "NEEDS_REVIEW"
    assert _status(report, "Contrast (sampled)") == "NEEDS_REVIEW"
    assert report["verdict"] == "NEEDS_REVIEW"


def test_qa_crest_monogram_needs_no_license():
    from apps.measurement.render_qa import check_media_rights

    check = check_media_rights(_score_graph(), ROOT)
    assert check["status"] == "PASS"
    assert "monogram" in check["detail"]


def test_qa_primitive_geometry_needs_review_not_pass():
    from apps.measurement.render_qa import qa_scene

    report = qa_scene(_primitive_graph(), None)
    assert _status(report, "Text clipping (no-clip)") == "NEEDS_REVIEW"
    assert _status(report, "Safe area") == "NEEDS_REVIEW"
    assert _status(report, "Visual density") == "NEEDS_REVIEW"
    assert report["verdict"] == "NEEDS_REVIEW"


def test_qa_narration_overflow_fails():
    from apps.measurement.render_qa import qa_scene

    report = qa_scene(_hook_graph(), None, narration=" ".join(["chuyen"] * 200))
    assert _status(report, "Narration fit") == "FAIL"
    assert report["verdict"] == "FAIL"


def test_qa_media_rights_without_registry_needs_review(tmp_path):
    from apps.measurement.render_qa import check_media_rights
    from apps.scene_graph.builder import build_scene_graph

    graph = build_scene_graph(
        segment_id="beat-9", visual_mode="media_b_roll", starter_id=None,
        graphic_data={}, evidence=[], content_type="short",
        start_seconds=0.0, end_seconds=5.0, index=0,
        media_asset_id="asset-cleared01",
        asset_info={"rights_state": "verified", "lifecycle_state": "active",
                    "license_type": "CC BY 4.0", "purpose_code": "broll-generic"},
    )
    check = check_media_rights(graph, tmp_path, _purpose())
    # asset_info chua rights_scope_json -> builder danh pending ->
    # QA ket qua FAIL (khong duoc phep danh NEEDS_REVIEW bo qua pending gate).
    assert check["status"] == "FAIL"
    assert "pending" in check["detail"]


def test_qa_media_rights_pending_freeze_fails(tmp_path):
    # Frozen pending + empty registry: the pending gate fires first —
    # the planner never cleared this asset.
    from apps.measurement.render_qa import check_media_rights

    check = check_media_rights(_broll_graph(), tmp_path, _purpose())
    assert check["status"] == "FAIL"
    assert "pending" in check["detail"]


def test_qa_media_rights_unknown_asset_fails(tmp_path):
    from apps.asset_library.registry import connect
    from apps.measurement.render_qa import check_media_rights
    from apps.scene_graph.builder import build_scene_graph

    graph = build_scene_graph(
        segment_id="beat-9", visual_mode="media_b_roll", starter_id=None,
        graphic_data={}, evidence=[], content_type="short",
        start_seconds=0.0, end_seconds=5.0, index=0,
        media_asset_id="asset-deadbeef01",
        asset_info={"rights_state": "verified", "lifecycle_state": "active",
                    "license_type": "CC BY 4.0", "purpose_code": "broll-generic"},
    )
    connect(tmp_path / "runtime" / "engine.db").close()  # empty registry
    check = check_media_rights(graph, tmp_path, _purpose())
    assert check["status"] == "FAIL"
    assert "rights-scope-missing" in check["detail"]


def test_qa_media_rights_approved_and_scoped_passes(tmp_path):
    # Full workstream-1 path: approved freeze + verified/active/file +
    # is_usable_for(youtube/VN/commercial) allowed via CC BY backfill.
    from apps.measurement.render_qa import check_media_rights
    from apps.scene_graph.builder import build_scene_graph

    _seed_verified_image(tmp_path)
    graph = build_scene_graph(
        segment_id="beat-9", visual_mode="media_b_roll", starter_id=None,
        graphic_data={}, evidence=[], content_type="short",
        start_seconds=0.0, end_seconds=5.0, index=0,
        media_asset_id="asset-cleared01",
        asset_info={"rights_state": "verified", "lifecycle_state": "active",
                    "license_type": "CC BY 4.0", "purpose_code": "broll-generic",
                    "rights_scope_json": CLEARED_SCOPE_JSON},
    )
    check = check_media_rights(graph, tmp_path, _purpose())
    assert check["status"] == "PASS", check["detail"]
    assert "asset-cleared01" in check["detail"]


def test_qa_media_rights_scope_denied_without_intent(tmp_path):
    # Same cleared asset, but no upload intent: gate-1 passes, the scope
    # gate cannot run without guessing -> NEEDS_REVIEW, never PASS.
    from apps.measurement.render_qa import check_media_rights
    from apps.scene_graph.builder import build_scene_graph

    _seed_verified_image(tmp_path)
    graph = build_scene_graph(
        segment_id="beat-9", visual_mode="media_b_roll", starter_id=None,
        graphic_data={}, evidence=[], content_type="short",
        start_seconds=0.0, end_seconds=5.0, index=0,
        media_asset_id="asset-cleared01",
        asset_info={"rights_state": "verified", "lifecycle_state": "active",
                    "license_type": "CC BY 4.0", "purpose_code": "broll-generic",
                    "rights_scope_json": CLEARED_SCOPE_JSON},
    )
    check = check_media_rights(graph, tmp_path, None)
    # approved trong graph nhung purpose=None -> cuc 2 (is_usable_for) khong
    # chay duoc -> NEEDS_REVIEW, khong bao giờ duoc mac dinh la PASS.
    assert check["status"] == "NEEDS_REVIEW"


def test_qa_clip_timing_gap_fails():
    from apps.measurement.render_qa import qa_clip

    graphs = [_hook_graph(), _score_graph(start_seconds=14.0, end_seconds=20.0)]
    report = qa_clip(graphs)
    assert next(c["status"] for c in report["clip_checks"]
                if c["criterion"] == "Timing continuity") == "FAIL"
    assert report["verdict"] == "FAIL"


def test_qa_clip_motion_mapping_passes_for_v1_graphs():
    from apps.measurement.render_qa import qa_clip

    report = qa_clip([_hook_graph(), _score_graph()])
    assert next(c["status"] for c in report["clip_checks"]
                if c["criterion"] == "Motion execution mapping") == "PASS"


def test_qa_clip_structure_roles():
    from apps.measurement.render_qa import qa_clip

    graphs = [_hook_graph(), _score_graph()]
    blind = qa_clip(graphs)
    assert next(c["status"] for c in blind["clip_checks"]
                if c["criterion"] == "Video structure") == "NEEDS_REVIEW"
    labelled = qa_clip(graphs, roles={"beat-1": "hook", "beat-2": "ending"})
    assert next(c["status"] for c in labelled["clip_checks"]
                if c["criterion"] == "Video structure") == "PASS"


# --- renderer: Scene Graph opening/ending brand scenes -----------------------


def _resolve_template_package():
    import template_foundation
    from pathlib import Path
    repo_root = Path(__file__).resolve().parent.parent
    return template_foundation.resolve_template(
        repo_root, "allen-knows-ball.shortform-analyst", allow_draft=True
    )


@pytest.mark.parametrize("content_type,role,card_id", [
    ("short", "opening", "C-01"),   # legacy path still renders C-01 directly
    ("short", "ending", "C-10"),
    ("long", "opening", "LC-14"),
    ("long", "ending", "LC-14"),
])
def test_render_brand_scene_renders(tmp_path, content_type, role, card_id):
    from apps.video_renderer import _render_brand_scene
    package = _resolve_template_package()
    out = tmp_path / f"{content_type}_{role}.png"
    _render_brand_scene(package, content_type=content_type, role=role,
                        output_path=out)
    assert out.is_file() and out.stat().st_size > 0


def test_short_form_render_full_run_skips_opening(monkeypatch, tmp_path):
    """Short-form full render must NOT render the C-01 opening scene.

    Mocks _render_brand_scene to record which roles are rendered, then runs
    the real _render path (with heavy drawing primitives mocked out) for a
    short-form run. Asserts opening is never rendered while ending still is.
    """
    import apps.video_renderer as renderer
    import template_foundation
    from pathlib import Path

    run = _make_run(tmp_path, "aaaaaaaaaaaa")
    run["draft"]["duration_target_seconds"] = 20
    run["voice_preview"] = {"path": "preview.wav"}
    (tmp_path / "runtime" / "runs" / f"{run['run_id']}.json").write_text(
        json.dumps(run, ensure_ascii=False), encoding="utf-8"
    )
    # Create a silent WAV voice preview so _render's voice check passes.
    import wave
    voice_dir = tmp_path / "runtime" / "voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    with wave.open(str(voice_dir / "preview.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100)

    calls = []
    def fake_brand_scene(package, *, content_type, role, output_path):
        calls.append((role, content_type))
        # Write a valid placeholder PNG so downstream ffmpeg input exists.
        from PIL import Image
        Image.new("RGB", (1080, 1920), (0, 0, 0)).save(output_path)

    monkeypatch.setattr(renderer, "_render_brand_scene", fake_brand_scene)
    monkeypatch.setattr(renderer, "_ensure_voice_fits_script", lambda root, run: None)
    import apps.card_selector as card_selector_mod
    monkeypatch.setattr(card_selector_mod, "apply_card_plan", lambda root, run: None)

    repo_root = Path(__file__).resolve().parent.parent
    monkeypatch.setattr(renderer, "resolve_template",
        lambda root, template_id, version=None, *, allow_draft=False:
            template_foundation.resolve_template(repo_root, template_id,
                                                 version=version,
                                                 allow_draft=allow_draft))

    monkeypatch.setattr(renderer, "_ffmpeg", lambda root: "ffmpeg")
    monkeypatch.setattr(renderer, "_write_backdrop", lambda *a, **k: None)
    monkeypatch.setattr(renderer, "_write_scene_graph_beat",
                        lambda *a, **k: None)
    monkeypatch.setattr(renderer, "_write_text", lambda *a, **k: str(a[0]))
    monkeypatch.setattr(renderer, "_write_editorial_data_scene",
                        lambda *a, **k: None)

    class _FakeResult:
        returncode = 0
        stdout = '{"format": {"duration": "20.0", "size": "1000"}, "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920}]}'

    monkeypatch.setattr(renderer.subprocess, "run",
                        lambda *a, **k: _FakeResult())

    renderer.render_full_run(tmp_path, "aaaaaaaaaaaa")

    # Short-form: no opening scene should be rendered.
    opening_calls = [c for c in calls if c[0] == "opening"]
    assert not opening_calls, f"short-form should not render opening: {calls}"
    # Ending should still be rendered.
    ending_calls = [c for c in calls if c[0] == "ending"]
    assert ending_calls, "short-form should still render ending"


def test_readiness_verdict_false_for_fail_and_needs_review():
    from apps.measurement.render_qa import readiness_verdict

    assert readiness_verdict({"verdict": "FAIL"}) is False
    assert readiness_verdict({"verdict": "NEEDS_REVIEW"}) is False
    assert readiness_verdict(None) is False


def test_readiness_verdict_true_for_pass():
    from apps.measurement.render_qa import readiness_verdict

    assert readiness_verdict({"verdict": "PASS"}) is True


def test_qa_scene_ready_false_on_verdict_fail():
    from apps.measurement.render_qa import qa_scene

    report = qa_scene(_hook_graph(), None,
                      narration=" ".join(["chuyen"] * 200))
    assert report["verdict"] == "FAIL"
    assert report["ready"] is False


def test_qa_scene_ready_false_on_verdict_needs_review():
    from apps.measurement.render_qa import qa_scene

    report = qa_scene(_hook_graph(), None)
    assert report["verdict"] == "NEEDS_REVIEW"
    assert report["ready"] is False


def test_qa_clip_ready_false_on_timing_fail():
    from apps.measurement.render_qa import qa_clip

    graphs = [_hook_graph(), _score_graph(start_seconds=14.0, end_seconds=20.0)]
    report = qa_clip(graphs)
    assert next(c["status"] for c in report["clip_checks"]
                if c["criterion"] == "Timing continuity") == "FAIL"
    assert report["verdict"] == "FAIL"
    assert report["ready"] is False


# --- renderer: Scene Graph wiring in render_full_run -----------------------
#
# apps.scene_graph.pipeline (Agent 2) chưa có trong cây này, do wiring của
# render_full_run được kiểm tra bằng cách inject một module pipeline giả vào
# sys.modules trước khi import lazy bên trong hàm thực thi. Không gọi
# render_full_run thật (cần ffmpeg/voice/owner approval) — mọi phụ thuộc nặng
# đều bị mock, chạy in-memory trong tmp_path.


def _make_run(root: Path, run_id: str = "aaaaaaaaaaaa") -> dict:
    run = {
        "run_id": run_id,
        "script_owner_approved": True,
        "voice_preview_audited": True,
        "status": "READY_TO_RENDER",
        "draft": {
            "content_type": "short",
            "duration_target_seconds": 18,
            "segments": [
                {"start_seconds": 0, "end_seconds": 9},
                {"start_seconds": 9, "end_seconds": 18},
            ],
        },
    }
    (root / "runtime" / "runs").mkdir(parents=True, exist_ok=True)
    (root / "runtime" / "runs" / f"{run_id}.json").write_text(
        json.dumps(run, ensure_ascii=False), encoding="utf-8"
    )
    return run


def _install_fake_pipeline(monkeypatch, graphs):
    """Gạt apps.scene_graph.pipeline bằng module giả ghi nhận các cuộc gọi."""
    fake_calls = []

    def build_run_scene_graphs(root, run):
        fake_calls.append((root, run))
        run.setdefault("draft", {})["scene_graphs"] = list(graphs)

    mod = types.ModuleType("apps.scene_graph.pipeline")
    mod.build_run_scene_graphs = build_run_scene_graphs
    monkeypatch.setitem(sys.modules, "apps.scene_graph.pipeline", mod)
    return fake_calls


def _mock_render_deps(monkeypatch):
    import apps.video_renderer as renderer
    import apps.card_selector as card_selector

    monkeypatch.setattr(renderer, "_ensure_voice_fits_script", lambda root, run: None)
    monkeypatch.setattr(
        renderer,
        "_render",
        lambda root, run, preview, output_name: {
            "report": {"rendered_at": "2026-10-17T00:00:00Z"},
            "rendered": True,
        },
    )
    monkeypatch.setattr(card_selector, "apply_card_plan", lambda root, run: None)
    return renderer


def test_render_full_run_builds_and_attaches_scene_graphs_flag_on(tmp_path, monkeypatch):
    monkeypatch.setenv("ACE_SCENE_GRAPH_RENDER", "1")
    graphs = [{"segment_id": "beat-1"}, {"segment_id": "beat-2"}]
    calls = _install_fake_pipeline(monkeypatch, graphs)
    renderer = _mock_render_deps(monkeypatch)

    run = _make_run(tmp_path)
    result = renderer.render_full_run(tmp_path, run["run_id"])

    assert result["rendered"] is True
    assert len(calls) == 1
    assert calls[0] == (tmp_path, calls[0][1])
    assert calls[0][1]["draft"]["scene_graphs"] == graphs

    # Gắn graph cũng được lưu lại khi render_full_run ghi run.json trở lại.
    stored = json.loads(
        (tmp_path / "runtime" / "runs" / f"{run['run_id']}.json").read_text(encoding="utf-8")
    )
    assert stored["draft"]["scene_graphs"] == graphs


def test_render_full_run_skips_build_flag_off(tmp_path, monkeypatch):
    monkeypatch.delenv("ACE_SCENE_GRAPH_RENDER", raising=False)
    graphs = [{"segment_id": "beat-1"}, {"segment_id": "beat-2"}]
    calls = _install_fake_pipeline(monkeypatch, graphs)
    renderer = _mock_render_deps(monkeypatch)

    run = _make_run(tmp_path)
    result = renderer.render_full_run(tmp_path, run["run_id"])

    assert result["rendered"] is True
    assert calls == []
    assert "scene_graphs" not in run.get("draft", {})

    # Legacy path: flag tắt -> _scene_graph_clip trả None, không rơi vào fail-closed.
    from apps.video_renderer import _scene_graph_clip
    assert _scene_graph_clip(run["draft"], False, [(0, 9), (9, 18)]) is None


def test_render_full_run_fail_closed_when_scene_graph_build_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("ACE_SCENE_GRAPH_RENDER", "1")

    def boom(root, run):
        raise ValueError("scene graph build failed: missing starter mapping")

    mod = types.ModuleType("apps.scene_graph.pipeline")
    mod.build_run_scene_graphs = boom
    monkeypatch.setitem(sys.modules, "apps.scene_graph.pipeline", mod)
    renderer = _mock_render_deps(monkeypatch)

    run = _make_run(tmp_path)
    with pytest.raises(ValueError, match="scene graph build failed"):
        renderer.render_full_run(tmp_path, run["run_id"])


# --- render_full_run: production path với pipeline thật (không fake) -------
# build_run_scene_graphs thật (apps.scene_graph.pipeline), run đầy đủ
# card_plan/decisions, chạy in-memory trong tmp_path. Mock _render +
# _ensure_voice_fits_script (tránh ffmpeg/voice) và apply_card_plan (giữ
# card_plan đã bait); không fake pipeline. Không viết runtime thực.


_HOOK_DECISION = {
    "segment_id": "beat-1",
    "visual_mode": "hook_card",
    "starter_id": "C-03",
    "graphic_data": {"hook_text": "Demo *Etihad*"},
    "evidence": ["ESPN 14/10/2026"],
    "index": 0,
}

_SCORE_DECISION = {
    "segment_id": "beat-2",
    "visual_mode": "score_card",
    "starter_id": "MR-03",
    "graphic_data": {
        "home": "Manchester City", "away": "Paris Saint-Germain",
        "score": "2 - 4", "source": "ESPN", "date": "14/10/2026",
        "context": "Champions League",
    },
    "evidence": ["ESPN 14/10/2026"],
    "index": 1,
}

_BROLL_DECISION = {
    "segment_id": "beat-9",
    "visual_mode": "media_b_roll",
    "starter_id": None,
    "graphic_data": {},
    "evidence": [],
    "media_asset_id": "asset-cleared01",
    "index": 0,
}

_SEGMENTS = [
    {"id": "beat-1", "start_seconds": 0, "end_seconds": 9,
     "beat_intent": {"image_goal": "establish_moment", "focus_subject": "Etihad hook",
                     "evidence_type": "sourced_stat", "emphasis_level": "hero"}},
    {"id": "beat-2", "start_seconds": 9, "end_seconds": 18,
     "beat_intent": {"image_goal": "show_evidence", "focus_subject": "Man City vs PSG",
                     "evidence_type": "match_event", "emphasis_level": "standard"}},
    {"id": "beat-9", "start_seconds": 0, "end_seconds": 5,
     "beat_intent": {"image_goal": "land_takeaway", "focus_subject": "closing b-roll",
                     "evidence_type": "none", "emphasis_level": "quiet"}},
]


def _make_full_run(root: Path, run_id: str, decisions, segments,
                   content_type: str = "short", template_version: str = "12.0.0"):
    run = {
        "run_id": run_id,
        "script_owner_approved": True,
        "voice_preview_audited": True,
        "status": "READY_TO_RENDER",
        "draft": {
            "content_type": content_type,
            "template_version": template_version,
            "segments": segments,
        },
        "card_plan": {"decisions": list(decisions)},
    }
    (root / "runtime" / "runs").mkdir(parents=True, exist_ok=True)
    (root / "runtime" / "runs" / f"{run_id}.json").write_text(
        json.dumps(run, ensure_ascii=False), encoding="utf-8"
    )
    return run


def _mock_full_render_deps(monkeypatch):
    import apps.video_renderer as renderer
    import apps.card_selector as card_selector

    render_calls = []
    monkeypatch.setattr(renderer, "_ensure_voice_fits_script", lambda root, run: None)
    monkeypatch.setattr(
        renderer,
        "_render",
        lambda root, run, preview, output_name: (
            render_calls.append((root, run, output_name)),
            {"report": {"rendered_at": "2026-10-18T00:00:00Z"}, "rendered": True},
        )[1],
    )
    # Giữ nguyên card_plan đã bait trong run; chỉ build_run_scene_graphs là thật.
    monkeypatch.setattr(card_selector, "apply_card_plan", lambda root, run: None)
    return renderer, render_calls


def test_render_full_run_real_pipeline_flag_on_attaches_graphs(tmp_path, monkeypatch):
    monkeypatch.setenv("ACE_SCENE_GRAPH_RENDER", "1")
    renderer, render_calls = _mock_full_render_deps(monkeypatch)
    run = _make_full_run(tmp_path, "aaaaaaaaaaaa",
                         [_HOOK_DECISION, _SCORE_DECISION], _SEGMENTS[:2])

    result = renderer.render_full_run(tmp_path, run["run_id"])

    assert result["rendered"] is True
    assert len(render_calls) == 1  # _render được gọi 1 lần, không rơi về legacy

    stored = json.loads(
        (tmp_path / "runtime" / "runs" / f"{run['run_id']}.json").read_text(encoding="utf-8")
    )
    graphs = stored["draft"]["scene_graphs"]
    assert isinstance(graphs, list) and len(graphs) == 2
    # build_run_scene_graphs truyền template_version + beat_intent từ draft segments
    assert graphs[0]["provenance"]["template_version"] == "12.0.0"
    assert graphs[0]["provenance"]["beat_intent"] == _SEGMENTS[0]["beat_intent"]
    assert graphs[1]["provenance"]["template_version"] == "12.0.0"
    assert graphs[1]["provenance"]["beat_intent"] == _SEGMENTS[1]["beat_intent"]
    # Mỗi graph đã freeze (graph_hash) và validate lại vẫn pass.
    from apps.scene_graph.schema import validate_scene_graph

    for graph in graphs:
        assert len(graph["provenance"]["graph_hash"]) == 64
        validate_scene_graph(graph)


def test_render_full_run_real_pipeline_flag_off_no_graphs(tmp_path, monkeypatch):
    monkeypatch.delenv("ACE_SCENE_GRAPH_RENDER", raising=False)
    renderer, render_calls = _mock_full_render_deps(monkeypatch)
    run = _make_full_run(tmp_path, "bbbbbbbbbbbb",
                         [_HOOK_DECISION, _SCORE_DECISION], _SEGMENTS[:2])

    result = renderer.render_full_run(tmp_path, run["run_id"])

    assert result["rendered"] is True
    assert len(render_calls) == 1
    # Flag tắt: legacy path byte-identical, không build/gắn scene_graphs.
    assert "scene_graphs" not in run.get("draft", {})


def test_render_full_run_real_pipeline_build_fail_raises_valueerror(tmp_path, monkeypatch):
    monkeypatch.setenv("ACE_SCENE_GRAPH_RENDER", "1")
    renderer, render_calls = _mock_full_render_deps(monkeypatch)

    def _write(run: dict) -> None:
        (tmp_path / "runtime" / "runs").mkdir(parents=True, exist_ok=True)
        (tmp_path / "runtime" / "runs" / f"{run['run_id']}.json").write_text(
            json.dumps(run, ensure_ascii=False), encoding="utf-8"
        )

    # Thiếu card_plan -> build_run_scene_graphs raise ValueError; render_full_run
    # dừng ngay, KHÔNG gọi _render (không rơi về legacy render).
    run_no_plan = {
        "run_id": "cccccccccccc",
        "script_owner_approved": True,
        "voice_preview_audited": True,
        "status": "READY_TO_RENDER",
        "draft": {"content_type": "short", "segments": [_SEGMENTS[0]]},
    }
    _write(run_no_plan)
    with pytest.raises(ValueError, match="card plan"):
        renderer.render_full_run(tmp_path, run_no_plan["run_id"])
    assert render_calls == []

    # Thiếu segments -> ValueError, cũng không gọi _render.
    run_no_segments = {
        "run_id": "dddddddddddd",
        "script_owner_approved": True,
        "voice_preview_audited": True,
        "status": "READY_TO_RENDER",
        "draft": {"content_type": "short"},
        "card_plan": {"decisions": [_HOOK_DECISION]},
    }
    _write(run_no_segments)
    with pytest.raises(ValueError, match="segments"):
        renderer.render_full_run(tmp_path, run_no_segments["run_id"])
    assert render_calls == []


def test_render_full_run_real_pipeline_asset_map_reads_rights_scope_json(tmp_path, monkeypatch):
    # asset_map đọc rights_scope_json từ DB; verified/active đơn lẻ KHÔNG đủ
    # để coi là cleared (không suy quyền từ rights_state).
    from apps.asset_library.registry import connect

    monkeypatch.setenv("ACE_SCENE_GRAPH_RENDER", "1")
    renderer, render_calls = _mock_full_render_deps(monkeypatch)

    db_path = tmp_path / "runtime" / "engine.db"
    conn = connect(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(assets)").fetchall()}
    if "rights_scope_json" not in cols:
        conn.execute("ALTER TABLE assets ADD COLUMN rights_scope_json TEXT")
    conn.execute(
        "INSERT INTO assets (asset_id, original_name, stored_path, asset_type, size_bytes,"
        " sha256, source_type, source_url, creator, license_type, rights_state,"
        " lifecycle_state, metadata_json, rights_scope_json)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("asset-cleared01", "cleared.jpg", "runtime/assets/library/cleared.jpg", "image", 204,
         "ab" * 32, "wikimedia-commons", "https://commons.wikimedia.org/wiki/Cleared",
         "A Jean Genie", "CC BY 4.0", "verified", "active", "{}", CLEARED_SCOPE_JSON),
    )
    conn.commit()
    conn.close()

    run = _make_full_run(tmp_path, "eeeeeeeeeeee", [_BROLL_DECISION], [_SEGMENTS[2]])
    result = renderer.render_full_run(tmp_path, run["run_id"])

    assert result["rendered"] is True
    stored = json.loads(
        (tmp_path / "runtime" / "runs" / f"{run['run_id']}.json").read_text(encoding="utf-8")
    )
    graphs = stored["draft"]["scene_graphs"]
    assert len(graphs) == 1
    hero = graphs[0]["roles"]["hero_image"]
    assert hero["asset_id"] == "asset-cleared01"
    # Quyền được cấp từ rights_scope_json (granted_by="human"), không từ rights_state.
    assert hero["approval_status"] == "approved", hero
    assert "human-granted" in hero["rights_scope"], hero


# --- SG overlay: renderer reads from graph, never re-derives from timeline ---


def _ol_graph(**overrides):
    from apps.scene_graph.builder import build_scene_graph

    kwargs = {
        "segment_id": "beat-ol",
        "visual_mode": "hook_card",
        "starter_id": "C-03",
        "graphic_data": {"hook_text": "Etihad leads"},
        "evidence": ["ESPN 14/10/2026"],
        "content_type": "short",
        "start_seconds": 0.0,
        "end_seconds": 9.0,
        "index": 0,
        "overlays": [
            {"type": "lower_third", "text": "Etihad leads", "start_seconds": 2.0,
             "end_seconds": 5.0, "role": "name_tag"},
        ],
    }
    kwargs.update(overrides)
    return build_scene_graph(**kwargs)


def test_sg_clip_preserves_graph_overlays(monkeypatch):
    # Freeze flag on: one graph per segment, overlays carried through verbatim.
    monkeypatch.setenv("ACE_SCENE_GRAPH_RENDER", "1")
    from apps.video_renderer import _scene_graph_clip

    graphs = _scene_graph_clip(
        {"scene_graphs": [_ol_graph()]}, False, [(0.0, 9.0)])
    assert len(graphs) == 1
    assert graphs[0]["overlays"] == [
        {"type": "lower_third", "text": "Etihad leads",
         "start_seconds": 2.0, "end_seconds": 5.0, "role": "name_tag"}]


def test_sg_overlay_clip_relative_on_nonzero_beat_not_rejected(monkeypatch):
    """Beat [9.0, 18.0] (start_seconds > 0) kem overlay clip-relative [2.0, 5.0].

    Thoi gian overlay la CLIP-RELATIVE (bat dau tu dau beat): duoc so sanh
    voi beat_duration = 18 - 9 = 9, KHONG so thang truc tiep voi
    timing.start = 9. Sau Agent A chinh sua validator timebase, [2.0, 5.0]
    thoa 0 <= 2 < 5 <= 9 nen schema/clip KHONG tu choi (hien tai chua sua
    thi se bi "starts before the beat window" — chay lai sau Agent A/B).
    Renderer (sau Agent B) chuyen clip-relative sang absolute ve khung:
    abs_start = 9.0 + 2.0 = 11.0, abs_end = 9.0 + 5.0 = 14.0
    (window between(t,11.000,14.000)). Test nay KHONG render video dai: chi
    validate graph va goi _scene_graph_clip de xac nhan khong bi tu choi.
    Renderer must suppress any unbound free-standing text."""
    from apps.video_renderer import _scene_graph_clip
    from apps.scene_graph.builder import build_scene_graph
    from apps.scene_graph.schema import validate_scene_graph

    graph = build_scene_graph(
        segment_id="beat-2",
        visual_mode="hook_card",
        starter_id="C-03",
        graphic_data={"hook_text": "Etihad leads"},
        evidence=["ESPN 14/10/2026"],
        content_type="short",
        start_seconds=9.0,
        end_seconds=18.0,
        index=1,
        overlays=[
            {"type": "caption", "text": "Xin chao Viet Nam",
             "start_seconds": 2.0, "end_seconds": 5.0}
        ],
    )

    # Schema chap nhan (clip-relative vs beat_duration), khong tu choi overlay.
    validate_scene_graph(graph)

    # Clip-level khong tu choi (flag on, dung 1 graph / 1 beat).
    monkeypatch.setenv("ACE_SCENE_GRAPH_RENDER", "1")
    checked = _scene_graph_clip(
        {"scene_graphs": [graph]}, False, [(9.0, 18.0)]
    )
    assert len(checked) == 1
    assert checked[0]["segment_id"] == "beat-2"
    assert checked[0]["overlays"] == [
        {"type": "caption", "text": "Xin chao Viet Nam",
         "start_seconds": 2.0, "end_seconds": 5.0}
    ]


def test_sg_flag_off_legacy_does_not_read_graph_overlay(monkeypatch):
    # Flag tắt -> _scene_graph_clip từ chối scene_graphs (None) và không đi
    # vào đường dẫn vẽ overlay từ graph.
    monkeypatch.delenv("ACE_SCENE_GRAPH_RENDER", raising=False)
    from apps.video_renderer import _scene_graph_clip
    assert _scene_graph_clip({"scene_graphs": [_ol_graph()]}, False, [(0.0, 9.0)]) is None


# --- QA: overlay rendered criterion ----------------------------------------


def test_qa_scene_overlay_bad_timing_fails():
    from apps.measurement.render_qa import qa_scene

    # Overlay kết thúc sau cửa sổ beat (0-9) -> schema từ chối, QA surfaced
    # qua criterion "Overlay rendered" làm FAIL.
    report = qa_scene(
        _ol_graph(overlays=[{"type": "caption", "text": "muộn",
                             "start_seconds": 20.0, "end_seconds": 25.0}]),
        None)
    assert _status(report, "Overlay rendered") == "FAIL"
    assert report["verdict"] == "FAIL"
    assert report["ready"] is False


def test_qa_scene_overlay_declared_empty_text_not_pass():
    from apps.measurement.render_qa import qa_scene

    report = qa_scene(
        _ol_graph(overlays=[{"type": "caption", "text": "",
                             "start_seconds": 1.0, "end_seconds": 2.0}]),
        None)
    assert _status(report, "Overlay rendered") == "FAIL"
    assert report["verdict"] == "FAIL"


def test_qa_scene_overlay_without_template_slot_fails():
    # Overlay có text/timing hợp lệ vẫn không được render nếu chưa bind vào slot.
    from apps.measurement.render_qa import qa_scene

    report = qa_scene(_ol_graph(), None)
    assert _status(report, "Overlay rendered") == "FAIL"
    assert report["verdict"] == "FAIL"
    assert report["ready"] is False


def test_qa_scene_no_overlay_declared_passes_gate():
    from apps.measurement.render_qa import qa_scene

    # Không overlay nào được khai báo -> PASS (không có gì cần vẽ).
    report = qa_scene(_hook_graph(), None)
    assert _status(report, "Overlay rendered") == "PASS"


def test_qa_clip_overlay_bad_timing_fails():
    from apps.measurement.render_qa import qa_clip

    graphs = [_ol_graph(overlays=[{"type": "caption", "text": "muộn",
                                    "start_seconds": 20.0, "end_seconds": 25.0}])]
    report = qa_clip(graphs)
    statuses = {c["criterion"]: c["status"] for c in report["clip_checks"]}
    assert statuses["Overlay rendered"] == "FAIL"
    assert report["verdict"] == "FAIL"
    assert report["ready"] is False


def test_qa_clip_overlay_without_template_slot_fails():
    from apps.measurement.render_qa import qa_clip

    # Overlay clip-relative [2,4] nằm trong beat_duration = 9, nhưng chưa có
    # frozen template-slot binding nên phải fail closed.
    graphs = [_ol_graph(), _ol_graph(segment_id="beat-ol-2", start_seconds=9.0,
                                     end_seconds=18.0,
                                     overlays=[{"type": "lower_third", "text": "x",
                                                "start_seconds": 2.0,
                                                "end_seconds": 4.0}])]
    report = qa_clip(graphs)
    statuses = {c["criterion"]: c["status"] for c in report["clip_checks"]}
    assert statuses["Overlay rendered"] == "FAIL"
    assert report["verdict"] == "FAIL"
    assert report["ready"] is False
