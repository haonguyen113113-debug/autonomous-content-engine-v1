"""Scene Graph v1 additive blocks: roles/motion/transition/provenance+hash.

Planner contract under test:
- LLM owns beat meaning only (image_goal/focus_subject/evidence_type/
  emphasis_level); composition comes from intent + approved assets + template.
- build_scene_graph()/build_from_decision()/build_clip_graphs() freeze
  roles{hero_image?, data_chart?, player_focus?, headline, source} +
  timing/motion/transition + provenance{starter_id, template_version,
  graph_hash}.
- validate() (renderer/QA gate) accepts legacy graphs, checks new blocks
  strictly, and rejects post-freeze edits via the hash.
- Asset refs always carry rights_scope + approval_status (approved only
  with a verified/active record; otherwise explicit pending placeholders).
"""

from __future__ import annotations

import inspect

import pytest


def _beat1_kwargs() -> dict:
    return {
        "segment_id": "beat-1",
        "visual_mode": "hook_card",
        "starter_id": "C-03",
        "graphic_data": {"hook_text": "Dem ac mong *Etihad*"},
        "evidence": ["ESPN 14/10/2026", "BBC Sport 14/10/2026"],
        "content_type": "short",
        "start_seconds": 0.0,
        "end_seconds": 9.0,
        "index": 0,
    }


def _clip6_decisions() -> list[dict]:
    # Mirrors runtime/runs/6cebedb10a9f.json card_plan (6 beats, clip 1).
    return [
        {"segment_id": "beat-1", "index": 0, "visual_mode": "hook_card",
         "starter_id": "C-03", "media_asset_id": None,
         "graphic_data": {"hook_text": "Dem ac mong *Etihad*"}},
        {"segment_id": "beat-2", "index": 1, "visual_mode": "score_card",
         "starter_id": "MR-03", "media_asset_id": None,
         "graphic_data": {"home": "Manchester City", "away": "Paris Saint-Germain",
                           "score": "2 - 4", "source": "ESPN", "date": "14/10/2026",
                           "context": "Champions League"}},
        {"segment_id": "beat-3", "index": 2, "visual_mode": "duel_columns",
         "starter_id": "C-07", "media_asset_id": None,
         "graphic_data": {"home": "Man City", "away": "PSG", "source": "ESPN",
                           "date": "14/10/2026",
                           "metrics": [{"label": "Ban thang ky vong",
                                        "home": "2.57", "away": "1.83"}]}},
        {"segment_id": "beat-4", "index": 3, "visual_mode": "goal_card",
         "starter_id": "MR-04", "media_asset_id": None,
         "graphic_data": {"hook_text": "Chin muoi chin *giay*", "score": "0 - 2",
                           "home": "Man City", "away": "PSG"}},
        {"segment_id": "beat-5", "index": 4, "visual_mode": "player_card",
         "starter_id": "C-04", "media_asset_id": None,
         "graphic_data": {"player_name": "Erling Haaland", "source": "ESPN",
                           "date": "14/10/2026",
                           "stats": [{"label": "Ban thang", "value": "2"}]}},
        {"segment_id": "beat-6", "index": 5, "visual_mode": "media_b_roll",
         "starter_id": None, "media_asset_id": "asset-3960da53eba5",
         "graphic_data": {"hook_text": "Nha vua *tien buoc*"}},
    ]


def _clip6_segments() -> dict[str, dict]:
    bounds = [(0.0, 9.0), (9.0, 18.0), (18.0, 27.0), (27.0, 36.0),
              (36.0, 45.0), (45.0, 59.0)]
    refs = [["ESPN 14/10/2026", "BBC Sport 14/10/2026"], ["ESPN 14/10/2026"],
            ["ESPN 14/10/2026"], ["PSG.fr 14/10/2026"], ["ESPN 14/10/2026"],
            ["AFP 15/10/2026"]]
    return {f"beat-{i + 1}": {"evidence_refs": refs[i],
                              "start_seconds": bounds[i][0],
                              "end_seconds": bounds[i][1]}
            for i in range(6)}


