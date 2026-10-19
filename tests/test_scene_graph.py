"""Scene Graph boundary: planner picks, builder freezes, renderer executes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _tactical_graph(*, with_diagram: bool = True, index: int = 0,
                    content_type: str = "long"):
    from apps.scene_graph.builder import build_scene_graph

    diagram = {
        "players": [
            {"id": "1", "team": "possession", "x": 0.12, "y": 0.54,
             "role_label": "CB"},
            {"id": "5", "team": "press", "x": 0.25, "y": 0.51},
        ],
        "pass_vector": {"from": [0.12, 0.54], "to": [0.32, 0.34]},
        "run_vectors": [{"from": [0.48, 0.60], "to": [0.66, 0.38]}],
        "press_vectors": [{"from": [0.25, 0.51], "to": [0.12, 0.54]}],
    }
    kwargs = {
        "segment_id": f"beat-{index + 1}",
        "visual_mode": "tactical_explainer",
        "starter_id": None,
        "graphic_data": {},
        "evidence": [],
        "content_type": content_type,
        "start_seconds": 0.0,
        "end_seconds": 5.0,
        "index": index,
    }
    if with_diagram:
        kwargs["tactical_diagram"] = diagram
    return build_scene_graph(**kwargs), diagram


def _beat1_inputs() -> dict:
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


def test_build_deterministic_same_input_same_graph():
    from apps.scene_graph.builder import build_scene_graph

    kwargs = _beat1_inputs()
    first = build_scene_graph(**kwargs)
    second = build_scene_graph(**kwargs)
    assert first == second
    # JSON-serialized form is stable as well (sorted keys).
    assert (json.dumps(first, ensure_ascii=False, sort_keys=True)
            == json.dumps(second, ensure_ascii=False, sort_keys=True))
    assert first["version"] == "1.0.0"
    assert first["kind"] == "starter"
    assert first["mode"] == "hook_card"
    assert first["starter_id"] == "C-03"
    assert (first["canvas"]["width"], first["canvas"]["height"]) == (1080, 1920)
    assert first["design"] is not None
    assert (first["design"]["width"], first["design"]["height"]) == (1080, 1920)


def test_validator_rejects_unknown_mode():
    from apps.scene_graph.builder import build_scene_graph
    from apps.scene_graph.schema import validate_scene_graph

    graph = build_scene_graph(**_beat1_inputs())
    bad = dict(graph)
    bad["mode"] = "not_a_mode"
    try:
        validate_scene_graph(bad)
    except ValueError as error:
        assert "unknown visual_mode" in str(error)
    else:  # pragma: no cover
        raise AssertionError("validator accepted an unknown mode")


def test_executor_has_no_selector_import():
    path = ROOT / "apps" / "scene_graph" / "executor.py"
    text = path.read_text(encoding="utf-8")
    assert "card_selector" not in text


def test_beat1_graph_renders_short_canvas():
    from apps.scene_graph.builder import build_scene_graph
    from apps.scene_graph.executor import render_scene_graph
    from apps.scene_graph.schema import validate_scene_graph

    graph = build_scene_graph(**_beat1_inputs())
    validate_scene_graph(graph)
    image = render_scene_graph(graph)
    assert image.size == (1080, 1920)


def test_winner_first_puts_psg_on_top_for_beat2():
    # Clip 6cebedb10a9f beat-2: Man City 2 - 4 PSG -> away wins -> PSG on top.
    from apps.scene_graph.builder import build_scene_graph

    graph = build_scene_graph(
        segment_id="beat-2",
        visual_mode="score_card",
        starter_id="MR-03",
        graphic_data={
            "home": "Manchester City",
            "away": "Paris Saint-Germain",
            "score": "2 - 4",
            "source": "ESPN",
            "date": "14/10/2026",
            "context": "Champions League",
        },
        evidence=["ESPN 14/10/2026"],
        content_type="short",
        start_seconds=9.0,
        end_seconds=18.0,
        index=1,
    )
    assert graph["kind"] == "starter"
    assert graph["slots"]["home"] == "Paris Saint-Germain"
    assert graph["slots"]["score"] == "4"
    assert graph["slots"]["crest-winner"] == "PS"


def test_executor_has_no_diagram_specs_import():
    path = ROOT / "apps" / "scene_graph" / "executor.py"
    text = path.read_text(encoding="utf-8")
    assert "card_selector" not in text
    assert "_diagram_specs" not in text


def test_tactical_explainer_missing_diagram_raises_no_fallback():
    from apps.scene_graph.builder import build_scene_graph
    from apps.scene_graph.executor import render_scene_graph
    from apps.scene_graph.schema import validate_scene_graph

    graph, _ = _tactical_graph(with_diagram=False, index=2)
    validate_scene_graph(graph)  # the frozen graph itself is valid
    assert "tactical_diagram" not in graph or graph["tactical_diagram"] is None
    with pytest.raises(ValueError, match="tactical_diagram"):
        render_scene_graph(graph)


def test_tactical_explainer_reads_spec_from_graph_not_legacy_storyboard(
    monkeypatch: pytest.MonkeyPatch,
):
    from apps.scene_graph.executor import render_scene_graph
    from apps.scene_graph.schema import validate_scene_graph

    import apps.video_renderer as renderer

    graph, diagram = _tactical_graph(with_diagram=True, index=2)
    validate_scene_graph(graph)
    assert graph["tactical_diagram"] == diagram

    captured: dict = {}

    def fake_write_pitch(path, *, width, height, font_path, display_font_path,
                         palette, spec, is_long, scene_number, scene_count):
        captured["spec"] = spec
        from PIL import Image
        Image.new("RGB", (int(width), int(height))).save(path)

    monkeypatch.setattr(renderer, "_write_tactical_scene", fake_write_pitch)
    image = render_scene_graph(graph)

    assert captured["spec"] == diagram
    # Executor executes the frozen graph spec, not the legacy beat-index
    # storyboard (_specs()[index % 3]).
    assert captured["spec"] not in renderer._diagram_specs()
    assert image.size == (1920, 1080)
