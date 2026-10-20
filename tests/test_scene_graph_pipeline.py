"""In-memory tests for apps.scene_graph.pipeline.build_run_scene_graphs.

No runtime/ access: the asset registry lookup is monkeypatched.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _canonical(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def _run_hash(run: dict) -> str:
    """Hash of run content inputs (scene_graphs attachment excluded)."""
    snapshot = copy.deepcopy(run)
    snapshot.get("draft", {}).pop("scene_graphs", None)
    return hashlib.sha256(_canonical(snapshot).encode("utf-8")).hexdigest()


def _make_run(media_asset_ids=None) -> dict:
    media_asset_ids = media_asset_ids or [None, None, None]
    return {
        "draft": {
            "content_type": "short",
            "template_version": "12.0.0",
            "segments": [
                {
                    "id": "beat-1",
                    "start_seconds": 0.0,
                    "end_seconds": 9.0,
                    "beat_intent": {
                        "image_goal": "establish_moment",
                        "focus_subject": "opening claim",
                        "evidence_type": "sourced_quote",
                        "emphasis_level": "hero",
                    },
                    "evidence_refs": ["ESPN 14/10/2026"],
                },
                {
                    "id": "beat-2",
                    "start_seconds": 9.0,
                    "end_seconds": 18.0,
                    "beat_intent": {
                        "image_goal": "show_evidence",
                        "focus_subject": "score",
                        "evidence_type": "match_event",
                        "emphasis_level": "standard",
                    },
                    "evidence_refs": ["ESPN 14/10/2026"],
                },
                {
                    "id": "beat-3",
                    "start_seconds": 18.0,
                    "end_seconds": 27.0,
                    "beat_intent": {
                        "image_goal": "land_takeaway",
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
                {
                    "segment_id": "beat-1",
                    "index": 0,
                    "visual_mode": "hook_card",
                    "starter_id": "C-03",
                    "media_asset_id": media_asset_ids[0],
                    "graphic_data": {"hook_text": "Dem ac mong *Etihad*"},
                },
                {
                    "segment_id": "beat-2",
                    "index": 1,
                    "visual_mode": "score_card",
                    "starter_id": "MR-03",
                    "media_asset_id": media_asset_ids[1],
                    "graphic_data": {
                        "home": "Manchester City",
                        "away": "Paris Saint-Germain",
                        "score": "2 - 4",
                    },
                },
                {
                    "segment_id": "beat-3",
                    "index": 2,
                    "visual_mode": "media_b_roll",
                    "starter_id": None,
                    "media_asset_id": media_asset_ids[2],
                    "graphic_data": {"hook_text": "Dong phim ket thuc"},
                },
            ],
        },
    }


def _human_scope_json() -> str:
    scope = {
        "schema_version": 1,
        "platforms": ["youtube", "tiktok"],
        "territories": ["VN"],
        "commercial": True,
        "monetization": True,
        "edit_allowed": True,
        "credit": {"required": True, "text": "Nguon"},
        "granted_by": "human",
        "license": "CC BY 4.0",
        "source": "owner",
    }
    return json.dumps(scope, ensure_ascii=False, sort_keys=True)


def _patch_registry(monkeypatch, asset_infos: dict[str, dict]) -> None:
    from apps.scene_graph import pipeline

    def fake_fetch(root: Path, media_ids: list[str]) -> dict[str, dict]:
        return {mid: info for mid, info in asset_infos.items() if mid in media_ids}

    monkeypatch.setattr(pipeline, "_fetch_asset_infos", fake_fetch)


def test_attaches_and_returns_all_segment_graphs(monkeypatch):
    from apps.scene_graph import pipeline
    from apps.scene_graph.schema import validate_scene_graph

    _patch_registry(monkeypatch, {})
    # beat-3 có media_asset_id nhưng không có record -> pending placeholder
    run = _make_run(media_asset_ids=[None, None, "asset-missing"])
    graphs = pipeline.build_run_scene_graphs(ROOT, run)

    assert graphs == run["draft"]["scene_graphs"]  # gắn vào draft và trả về
    assert len(graphs) == 3  # số graph = số segment
    assert [g["segment_id"] for g in graphs] == ["beat-1", "beat-2", "beat-3"]
    for graph in graphs:
        validate_scene_graph(graph)  # mỗi graph validate được
    assert graphs[0]["mode"] == "hook_card"
    assert graphs[0]["kind"] == "starter"
    assert graphs[2]["kind"] == "primitive"
    # timing đọc từ segment (không tự bịa)
    assert graphs[0]["timing"] == {"start": 0.0, "end": 9.0}
    assert graphs[1]["timing"] == {"start": 9.0, "end": 18.0}
    # beat-3 có media_asset_id nhưng không có registry record -> pending placeholder
    ref = graphs[2]["roles"]["hero_image"]
    assert ref is not None and ref["approval_status"] == "pending"


@pytest.mark.parametrize(
    "mutate, match",
    [
        (lambda run: run.pop("draft"), "run\\['draft'\\]"),
        (lambda run: run["draft"].pop("segments"), "segments"),
        (lambda run: run["draft"].update(segments=[]), "non-empty list"),
        (lambda run: run.pop("card_plan"), "apply_card_plan"),
        (lambda run: run["card_plan"].pop("decisions"), "apply_card_plan"),
        (lambda run: run["card_plan"].update(decisions=[]), "non-empty list"),
    ],
)
def test_missing_inputs_raise_clear_valueerror(monkeypatch, mutate, match):
    from apps.scene_graph import pipeline

    _patch_registry(monkeypatch, {})
    run = _make_run()
    mutate(run)
    with pytest.raises(ValueError, match=match):
        pipeline.build_run_scene_graphs(ROOT, run)


def test_deterministic_same_run_same_graphs(monkeypatch):
    from apps.scene_graph import pipeline

    _patch_registry(monkeypatch, {})
    run_a = _make_run()
    run_b = copy.deepcopy(_make_run())
    graphs_a = pipeline.build_run_scene_graphs(ROOT, run_a)
    graphs_b = pipeline.build_run_scene_graphs(ROOT, run_b)

    assert graphs_a == graphs_b
    hashes_a = [g["provenance"]["graph_hash"] for g in graphs_a]
    hashes_b = [g["provenance"]["graph_hash"] for g in graphs_b]
    assert hashes_a == hashes_b
    assert len(set(hashes_a)) == len(hashes_a)  # mỗi segment một hash riêng
    # hash của nội dung run (trước khi gắn graph) ổn định theo đầu vào
    assert _run_hash(run_a) == _run_hash(run_b)


def test_asset_rights_human_scope_approved_pending_without(monkeypatch):
    from apps.scene_graph import pipeline
    from apps.scene_graph.schema import validate_scene_graph

    verified = {
        "asset-human": {
            "asset_id": "asset-human",
            "rights_state": "verified",
            "lifecycle_state": "active",
            "license_type": "CC BY 4.0",
            "purpose_code": "broll-generic",
            "rights_scope_json": _human_scope_json(),
        }
    }
    _patch_registry(monkeypatch, verified)
    # beat-1 (hook_card): co record co scope human-granted -> approved
    # beat-3 (media_b_roll): media_asset_id khong co record -> pending
    run = _make_run(media_asset_ids=["asset-human", None, "asset-missing"])
    graphs = pipeline.build_run_scene_graphs(ROOT, run)

    ref = graphs[0]["roles"]["hero_image"]
    assert ref["asset_id"] == "asset-human"
    assert ref["approval_status"] == "approved"
    assert ref["rights_scope"] == "human-granted:youtube,tiktok"
    assert ref["license_type"] == "CC BY 4.0"
    validate_scene_graph(graphs[0])

    ref = graphs[2]["roles"]["hero_image"]
    assert ref["asset_id"] == "asset-missing"
    assert ref["approval_status"] == "pending"
    assert ref["rights_scope"] == "rights-scope-missing"
    validate_scene_graph(graphs[2])


def test_asset_rights_deny_default_pending(monkeypatch):
    from apps.scene_graph import pipeline
    from apps.scene_graph.schema import validate_scene_graph
    from apps.asset_library.rights_scope import default_deny_scope

    deny = {
        "asset-deny": {
            "asset_id": "asset-deny",
            "rights_state": "verified",
            "lifecycle_state": "active",
            "license_type": "All Rights Reserved",
            "purpose_code": "broll-generic",
            # verified != duoc phep su dung: scope la deny-default
            "rights_scope_json": json.dumps(default_deny_scope()),
        }
    }
    _patch_registry(monkeypatch, deny)
    run = _make_run(media_asset_ids=["asset-deny", None, None])
    graphs = pipeline.build_run_scene_graphs(ROOT, run)

    ref = graphs[0]["roles"]["hero_image"]
    assert ref["asset_id"] == "asset-deny"
    assert ref["approval_status"] == "pending"
    assert ref["rights_scope"] == "deny-default"
    validate_scene_graph(graphs[0])


def test_asset_rights_missing_scope_pending(monkeypatch):
    from apps.scene_graph import pipeline
    from apps.scene_graph.schema import validate_scene_graph

    missing = {
        "asset-noscope": {
            "asset_id": "asset-noscope",
            "rights_state": "verified",
            "lifecycle_state": "active",
            "license_type": "CC BY 4.0",
            "purpose_code": "broll-generic",
            # khong co khoá rights_scope_json (registry cu / chua backfill)
        }
    }
    _patch_registry(monkeypatch, missing)
    run = _make_run(media_asset_ids=["asset-noscope", None, None])
    graphs = pipeline.build_run_scene_graphs(ROOT, run)

    ref = graphs[0]["roles"]["hero_image"]
    assert ref["asset_id"] == "asset-noscope"
    assert ref["approval_status"] == "pending"
    assert ref["rights_scope"] == "rights-scope-missing"
    validate_scene_graph(graphs[0])


def test_asset_rights_invalid_json_pending(monkeypatch):
    from apps.scene_graph import pipeline
    from apps.scene_graph.schema import validate_scene_graph

    bad = {
        "asset-badjson": {
            "asset_id": "asset-badjson",
            "rights_state": "verified",
            "lifecycle_state": "active",
            "license_type": "CC BY 4.0",
            "purpose_code": "broll-generic",
            "rights_scope_json": "{not valid json",
        }
    }
    _patch_registry(monkeypatch, bad)
    run = _make_run(media_asset_ids=["asset-badjson", None, None])
    graphs = pipeline.build_run_scene_graphs(ROOT, run)

    ref = graphs[0]["roles"]["hero_image"]
    assert ref["approval_status"] == "pending"
    assert ref["rights_scope"] == "rights-scope-missing"
    validate_scene_graph(graphs[0])


def test_fetch_asset_infos_selects_rights_scope_json(tmp_path):
    """_fetch_asset_infos doc cột rights_scope_json (không phải rights_scope)
    và tra row dict chua key nay khi co ton tai trong schema."""
    from apps.scene_graph import pipeline

    root = tmp_path / "proj"
    root.mkdir()
    db_path = root / "runtime" / "engine.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE assets ("
        "asset_id TEXT PRIMARY KEY, original_name TEXT NOT NULL, "
        "stored_path TEXT NOT NULL, asset_type TEXT NOT NULL, "
        "size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, "
        "source_type TEXT NOT NULL, rights_state TEXT NOT NULL, "
        "lifecycle_state TEXT NOT NULL, metadata_json TEXT NOT NULL, "
        "license_type TEXT, purpose_code TEXT, rights_scope_json TEXT)"
    )
    conn.execute(
        "INSERT INTO assets (asset_id, original_name, stored_path, asset_type, "
        "size_bytes, sha256, source_type, rights_state, lifecycle_state, "
        "metadata_json, license_type, purpose_code, rights_scope_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("a-1", "n", "p", "image", 1, "s", "x", "verified", "active", "{}",
         "CC BY 4.0", "broll", _human_scope_json()),
    )
    # schema_migrations o v4 de initialize_database khong chay migration_4
    # (ko them/backfill rights_scope_json, giu nguyen du lieu de test).
    conn.execute(
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, "
        "applied_at TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO schema_migrations VALUES (4, '2026-01-01')")
    conn.commit()
    conn.close()

    infos = pipeline._fetch_asset_infos(root, ["a-1"])
    assert "a-1" in infos
    assert infos["a-1"]["rights_scope_json"] == _human_scope_json()
    assert infos["a-1"]["asset_type"] == "image"
    assert "rights_scope" not in infos["a-1"]  # khong doc cot cu khong ton tai
    # Registry fixture is isolated under tmp_path; repo runtime may already exist.
    assert db_path.is_file()
    assert db_path.is_relative_to(tmp_path)


def test_fetch_asset_infos_old_registry_without_rights_scope_json(tmp_path):
    """Registry cu chua cot rights_scope_json: _fetch_asset_infos khong bi loi,
    tra row khong chua khoa nay, builder chuyen sang pending/rights-scope-missing."""
    from apps.scene_graph import pipeline
    from apps.scene_graph.builder import _asset_ref

    root = tmp_path / "proj2"
    root.mkdir()
    db_path = root / "runtime" / "engine.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE assets ("
        "asset_id TEXT PRIMARY KEY, original_name TEXT NOT NULL, "
        "stored_path TEXT NOT NULL, asset_type TEXT NOT NULL, "
        "size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, "
        "source_type TEXT NOT NULL, rights_state TEXT NOT NULL, "
        "lifecycle_state TEXT NOT NULL, metadata_json TEXT NOT NULL, "
        "license_type TEXT, purpose_code TEXT)"
    )
    conn.execute(
        "INSERT INTO assets (asset_id, original_name, stored_path, asset_type, "
        "size_bytes, sha256, source_type, rights_state, lifecycle_state, "
        "metadata_json, license_type, purpose_code) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("a-old", "n", "p", "image", 1, "s", "x", "verified", "active", "{}",
         "CC BY 4.0", "broll"),
    )
    conn.execute(
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, "
        "applied_at TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO schema_migrations VALUES (4, '2026-01-01')")
    conn.commit()
    conn.close()

    infos = pipeline._fetch_asset_infos(root, ["a-old"])
    assert "a-old" in infos
    assert "rights_scope_json" not in infos["a-old"]  # cot cu khong tra ve

    ref = _asset_ref("a-old", infos["a-old"])
    assert ref["approval_status"] == "pending"
    assert ref["rights_scope"] == "rights-scope-missing"
    assert ref["asset_id"] == "a-old"
    # Registry fixture is isolated under tmp_path; repo runtime may already exist.
    assert db_path.is_file()
    assert db_path.is_relative_to(tmp_path)


def test_tactical_blocks_passed_through_not_invented(monkeypatch):
    from apps.scene_graph import pipeline
    from apps.scene_graph.schema import validate_scene_graph

    _patch_registry(monkeypatch, {})
    diagram = {
        "players": [{"id": "P1", "team": "home", "x": 0.25, "y": 0.5}],
        "pass_vector": {"from": [0.25, 0.5], "to": [0.7, 0.5]},
        "run_vectors": [],
        "press_vectors": [],
    }
    segment_diagram = {
        "players": [{"id": "P2", "team": "away", "x": 0.8, "y": 0.2}],
        "pass_vector": {"from": [0.8, 0.2], "to": [0.2, 0.8]},
        "run_vectors": [],
        "press_vectors": [],
    }

    run = _make_run()
    # media_b_roll -> primitive graph co params dict (mirror cho executor)
    decision = run["card_plan"]["decisions"][0]
    decision["visual_mode"] = "media_b_roll"
    decision["starter_id"] = None
    decision["media_asset_id"] = None
    decision["tactical_diagram"] = diagram
    decision["media_caption"] = "Mo dau"
    decision["overlays"] = [{"type": "lower_third", "text": "Tin tuc",
                             "start_seconds": 2.0, "end_seconds": 7.0}]
    # segment override ghi de decision (theo contract builder)
    run["draft"]["segments"][0]["tactical_diagram"] = segment_diagram
    run["draft"]["segments"][0]["media_caption"] = "segment caption"

    graphs = pipeline.build_run_scene_graphs(ROOT, run)
    g = graphs[0]
    validate_scene_graph(g)
    assert g["kind"] == "primitive"
    assert g["tactical_diagram"] == segment_diagram  # segment override, khong tu bia
    assert g["media_caption"] == "segment caption"
    assert g["overlays"] == [{"type": "lower_third", "text": "Tin tuc",
                              "start_seconds": 2.0, "end_seconds": 7.0}]
    # primitive graph: params mirror cac block nay de executor doc
    assert g["params"]["tactical_diagram"] == segment_diagram
    assert g["params"]["media_caption"] == "segment caption"
    assert g["params"]["overlays"] == [{"type": "lower_third", "text": "Tin tuc",
                                        "start_seconds": 2.0, "end_seconds": 7.0}]

    # decision/starter graph khong co block nao -> keys duoc emit o gia tri None, graph van hop le
    g2 = graphs[1]
    assert g2["tactical_diagram"] is None
    assert g2["media_caption"] is None
    assert g2["overlays"] is None
    validate_scene_graph(g2)


def test_beat_intent_carried_from_segment(monkeypatch):
    from apps.scene_graph import pipeline

    _patch_registry(monkeypatch, {})
    run = _make_run()
    run["draft"]["segments"][1]["beat_intent"] = {
        "image_goal": "compare_numbers",
        "focus_subject": "x so sanh y",
        "evidence_type": "sourced_stat",
        "emphasis_level": "hero",
    }
    graphs = pipeline.build_run_scene_graphs(ROOT, run)
    assert graphs[1]["provenance"]["beat_intent"]["image_goal"] == "compare_numbers"
    assert graphs[1]["provenance"]["beat_intent"]["focus_subject"] == "x so sanh y"


def test_no_runtime_created_when_registry_missing(tmp_path):
    from apps.scene_graph import pipeline

    empty_root = tmp_path / "proj"
    empty_root.mkdir()
    run = _make_run()
    graphs = pipeline.build_run_scene_graphs(empty_root, run)

    assert len(graphs) == 3
    assert not (empty_root / "runtime").exists()  # khong tao/sua duoi runtime
    for graph in graphs:
        ref = graph["roles"]["hero_image"]
        if ref is not None:
            assert ref["approval_status"] == "pending"


def test_fail_fast_invalid_graph_not_attached(monkeypatch):
    from apps.scene_graph import pipeline

    _patch_registry(monkeypatch, {})
    run = _make_run()

    def fake_build(decisions, *, segments_by_id=None, content_type="short",
                   template_version=None, asset_map=None):
        return [{"version": "1.0.0", "mode": "not_a_mode"}]

    monkeypatch.setattr(pipeline, "build_clip_graphs", fake_build)
    with pytest.raises(ValueError, match="unknown visual_mode"):
        pipeline.build_run_scene_graphs(ROOT, run)
    assert "scene_graphs" not in run["draft"]  # invalid graph khong duoc gan