def test_beat1_roles_motion_transition_provenance():
    from apps.scene_graph import build_scene_graph, validate

    graph = build_scene_graph(**_beat1_kwargs())
    validate(graph)
    roles = graph["roles"]
    assert roles["headline"] == "Dem ac mong Etihad"  # stars stripped, never kept
    assert roles["source"] == "ESPN • 14/10/2026"
    assert roles["hero_image"] is None
    assert roles["data_chart"] is None
    assert roles["player_focus"] is None
    assert graph["motion"]["enter"] == "hook_punch_in"
    assert graph["transition"] == {"in": "clean_cut", "out": "clean_cut"}
    provenance = graph["provenance"]
    assert provenance["starter_id"] == "C-03"
    assert provenance["template_version"] == "12.0.0"
    assert len(provenance["graph_hash"]) == 64
    assert set(provenance["beat_intent"]) == {
        "image_goal", "focus_subject", "evidence_type", "emphasis_level"}


def test_deterministic_hash_same_input_same_version():
    from apps.scene_graph import build_scene_graph, graph_hash

    first = build_scene_graph(**_beat1_kwargs())
    second = build_scene_graph(**_beat1_kwargs())
    assert first == second
    assert first["provenance"]["graph_hash"] == graph_hash(first)
    other_version = build_scene_graph(**_beat1_kwargs(), template_version="13.0.0")
    assert other_version["provenance"]["graph_hash"] != first["provenance"]["graph_hash"]


def test_hash_tamper_rejected():
    import copy

    from apps.scene_graph import build_scene_graph, validate

    graph = build_scene_graph(**_beat1_kwargs())
    bad = copy.deepcopy(graph)
    bad["roles"]["headline"] = "Edited after freeze"
    with pytest.raises(ValueError, match="graph_hash mismatch"):
        validate(bad)


def test_legacy_graph_without_new_blocks_still_validates():
    from apps.scene_graph import build_scene_graph, validate

    graph = build_scene_graph(**_beat1_kwargs())
    legacy = {k: v for k, v in graph.items()
              if k not in ("roles", "motion", "transition", "provenance")}
    validate(legacy)  # backward compat: additive blocks are optional on read


def test_asset_rights_pending_by_default_approved_with_record():
    from apps.scene_graph import build_scene_graph, validate

    base = {"segment_id": "beat-6", "visual_mode": "media_b_roll",
            "starter_id": None, "graphic_data": {"hook_text": "Nha vua *tien buoc*"},
            "evidence": ["AFP 15/10/2026"], "content_type": "short",
            "start_seconds": 45.0, "end_seconds": 59.0, "index": 5,
            "media_asset_id": "asset-3960da53eba5"}
    pending = build_scene_graph(**base)
    validate(pending)
    ref = pending["roles"]["hero_image"]
    assert ref["asset_id"] == "asset-3960da53eba5"
    assert ref["rights_scope"] == "pending-rights-review"
    assert ref["approval_status"] == "pending"

    cleared = build_scene_graph(
        **base,
        asset_info={"rights_state": "verified", "lifecycle_state": "active",
                    "license_type": "CC BY 4.0", "purpose_code": "broll-generic"})
    validate(cleared)
    ref = cleared["roles"]["hero_image"]
    assert ref["approval_status"] == "approved"
    assert ref["license_type"] == "CC BY 4.0"


def test_player_focus_monogram_fallback_without_media():
    from apps.scene_graph import build_scene_graph, validate

    graph = build_scene_graph(
        segment_id="beat-5", visual_mode="player_card", starter_id="C-04",
        graphic_data={"player_name": "Erling Haaland", "source": "ESPN",
                      "date": "14/10/2026",
                      "stats": [{"label": "Ban thang", "value": "2"}]},
        evidence=["ESPN 14/10/2026"], start_seconds=36.0, end_seconds=45.0,
        index=4)
    validate(graph)
    focus = graph["roles"]["player_focus"]
    assert focus["player_name"] == "Erling Haaland"
    assert focus["portrait"]["kind"] == "monogram_fallback"
    assert focus["portrait"]["approval_status"] == "approved"
    assert graph["roles"]["hero_image"] is None  # portrait lives in player_focus only
    assert graph["roles"]["data_chart"]["chart_kind"] == "player_stats"
    assert "Haaland" in graph["roles"]["headline"]


