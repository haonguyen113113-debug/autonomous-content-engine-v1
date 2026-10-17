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
from pathlib import Path

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
    with pytest.raises(ValueError, match="does not exist"):
        render_scene_png(graph, tmp_path / "broll.png", root=tmp_path)


def test_sg_path_makes_no_storytelling_decisions():
    import apps.video_renderer as renderer

    banned = ("card_selector", "STARTERS_SHORT", "_hook_lines", "_count_steps",
              "_phrase_lines", "render_starter_layers", "_write_starter_scene")
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
    assert check["status"] == "NEEDS_REVIEW"
    assert "unverifiable" in check["detail"]


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
    assert "does not exist" in check["detail"]


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
                    "license_type": "CC BY 4.0", "purpose_code": "broll-generic"},
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
                    "license_type": "CC BY 4.0", "purpose_code": "broll-generic"},
    )
    check = check_media_rights(graph, tmp_path, None)
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


# --- render_qa: readiness field --------------------------------------------


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
