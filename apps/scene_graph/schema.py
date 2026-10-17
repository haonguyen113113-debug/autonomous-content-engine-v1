"""Versioned Scene Graph validator (planner/renderer contract).

A Scene Graph is the ONLY thing the renderer may execute. It freezes:
mode (planner-chosen), starter (planner-chosen), canvas, absolute layers
(boxes in pixels), timing, and provenance. The executor must call
``validate_scene_graph`` first and then render verbatim — no remapping.

Schema v1 additive blocks (optional on read, always emitted by the
builder): ``roles`` (hero_image/data_chart/player_focus/headline/source),
``motion``, ``transition``, and ``provenance`` (starter_id,
template_version, graph_hash). ``tactical_diagram`` (players +
pass/run/press vectors on the normalized 0..1 canvas), ``media_caption``,
and ``overlays`` are likewise optional top-level blocks, emitted on the
graph (and mirrored into primitive ``params``) and covered by
``graph_hash``. Legacy graphs without these blocks still validate;
graphs carrying them are checked strictly, including the deterministic
hash check when ``provenance.graph_hash`` is present.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from apps.scene_graph import SCENE_GRAPH_VERSION

try:  # Mirror the planner contract; never widen it here.
    from apps.content_workflow import VISUAL_MODES as _VISUAL_MODES

    SUPPORTED_MODES = frozenset(set(_VISUAL_MODES) | {"media_b_roll"})
except Exception:  # pragma: no cover - import-safe fallback
    SUPPORTED_MODES = frozenset({
        "tactical_explainer", "statline_scorecard", "source_card",
        "chart_comparison", "chart_timeline", "hook_card", "player_card",
        "comparison_duel", "stat_leader", "player_poster",
        "goal_card", "fixture_card", "score_card",
        "duel_columns", "player_poster_side", "player_poster_top",
        "fixture_list", "quote_card", "potm_card",
        "discipline_card", "welcome_card", "media_b_roll",
    })

SHORT_CANVAS = (1080, 1920)
LONG_CANVAS = (1920, 1080)

_KINDS = ("starter", "primitive")

# Planner motion/transition vocabulary. Values map 1:1 onto the locked
# template pack's timeline language (timeline.motion + timeline.effects +
# timeline.transitions); the renderer executes them verbatim, never remaps.
MOTION_ENTERS = frozenset({
    "hook_punch_in",       # beat-0 hook punch (template: hook stagger 0.18s)
    "slide_in_right_0_3s",  # template motion.scene_enter
    "fade_0_3s",            # b-roll beds only
})
MOTION_EFFECTS = frozenset({
    "none", "freeze_and_trace", "number_pop", "pitch_grid",
})
TRANSITION_INS = frozenset({"clean_cut", "chalk_line_wipe"})
TRANSITION_OUTS = frozenset({"clean_cut"})

APPROVAL_STATUSES = frozenset({"approved", "pending"})
ASSET_KINDS = frozenset({"library_image", "monogram_fallback", "none"})


def is_supported_mode(mode: str) -> bool:
    return str(mode) in SUPPORTED_MODES


def _need_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"scene graph: '{name}' must be a number")
    return float(value)


def canonical_json(graph: dict[str, Any]) -> str:
    """Canonical form for hashing: sorted keys, compact separators."""
    return json.dumps(graph, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_payload(graph: dict[str, Any]) -> dict[str, Any]:
    """Hash input: every frozen field except the hash itself."""
    payload = dict(graph)
    provenance = payload.get("provenance")
    if isinstance(provenance, dict):
        provenance = {k: v for k, v in provenance.items() if k != "graph_hash"}
        payload["provenance"] = provenance
    return payload


def graph_hash(graph: dict[str, Any]) -> str:
    """Deterministic sha256 over the canonical payload.

    Same input + same template version -> same hash. Any post-freeze edit
    (headline, timing, design, motion, ...) changes the hash, which
    ``validate_scene_graph`` rejects loudly when a hash is recorded.
    """
    if not isinstance(graph, dict):
        raise ValueError("scene graph must be an object")
    digest = hashlib.sha256(
        canonical_json(_hash_payload(graph)).encode("utf-8")
    ).hexdigest()
    return digest


def _check_asset_ref(ref: Any, name: str) -> None:
    if not isinstance(ref, dict):
        raise ValueError(f"scene graph: roles.{name} must be an object or null")
    kind = ref.get("kind")
    if kind not in ASSET_KINDS:
        raise ValueError(
            f"scene graph: roles.{name}.kind must be one of "
            f"{sorted(ASSET_KINDS)}, got {kind!r}"
        )
    if kind == "library_image":
        asset_id = ref.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise ValueError(
                f"scene graph: roles.{name}.asset_id must be a non-empty string"
            )
    rights_scope = ref.get("rights_scope")
    if not isinstance(rights_scope, str) or not rights_scope.strip():
        raise ValueError(
            f"scene graph: roles.{name}.rights_scope must be a non-empty string "
            f"(Rights/Discovery workstream owns the vocabulary; "
            f"'pending-rights-review' while unset)"
        )
    approval = ref.get("approval_status")
    if approval not in APPROVAL_STATUSES:
        raise ValueError(
            f"scene graph: roles.{name}.approval_status must be one of "
            f"{sorted(APPROVAL_STATUSES)}, got {approval!r}"
        )


def _check_roles(roles: Any) -> None:
    if not isinstance(roles, dict):
        raise ValueError("scene graph: 'roles' must be an object when present")
    headline = roles.get("headline", "")
    source = roles.get("source", "")
    if not isinstance(headline, str):
        raise ValueError("scene graph: roles.headline must be a string")
    if not isinstance(source, str):
        raise ValueError("scene graph: roles.source must be a string")
    for key in ("hero_image", "data_chart", "player_focus"):
        value = roles.get(key)
        if value is None:
            continue
        if key == "data_chart":
            if not isinstance(value, dict):
                raise ValueError("scene graph: roles.data_chart must be an object or null")
            if not isinstance(value.get("chart_kind"), str) or not value["chart_kind"].strip():
                raise ValueError("scene graph: roles.data_chart.chart_kind must be a non-empty string")
            if "values" in value and not isinstance(value["values"], (list, dict, str)):
                raise ValueError("scene graph: roles.data_chart.values must be list/dict/str when present")
            continue
        if key == "player_focus":
            if not isinstance(value, dict):
                raise ValueError("scene graph: roles.player_focus must be an object or null")
            if not isinstance(value.get("player_name"), str) or not value["player_name"].strip():
                raise ValueError("scene graph: roles.player_focus.player_name must be a non-empty string")
            portrait = value.get("portrait")
            if portrait is not None:
                _check_asset_ref(portrait, "player_focus.portrait")
            continue
        _check_asset_ref(value, key)


def _check_motion(motion: Any) -> None:
    if not isinstance(motion, dict):
        raise ValueError("scene graph: 'motion' must be an object when present")
    enter = motion.get("enter")
    if enter not in MOTION_ENTERS:
        raise ValueError(
            f"scene graph: motion.enter must be one of {sorted(MOTION_ENTERS)}, "
            f"got {enter!r}"
        )
    effect = motion.get("effect", "none")
    if effect not in MOTION_EFFECTS:
        raise ValueError(
            f"scene graph: motion.effect must be one of {sorted(MOTION_EFFECTS)}, "
            f"got {effect!r}"
        )
    for key in ("stagger_seconds", "count_up_steps"):
        if key in motion and motion[key] is not None:
            _need_number(motion[key], f"motion.{key}")


def _check_transition(transition: Any) -> None:
    if not isinstance(transition, dict):
        raise ValueError("scene graph: 'transition' must be an object when present")
    if transition.get("in") not in TRANSITION_INS:
        raise ValueError(
            f"scene graph: transition.in must be one of {sorted(TRANSITION_INS)}, "
            f"got {transition.get('in')!r}"
        )
    if transition.get("out") not in TRANSITION_OUTS:
        raise ValueError(
            f"scene graph: transition.out must be one of {sorted(TRANSITION_OUTS)}, "
            f"got {transition.get('out')!r}"
        )


def _check_xy(value: Any, name: str) -> tuple[float, float]:
    """Validate a normalized [x, y] pair: both numbers in [0.0, 1.0]."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(
            f"scene graph: '{name}' must be [x, y] with length 2, got {value!r}"
        )
    x, y = value[0], value[1]
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, (int, float))
        or not isinstance(y, (int, float))
    ):
        raise ValueError(f"scene graph: '{name}' coordinates must be numbers, got {value!r}")
    x, y = float(x), float(y)
    if not (0.0 <= x <= 1.0) or not (0.0 <= y <= 1.0):
        raise ValueError(
            f"scene graph: '{name}' coordinates must be in [0.0, 1.0], got {value!r}"
        )
    return x, y