def test_clip_transition_budget_max_two_chalk():
    from apps.scene_graph.builder import build_clip_graphs
    from apps.scene_graph.schema import validate_scene_graph

    decisions = [
        {"segment_id": f"beat-{i + 1}", "index": i,
         "visual_mode": "tactical_explainer", "starter_id": None,
         "graphic_data": {}, "media_asset_id": None}
        for i in range(5)
    ]
    graphs = build_clip_graphs(decisions, content_type="long")
    for graph in graphs:
        validate_scene_graph(graph)
    ins = [g["transition"]["in"] for g in graphs]
    assert ins[0] == "clean_cut"  # beat-0 invariant
    assert ins.count("chalk_line_wipe") == 2
    assert {g["segment_id"] for g in graphs if g["transition"]["in"] == "chalk_line_wipe"} == {
        "beat-2", "beat-3"}


def test_beat0_always_clean_even_with_explicit_chalk():
    from apps.scene_graph import build_scene_graph

    graph = build_scene_graph(
        segment_id="beat-1", visual_mode="tactical_explainer", starter_id=None,
        graphic_data={}, evidence=[], index=0, transition_in="chalk_line_wipe")
    assert graph["transition"] == {"in": "clean_cut", "out": "clean_cut"}


def test_clip6_all_beats_build_validate_deterministically():
    from apps.scene_graph.builder import build_clip_graphs
    from apps.scene_graph.schema import validate_scene_graph

    first = build_clip_graphs(_clip6_decisions(), _clip6_segments(), content_type="short")
    second = build_clip_graphs(_clip6_decisions(), _clip6_segments(), content_type="short")
    assert len(first) == 6
    assert first == second
    for graph in first:
        validate_scene_graph(graph)
    by_id = {g["segment_id"]: g for g in first}
    assert by_id["beat-2"]["roles"]["headline"] == "Manchester City 2–4 Paris Saint-Germain"
    assert by_id["beat-2"]["motion"]["effect"] == "number_pop"
    assert by_id["beat-3"]["roles"]["data_chart"]["chart_kind"] == "duel_bars"
    assert by_id["beat-6"]["kind"] == "primitive"
    assert by_id["beat-6"]["roles"]["hero_image"]["approval_status"] == "pending"
    assert by_id["beat-6"]["motion"]["enter"] == "fade_0_3s"


def test_llm_limited_to_beat_meaning():
    from apps.content_workflow import _clean_segment, _outline_beat, _ollama_beat

    source = inspect.getsource(_ollama_beat)
    for key in ("image_goal", "focus_subject", "evidence_type", "emphasis_level"):
        assert key in source
    assert "Do NOT choose layout" in source

    segment = _clean_segment({
        "id": "beat-2",
        "narration": "Mot nhan dinh co nguon cu the ve tran dau hom qua.",
        "visual": "Host analysis",
        "visual_mode": "hook_card",
        "graphic_data": {"hook_text": "Dem ac mong *Etihad*"},
        "beat_intent": {"image_goal": "bogus", "emphasis_level": "maximum"},
        "duration_seconds": 8,
    })
    assert segment is not None
    assert segment["beat_intent"] == {
        "image_goal": "establish_moment",  # deterministic fallback, never garbage
        "focus_subject": "",
        "evidence_type": "sourced_quote",
        "emphasis_level": "standard",
    }

    outline = _outline_beat("Chu de", ["a", "b", "c"], 0, 45)
    assert set(outline["beat_intent"]) == {
        "image_goal", "focus_subject", "evidence_type", "emphasis_level"}


def _tactical_diagram() -> dict:
    return {
        "players": [
            {"id": "P1", "team": "home", "x": 0.25, "y": 0.5, "role_label": "ST"},
            {"id": "P2", "team": "away", "x": 0.7, "y": 0.5},
        ],
        "pass_vector": {"from": [0.25, 0.5], "to": [0.7, 0.5]},
        "run_vectors": [{"from": [0.25, 0.5], "to": [0.4, 0.6]}],
        "press_vectors": [{"from": [0.7, 0.5], "to": [0.75, 0.45]}],
    }


def _tactical_kwargs(**overrides: Any) -> dict:
    kw = {
        "segment_id": "beat-t1",
        "visual_mode": "tactical_explainer",
        "starter_id": None,
        "graphic_data": {},
        "evidence": [],
        "content_type": "short",
        "start_seconds": 0.0,
        "end_seconds": 5.0,
        "index": 0,
    }
    kw.update(overrides)
    return kw


def test_tactical_diagram_emitted_on_graph_and_params():
    from apps.scene_graph import build_scene_graph, validate

    diagram = _tactical_diagram()
    graph = build_scene_graph(
        **_tactical_kwargs(),
        tactical_diagram=diagram,
        media_caption="Cao dien da san",
        overlays=[{"kind": "lower_third", "text": "Tin tuc"}],
    )
    validate(graph)
    assert graph["tactical_diagram"] == diagram
    assert graph["media_caption"] == "Cao dien da san"
    assert graph["overlays"] == [{"kind": "lower_third", "text": "Tin tuc"}]
    # Primitive graph: params mirror so the executor can read them.
    assert graph["kind"] == "primitive"
    assert graph["params"]["tactical_diagram"] == diagram
    assert graph["params"]["media_caption"] == "Cao dien da san"
    assert graph["params"]["overlays"] == [{"kind": "lower_third", "text": "Tin tuc"}]
    # Hash covers the new blocks (builder emits before freeze).
    from apps.scene_graph import graph_hash

    assert graph["provenance"]["graph_hash"] == graph_hash(graph)


def test_tactical_diagram_on_starter_graph_emitted_top_level_only():
    from apps.scene_graph import build_scene_graph, validate

    diagram = _tactical_diagram()
    graph = build_scene_graph(
        segment_id="beat-t2",
        visual_mode="hook_card",
        starter_id="C-03",
        graphic_data={"hook_text": "Dem ac mong *Etihad*"},
        evidence=["ESPN 14/10/2026"],
        index=0,
        tactical_diagram=diagram,
    )
    validate(graph)
    assert graph["tactical_diagram"] == diagram
    assert graph["media_caption"] is None
    assert graph["overlays"] is None
    # Starter graphs carry params=None; top-level fields are the source.
    assert graph["params"] is None


def test_tactical_diagram_tamper_rejected_by_graph_hash():
    import copy

    from apps.scene_graph import build_scene_graph, validate

    graph = build_scene_graph(
        **_tactical_kwargs(), tactical_diagram=_tactical_diagram())
    bad = copy.deepcopy(graph)
    bad["tactical_diagram"]["players"][0]["x"] = 0.9  # shape stays valid
    with pytest.raises(ValueError, match="graph_hash mismatch"):
        validate(bad)


def test_graph_without_tactical_blocks_still_validates():
    from apps.scene_graph import build_scene_graph, validate

    graph = build_scene_graph(
        segment_id="beat-t3",
        visual_mode="hook_card",
        starter_id="C-03",
        graphic_data={"hook_text": "x *y*"},
        evidence=["ESPN 14/10/2026"],
        index=0,
    )
    # Builder emits the keys with None; validator skips None values.
    validate(graph)
    assert graph["tactical_diagram"] is None
    assert graph["media_caption"] is None
    assert graph["overlays"] is None
    # Truly legacy graph: keys absent entirely (and provenance hash with
    # them) still validates — backward compat.
    legacy = {k: v for k, v in graph.items()
              if k not in ("tactical_diagram", "media_caption", "overlays", "provenance")}
    validate(legacy)


@pytest.mark.parametrize(
    "bad_kwargs, match",
    [
        # Coordinates out of [0.0, 1.0].
        ({"tactical_diagram": {**_tactical_diagram(),
                                "players": [{**_tactical_diagram()["players"][0],
                                             "x": 1.5}]}},
         r"\[0\.0, 1\.0\]"),
        # Missing player id.
        ({"tactical_diagram": {**_tactical_diagram(),
                                "players": [{k: v for k, v in _tactical_diagram()["players"][0].items()
                                            if k != "id"}]}},
         "'id'"),
        # Missing player team.
        ({"tactical_diagram": {**_tactical_diagram(),
                                "players": [{k: v for k, v in _tactical_diagram()["players"][0].items()
                                            if k != "team"}]}},
         "'team'"),
        # Missing player x coordinate.
        ({"tactical_diagram": {**_tactical_diagram(),
                                "players": [{k: v for k, v in _tactical_diagram()["players"][0].items()
                                            if k != "x"}]}},
         r"\[0\.0, 1\.0\]"),
        # pass_vector missing 'from'.
        ({"tactical_diagram": {**_tactical_diagram(),
                                "pass_vector": {"to": [0.7, 0.5]}}},
         r"both 'from' and 'to'"),
        # pass_vector 'from' with wrong length.
        ({"tactical_diagram": {**_tactical_diagram(),
                                "pass_vector": {"from": [0.25], "to": [0.7, 0.5]}}},
         "length 2"),
        # run_vector end outside [0, 1].
        ({"tactical_diagram": {**_tactical_diagram(),
                                "run_vectors": [{"from": [0.25, 0.5], "to": [2.0, 0.6]}]}},
         r"\[0\.0, 1\.0\]"),
        # role_label must be a string.
        ({"tactical_diagram": {**_tactical_diagram(),
                                "players": [{**_tactical_diagram()["players"][0],
                                             "role_label": 7}]}},
         "role_label"),
        # Missing required top-level key.
        ({"tactical_diagram": {k: v for k, v in _tactical_diagram().items()
                               if k != "press_vectors"}},
         "missing required key"),
        # media_caption must be str or None.
        ({"media_caption": 123}, "media_caption"),
        # overlays must be a list.
        ({"overlays": "not-a-list"}, "overlays"),
        # Each overlay must be a dict.
        ({"overlays": [{"k": 1}, "nope"]}, r"overlays\[1\]"),
    ],
)
def test_validator_rejects_bad_tactical_and_media_blocks(bad_kwargs, match):
    from apps.scene_graph import build_scene_graph
    from apps.scene_graph.schema import validate_scene_graph

    graph = build_scene_graph(**_tactical_kwargs(), **bad_kwargs)
    with pytest.raises(ValueError, match=match):
        validate_scene_graph(graph)