def _check_coord(value: Any, name: str) -> float:
    """Validate a single normalized coordinate: a number in [0.0, 1.0]."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"scene graph: '{name}' must be a number in [0.0, 1.0], got {value!r}")
    value = float(value)
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"scene graph: '{name}' must be in [0.0, 1.0], got {value!r}")
    return value


def _check_vector(vector: Any, name: str) -> None:
    if not isinstance(vector, dict):
        raise ValueError(
            f"scene graph: '{name}' must be an object with 'from' and 'to', got {vector!r}"
        )
    if "from" not in vector or "to" not in vector:
        raise ValueError(
            f"scene graph: '{name}' must have both 'from' and 'to', got {vector!r}"
        )
    _check_xy(vector.get("from"), f"{name}.from")
    _check_xy(vector.get("to"), f"{name}.to")


def _check_tactical_diagram(tactical: Any) -> None:
    """Validate the optional tactical_diagram top-level block.

    Shape:
        {
          "players": [{"id": str, "team": str, "x": 0..1, "y": 0..1,
                       "role_label?: str}],
          "pass_vector": {"from": [x, y], "to": [x, y]},
          "run_vectors": [{"from": [x, y], "to": [x, y]}, ...],
          "press_vectors": [{"from": [x, y], "to": [x, y]}, ...]
        }
    """
    if not isinstance(tactical, dict):
        raise ValueError(
            f"scene graph: 'tactical_diagram' must be an object, got {tactical!r}"
        )
    for key in ("players", "pass_vector", "run_vectors", "press_vectors"):
        if key not in tactical:
            raise ValueError(f"scene graph: tactical_diagram missing required key '{key}'")
    players = tactical["players"]
    if not isinstance(players, list):
        raise ValueError("scene graph: tactical_diagram.players must be a list")
    for index, player in enumerate(players):
        if not isinstance(player, dict):
            raise ValueError(
                f"scene graph: tactical_diagram.players[{index}] must be an object"
            )
        for key in ("id", "team"):
            value = player.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"scene graph: tactical_diagram.players[{index}] '{key}' "
                    f"must be a non-empty string, got {value!r}"
                )
        _check_coord(player.get("x"), f"tactical_diagram.players[{index}].x")
        _check_coord(player.get("y"), f"tactical_diagram.players[{index}].y")
        role_label = player.get("role_label")
        if role_label is not None and not isinstance(role_label, str):
            raise ValueError(
                f"scene graph: tactical_diagram.players[{index}].role_label "
                f"must be a string when present, got {role_label!r}"
            )
    _check_vector(tactical["pass_vector"], "tactical_diagram.pass_vector")
    for key in ("run_vectors", "press_vectors"):
        vectors = tactical[key]
        if not isinstance(vectors, list):
            raise ValueError(
                f"scene graph: tactical_diagram.{key} must be a list, got {vectors!r}"
            )
        for index, vector in enumerate(vectors):
            _check_vector(vector, f"tactical_diagram.{key}[{index}]")


def _check_media_caption(caption: Any) -> None:
    if caption is not None and not isinstance(caption, str):
        raise ValueError(
            f"scene graph: 'media_caption' must be a string or null, got {caption!r}"
        )


def _check_overlays(overlays: Any) -> None:
    if not isinstance(overlays, list):
        raise ValueError(
            f"scene graph: 'overlays' must be a list when present, got {overlays!r}"
        )
    for index, item in enumerate(overlays):
        if not isinstance(item, dict):
            raise ValueError(f"scene graph: overlays[{index}] must be an object, got {item!r}")


def _check_provenance(provenance: Any, graph: dict[str, Any]) -> None:
    if not isinstance(provenance, dict):
        raise ValueError("scene graph: 'provenance' must be an object when present")
    if "starter_id" in provenance and provenance["starter_id"] != graph.get("starter_id"):
        raise ValueError("scene graph: provenance.starter_id must match graph starter_id")
    version = provenance.get("template_version")
    if version is not None and (not isinstance(version, str) or not version.strip()):
        raise ValueError("scene graph: provenance.template_version must be a non-empty string")
    recorded = provenance.get("graph_hash")
    if recorded is not None:
        if not isinstance(recorded, str) or len(recorded) != 64:
            raise ValueError("scene graph: provenance.graph_hash must be a 64-char hex digest")
        actual = graph_hash(graph)
        if recorded != actual:
            raise ValueError(
                "scene graph: provenance.graph_hash mismatch — "
                "the graph was edited after freezing; rebuild instead of patching"
            )


def validate_scene_graph(graph: dict[str, Any]) -> dict[str, Any]:
    """Validate a Scene Graph dict. Returns it unchanged when valid.

    Raises ValueError on any contract violation, including unknown
    visual modes (planner must never emit them; renderer must never
    silently remap them).
    """
    if not isinstance(graph, dict):
        raise ValueError("scene graph must be an object")
    if graph.get("version") != SCENE_GRAPH_VERSION:
        raise ValueError(
            f"scene graph version must be {SCENE_GRAPH_VERSION!r}, "
            f"got {graph.get('version')!r}"
        )
    mode = graph.get("mode")
    if not isinstance(mode, str) or mode not in SUPPORTED_MODES:
        raise ValueError(f"scene graph: unknown visual_mode {mode!r}")
    kind = graph.get("kind")
    if kind not in _KINDS:
        raise ValueError(f"scene graph: kind must be one of {_KINDS}, got {kind!r}")
    starter_id = graph.get("starter_id")
    if starter_id is not None and not isinstance(starter_id, str):
        raise ValueError("scene graph: 'starter_id' must be a string or null")
    canvas = graph.get("canvas")
    if not isinstance(canvas, dict):
        raise ValueError("scene graph: 'canvas' must be an object")
    width, height = canvas.get("width"), canvas.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        raise ValueError("scene graph: canvas width/height must be ints")
    if (width, height) not in (SHORT_CANVAS, LONG_CANVAS):
        raise ValueError(
            f"scene graph: canvas {(width, height)} must be "
            f"{SHORT_CANVAS} or {LONG_CANVAS}"
        )
    timing = graph.get("timing")
    if not isinstance(timing, dict):
        raise ValueError("scene graph: 'timing' must be an object")
    start = _need_number(timing.get("start"), "timing.start")
    end = _need_number(timing.get("end"), "timing.end")
    if not end > start:
        raise ValueError("scene graph: timing.end must be > timing.start")
    segment_id = graph.get("segment_id")
    if not isinstance(segment_id, str) or not segment_id.strip():
        raise ValueError("scene graph: 'segment_id' must be a non-empty string")
    design = graph.get("design")
    if kind == "starter":
        if not isinstance(design, dict):
            raise ValueError("scene graph: starter kind requires a 'design' object")
        if (design.get("width"), design.get("height")) != (width, height):
            raise ValueError("scene graph: design canvas must match graph canvas")
        pages = design.get("pages")
        if not isinstance(pages, list) or len(pages) != 1:
            raise ValueError("scene graph: design must have exactly 1 page")
        children = pages[0].get("children") if isinstance(pages[0], dict) else None
        if not isinstance(children, list) or not children:
            raise ValueError("scene graph: design page must have children")
        for child in children:
            if not isinstance(child, dict):
                raise ValueError("scene graph: every layer must be an object")
            for key in ("x", "y", "width", "height"):
                value = child.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(
                        f"scene graph: layer {child.get('id', '?')!r} "
                        f"'{key}' must be an absolute number"
                    )
    else:
        if design is not None:
            raise ValueError("scene graph: primitive kind must have design=null")
        if not isinstance(graph.get("params"), dict):
            raise ValueError("scene graph: primitive kind requires a 'params' object")
    segments = graph.get("segments")
    if segments is not None:
        if not isinstance(segments, dict):
            raise ValueError("scene graph: 'segments' must be an object when present")
        for element_id, parts in segments.items():
            if not isinstance(parts, list) or not parts:
                raise ValueError(
                    f"scene graph: segments[{element_id!r}] must be a non-empty list"
                )
            for part in parts:
                if not isinstance(part, dict):
                    raise ValueError("scene graph: every segment part must be an object")
                if not isinstance(part.get("text"), str):
                    raise ValueError("scene graph: segment part 'text' must be a string")
                if not isinstance(part.get("accent"), bool):
                    raise ValueError("scene graph: segment part 'accent' must be bool")
    # Additive v1 blocks: absent on legacy graphs (pass), strict when present.
    if "roles" in graph and graph["roles"] is not None:
        _check_roles(graph["roles"])
    if "motion" in graph and graph["motion"] is not None:
        _check_motion(graph["motion"])
    if "transition" in graph and graph["transition"] is not None:
        _check_transition(graph["transition"])
    if "provenance" in graph and graph["provenance"] is not None:
        _check_provenance(graph["provenance"], graph)
    if "tactical_diagram" in graph and graph["tactical_diagram"] is not None:
        _check_tactical_diagram(graph["tactical_diagram"])
    if "media_caption" in graph and graph["media_caption"] is not None:
        _check_media_caption(graph["media_caption"])
    if "overlays" in graph and graph["overlays"] is not None:
        _check_overlays(graph["overlays"])
    return graph


validate_or_raise = validate_scene_graph
validate = validate_scene_graph

__all__ = [
    "SCENE_GRAPH_VERSION",
    "SUPPORTED_MODES",
    "SHORT_CANVAS",
    "LONG_CANVAS",
    "MOTION_ENTERS",
    "MOTION_EFFECTS",
    "TRANSITION_INS",
    "TRANSITION_OUTS",
    "APPROVAL_STATUSES",
    "ASSET_KINDS",
    "is_supported_mode",
    "canonical_json",
    "graph_hash",
    "validate_scene_graph",
    "validate_or_raise",
    "validate",
]