def test_build_from_decision_carries_tactical_blocks():
    from apps.scene_graph import build_from_decision, validate

    diagram = _tactical_diagram()
    decision = {
        "segment_id": "beat-d1",
        "visual_mode": "media_b_roll",
        "starter_id": None,
        "graphic_data": {"hook_text": "q"},
        "tactical_diagram": diagram,
        "media_caption": "Caption tu decision",
        "overlays": [{"kind": "overlay", "text": "x"}],
    }
    graph = build_from_decision(decision, evidence=[])
    validate(graph)
    assert graph["tactical_diagram"] == diagram
    assert graph["media_caption"] == "Caption tu decision"
    assert graph["overlays"] == [{"kind": "overlay", "text": "x"}]
    assert graph["params"]["tactical_diagram"] == diagram


def test_build_clip_graphs_passes_segment_tactical_blocks():
    from apps.scene_graph import build_clip_graphs
    from apps.scene_graph.schema import validate_scene_graph

    diagram = _tactical_diagram()
    decisions = [
        {"segment_id": "beat-s1", "index": 0, "visual_mode": "media_b_roll",
         "starter_id": None, "graphic_data": {},
         "tactical_diagram": {"players": [], "pass_vector": {"from": [0, 0], "to": [0, 0]},
                              "run_vectors": [], "press_vectors": []},
         "media_caption": "decision-cap"},
    ]
    segments = {"beat-s1": {"tactical_diagram": diagram,
                            "media_caption": "segment-cap",
                            "overlays": [{"kind": "o"}],
                            "start_seconds": 0.0, "end_seconds": 5.0}}
    graphs = build_clip_graphs(decisions, segments, content_type="short")
    from apps.scene_graph.schema import validate_scene_graph

    validate_scene_graph(graphs[0])
    # Segment overrides decision when present.
    assert graphs[0]["tactical_diagram"] == diagram
    assert graphs[0]["media_caption"] == "segment-cap"
    assert graphs[0]["overlays"] == [{"kind": "o"}]
    assert graphs[0]["params"]["tactical_diagram"] == diagram


def test_pack_version_pin_matches_released_pack():
    from pathlib import Path

    from apps.scene_graph.builder import TEMPLATE_VERSION_FALLBACK
    from template_foundation import resolve_template

    package = resolve_template(Path("."), "allen-knows-ball.shortform-analyst",
                               allow_draft=True)
    assert TEMPLATE_VERSION_FALLBACK == package.manifest["version"] == "12.0.0"


def test_rejects_unknown_mode_and_bad_transition():
    from apps.scene_graph import build_scene_graph

    with pytest.raises(ValueError, match="unknown visual_mode"):
        build_scene_graph(segment_id="b", visual_mode="not_a_mode",
                          starter_id=None, graphic_data={}, evidence=[])
    with pytest.raises(ValueError, match="transition_in"):
        build_scene_graph(segment_id="b", visual_mode="hook_card",
                          starter_id="C-03", graphic_data={"hook_text": "x y z w v"},
                          evidence=[], transition_in="star_wipe")
