"""Versioned Scene Graph validator (planner/renderer contract).

A Scene Graph is the ONLY thing the renderer may execute. It freezes:
mode (planner-chosen), starter (planner-chosen), canvas, absolute layers
(boxes in pixels), timing, and provenance. The executor must call
``validate_scene_graph`` first and then render verbatim — no remapping.

Schema v1 additive blocks (optional on read, always emitted by the
builder): ``roles`` (hero_image/data_chart/player_focus/headline/source),
``motion``, ``transition``, and ``provenance`` (starter_id,
template_version, graph_hash). ``media_bindings`` (frozen card-media slots
with their authored box/fit/mask/approval; covered by ``graph_hash``),
``tactical_diagram`` (players + pass/run/press vectors on the normalized
0..1 canvas), ``media_caption``, and ``overlays`` are likewise optional
top-level blocks, emitted on the graph (the last three are also mirrored
into primitive ``params``) and covered by ``graph_hash``. Legacy graphs
without these blocks still validate; graphs carrying them are checked
strictly, including the deterministic hash check when
``provenance.graph_hash`` is present.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
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

# Card-media contract vocabulary (authored regions for variable library media).
MEDIA_BINDING_STATUSES = frozenset({"bound", "fallback"})
MEDIA_ASSET_TYPES = frozenset({"image", "video"})
MEDIA_FITS = frozenset({"cover", "contain"})
MEDIA_MASK_SHAPES = frozenset({"rounded_rect", "none"})
MEDIA_BINDING_KEYS = frozenset({
    "slot_id", "role", "asset_type", "layer_id", "box_norm", "box_px",
    "fit", "focal_point", "mask", "min_source_px", "rights", "qa", "status",
    "reason", "proposed_asset_id", "asset",
})
MEDIA_QA_KEYS = frozenset({"min_painted_fraction", "max_outside_leak_pixels"})

CONTRACT_STATUSES = frozenset({
    "contract", "fallback", "legacy_non_ready",
    "missing_contract_record", "no_contract",
})
CONTRACT_ROUTES = frozenset({
    "starter_design", "legacy_generic", "legacy_long", "frame_legacy",
})
DATA_BINDING_KEYS = frozenset({
    "slot_id", "layer_id", "value", "visible", "active", "required",
    "sources", "fallback",
})

# Overlay preset types and roles (planner/renderer contract). Geometry,
# typography, and colors come from these finite presets; payloads may not add
# per-overlay layout or styling fields.
OVERLAY_TYPES = frozenset({"lower_third", "caption"})
OVERLAY_ROLES = {
    "lower_third": frozenset({"name_tag"}),
    "caption": frozenset({"hook"}),
}
OVERLAY_KEYS = frozenset({
    "type", "text", "start_seconds", "end_seconds", "role",
})


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


def _check_overlays(overlays: Any, timing: Any = None) -> None:
    """Kiểm tra nghiêm ngặt danh sách overlay theo contract overlay/caption.

    Mỗi overlay (thời gian clip-relative so với đầu beat):
        {
            "type": "lower_third" | "caption",  # required
            "text": str,                         # required, non-empty
            "start_seconds": float,              # required, >= 0
            "end_seconds": float,                # required, > start_seconds
            "role": str,                         # optional preset role
        }
    Thời gian là clip-relative so với đầu beat (0 = đầu beat). Khi timing
    có sẵn, start_seconds/end_seconds không được vượt quá
    beat_duration = timing.end - timing.start.
    """
    if not isinstance(overlays, list):
        raise ValueError(
            f"scene graph: 'overlays' must be a list when present, got {overlays!r}"
        )
    for index, item in enumerate(overlays):
        prefix = f"overlays[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"scene graph: {prefix} must be an object, got {item!r}")
        extra_keys = set(item) - OVERLAY_KEYS
        if extra_keys:
            raise ValueError(
                f"scene graph: {prefix} has unsupported keys {sorted(extra_keys)!r}"
            )
        otype = item.get("type")
        if otype not in OVERLAY_TYPES:
            raise ValueError(
                f"scene graph: {prefix}.type must be one of {sorted(OVERLAY_TYPES)}, "
                f"got {otype!r}"
            )
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"scene graph: {prefix}.text must be a non-empty string")
        start = _need_number(item.get("start_seconds"), f"{prefix}.start_seconds")
        if start < 0:
            raise ValueError(
                f"scene graph: {prefix}.start_seconds must be >= 0, got {start}"
            )
        end = _need_number(item.get("end_seconds"), f"{prefix}.end_seconds")
        if not end > start:
            raise ValueError(
                f"scene graph: {prefix}.end_seconds must be > start_seconds "
                f"({end} <= {start})"
            )
        if isinstance(timing, dict):
            try:
                beat_start = float(timing.get("start"))
                beat_end = float(timing.get("end"))
            except (TypeError, ValueError):
                beat_start = beat_end = None
        else:
            beat_start = beat_end = None
        if beat_start is not None and beat_end is not None and beat_end > beat_start:
            duration = beat_end - beat_start
            if start > duration:
                raise ValueError(
                    f"scene graph: {prefix} starts after the beat window "
                    f"({start} > {duration})"
                )
            if end > duration:
                raise ValueError(
                    f"scene graph: {prefix} ends after the beat window "
                    f"({end} > {duration})"
                )
        role = item.get("role")
        if role is not None and not isinstance(role, str):
            raise ValueError(f"scene graph: {prefix}.role must be a string when present")
        if role is not None and role not in OVERLAY_ROLES[otype]:
            raise ValueError(
                f"scene graph: {prefix}.role {role!r} is not supported for {otype!r}; "
                f"expected one of {sorted(OVERLAY_ROLES[otype])!r} or null"
            )


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


def _media_layers(design: Any) -> dict[str, dict[str, Any]]:
    """Media-slot layers declared by the frozen starter design, keyed by slot."""
    layers: dict[str, dict[str, Any]] = {}
    if not isinstance(design, dict):
        return layers
    pages = design.get("pages")
    children = pages[0].get("children") if isinstance(pages, list) and pages \
        and isinstance(pages[0], dict) else None
    if not isinstance(children, list):
        return layers
    for child in children:
        if not isinstance(child, dict) or child.get("type") != "media_slot":
            continue
        custom = child.get("custom") if isinstance(child.get("custom"), dict) else {}
        slot_id = custom.get("slot_id")
        if not isinstance(slot_id, str) or not slot_id.strip():
            raise ValueError(
                "scene graph: every media_slot layer needs custom.slot_id"
            )
        if slot_id in layers:
            raise ValueError(
                f"scene graph: duplicate media_slot layer for {slot_id!r}"
            )
        layers[slot_id] = child
    return layers


def _check_media_bindings(bindings: Any, graph: dict[str, Any]) -> None:
    """Validate frozen media bindings against the authored starter layers.

    A binding is executable data: the renderer may paint only ``bound``
    entries, and only with an ``approved`` library_image ref. A ``fallback``
    must carry no asset (the authored pack artwork remains). Geometry, fit,
    focal point, mask and QA thresholds must match the frozen ``media_slot``
    layer byte-for-byte; a post-freeze edit is rejected here.
    """
    if not isinstance(bindings, list):
        raise ValueError("scene graph: 'media_bindings' must be a list")
    if graph.get("kind") != "starter":
        raise ValueError("scene graph: media_bindings require a starter graph")
    canvas = graph.get("canvas") if isinstance(graph.get("canvas"), dict) else {}
    width = int(canvas.get("width", 0))
    height = int(canvas.get("height", 0))
    layers = _media_layers(graph.get("design"))
    seen: set[str] = set()
    for index, binding in enumerate(bindings):
        prefix = f"media_bindings[{index}]"
        if not isinstance(binding, dict):
            raise ValueError(f"scene graph: {prefix} must be an object")
        extra = set(binding) - MEDIA_BINDING_KEYS
        if extra:
            raise ValueError(
                f"scene graph: {prefix} has unsupported keys {sorted(extra)}"
            )
        slot_id = binding.get("slot_id")
        if not isinstance(slot_id, str) or not slot_id.strip():
            raise ValueError(f"scene graph: {prefix}.slot_id must be a non-empty string")
        if slot_id in seen:
            raise ValueError(f"scene graph: duplicate media binding {slot_id!r}")
        seen.add(slot_id)
        role = binding.get("role")
        if not isinstance(role, str) or not role.strip():
            raise ValueError(f"scene graph: {prefix}.role must be a non-empty string")
        asset_type = binding.get("asset_type")
        if asset_type not in MEDIA_ASSET_TYPES:
            raise ValueError(
                f"scene graph: {prefix}.asset_type must be one of "
                f"{sorted(MEDIA_ASSET_TYPES)}"
            )
        layer_id = binding.get("layer_id")
        expected_layer_id = f"media-{slot_id}"
        if layer_id != expected_layer_id:
            raise ValueError(
                f"scene graph: {prefix}.layer_id must be {expected_layer_id!r}, "
                f"got {layer_id!r}"
            )
        box_norm = binding.get("box_norm")
        if not isinstance(box_norm, list) or len(box_norm) != 4:
            raise ValueError(f"scene graph: {prefix}.box_norm must be [x, y, w, h]")
        norm = [_need_number(value, f"{prefix}.box_norm") for value in box_norm]
        if not all(0.0 <= value <= 1.0 for value in norm):
            raise ValueError(f"scene graph: {prefix}.box_norm values must be in [0, 1]")
        if norm[2] <= 0.0 or norm[3] <= 0.0:
            raise ValueError(f"scene graph: {prefix}.box_norm width/height must be > 0")
        box_px = binding.get("box_px")
        if not isinstance(box_px, list) or len(box_px) != 4:
            raise ValueError(f"scene graph: {prefix}.box_px must be [x, y, w, h]")
        pixels: list[int] = []
        for value in box_px:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"scene graph: {prefix}.box_px must be integers")
            pixels.append(value)
        x, y, w, h = pixels
        if w <= 0 or h <= 0:
            raise ValueError(f"scene graph: {prefix}.box_px width/height must be > 0")
        if x < 0 or y < 0 or x + w > width or y + h > height:
            raise ValueError(
                f"scene graph: {prefix}.box_px {pixels} is outside the "
                f"{width}x{height} canvas"
            )
        if binding.get("fit") not in MEDIA_FITS:
            raise ValueError(
                f"scene graph: {prefix}.fit must be one of {sorted(MEDIA_FITS)}"
            )
        _check_xy(binding.get("focal_point"), f"{prefix}.focal_point")
        mask = binding.get("mask")
        if not isinstance(mask, dict) or mask.get("shape") not in MEDIA_MASK_SHAPES:
            raise ValueError(
                f"scene graph: {prefix}.mask.shape must be one of "
                f"{sorted(MEDIA_MASK_SHAPES)}"
            )
        radii = mask.get("corner_radii_px", [0, 0, 0, 0])
        if not isinstance(radii, list) or len(radii) != 4:
            raise ValueError(
                f"scene graph: {prefix}.mask.corner_radii_px must be "
                "[tl, tr, br, bl]"
            )
        for radius in radii:
            if isinstance(radius, bool) or not isinstance(radius, int) or radius < 0:
                raise ValueError(
                    f"scene graph: {prefix}.mask.corner_radii_px values must be "
                    "integers >= 0"
                )
        min_source = binding.get("min_source_px")
        if not isinstance(min_source, list) or len(min_source) != 2:
            raise ValueError(f"scene graph: {prefix}.min_source_px must be [w, h]")
        for value in min_source:
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(
                    f"scene graph: {prefix}.min_source_px values must be "
                    "integers >= 1"
                )
        qa = binding.get("qa")
        if not isinstance(qa, dict) or set(qa) != MEDIA_QA_KEYS:
            raise ValueError(
                f"scene graph: {prefix}.qa must contain exactly "
                f"{sorted(MEDIA_QA_KEYS)}"
            )
        fraction = _need_number(
            qa.get("min_painted_fraction"), f"{prefix}.qa.min_painted_fraction"
        )
        if not 0.0 <= fraction <= 1.0:
            raise ValueError(
                f"scene graph: {prefix}.qa.min_painted_fraction must be in [0, 1]"
            )
        leak = qa.get("max_outside_leak_pixels")
        if isinstance(leak, bool) or not isinstance(leak, int) or leak < 0:
            raise ValueError(
                f"scene graph: {prefix}.qa.max_outside_leak_pixels must be "
                "an integer >= 0"
            )
        status = binding.get("status")
        if status not in MEDIA_BINDING_STATUSES:
            raise ValueError(
                f"scene graph: {prefix}.status must be one of "
                f"{sorted(MEDIA_BINDING_STATUSES)}"
            )
        proposed = binding.get("proposed_asset_id")
        if proposed is not None and (
            not isinstance(proposed, str) or not proposed.strip()
        ):
            raise ValueError(
                f"scene graph: {prefix}.proposed_asset_id must be a "
                "non-empty string or null"
            )
        reason = binding.get("reason")
        asset = binding.get("asset")
        if status == "bound":
            if not isinstance(asset, dict):
                raise ValueError(
                    f"scene graph: bound {prefix} must carry an asset ref"
                )
            _check_asset_ref(asset, f"media_bindings[{slot_id}].asset")
            if asset.get("kind") != "library_image":
                raise ValueError(
                    f"scene graph: {prefix}.asset.kind must be 'library_image'"
                )
            if asset.get("approval_status") != "approved":
                raise ValueError(
                    f"scene graph: {prefix}.asset must be approved before it "
                    "can be bound for painting"
                )
            if reason is not None:
                raise ValueError(
                    f"scene graph: bound {prefix} must not carry a fallback reason"
                )
            if proposed is not None and asset.get("asset_id") != proposed:
                raise ValueError(
                    f"scene graph: {prefix}.asset.asset_id must match "
                    "proposed_asset_id"
                )
        else:
            if asset is not None:
                raise ValueError(
                    f"scene graph: fallback {prefix} must not carry an asset"
                )
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(
                    f"scene graph: fallback {prefix} needs a non-empty reason"
                )
        layer = layers.get(slot_id)
        if layer is None:
            raise ValueError(
                f"scene graph: {prefix} has no frozen media_slot layer "
                f"{expected_layer_id!r} in the design"
            )
        custom = layer.get("custom") if isinstance(layer.get("custom"), dict) else {}
        if custom.get("slot_id") != slot_id:
            raise ValueError(
                f"scene graph: {expected_layer_id!r} custom.slot_id must be "
                f"{slot_id!r}"
            )
        layer_box = [layer.get("x"), layer.get("y"), layer.get("width"), layer.get("height")]
        if layer_box != pixels:
            raise ValueError(
                f"scene graph: {prefix}.box_px {pixels} disagrees with frozen "
                f"layer box {layer_box}"
            )
    undeclared = set(layers) - seen
    if undeclared:
        raise ValueError(
            "scene graph: media_slot layer(s) without a frozen binding: "
            f"{sorted(undeclared)}"
        )


def _layer_box(layer: dict[str, Any]) -> list[int]:
    return [
        int(round(float(layer.get(key, 0))))
        for key in ("x", "y", "width", "height")
    ]


def _design_children(graph: dict[str, Any]) -> list[dict[str, Any]]:
    design = graph.get("design")
    if not isinstance(design, dict):
        return []
    pages = design.get("pages")
    if not isinstance(pages, list) or not pages or not isinstance(pages[0], dict):
        return []
    children = pages[0].get("children")
    return children if isinstance(children, list) else []


def _starter_children(record: dict[str, Any]) -> list[dict[str, Any]]:
    from apps.file_digest import file_digest
    from apps.studio_templates.card_media import ROOT as media_root

    path = Path(media_root) / "apps" / "studio_templates" / record["starter_file"]
    try:
        payload = path.read_bytes()
        data = json.loads(payload.decode("utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(
            f"scene graph: cannot read contract starter {path}: {error}"
        ) from error
    if file_digest(path) != record["starter_sha256"]:
        raise ValueError(
            "scene graph: contract starter drifted from the frozen hash; "
            "rebuild instead of patching"
        )
    children = data.get("pages", [{}])[0].get("children")
    return children if isinstance(children, list) else []


def _check_contract_meta(
    meta: Any,
    graph: dict[str, Any],
    record: dict[str, Any] | None,
    version: str | None,
) -> str:
    if not isinstance(meta, dict):
        raise ValueError("scene graph: provenance.card_contract must be an object")
    allowed = {
        "id", "schema_version", "template_version", "sha256", "card_id",
        "starter_sha256", "route", "status", "reason",
    }
    extra = set(meta) - allowed
    if extra:
        raise ValueError(
            f"scene graph: provenance.card_contract has unsupported keys "
            f"{sorted(extra)}"
        )
    if meta.get("id") != "card-contract":
        raise ValueError(
            "scene graph: provenance.card_contract.id must be 'card-contract'"
        )
    status = meta.get("status")
    if status not in CONTRACT_STATUSES:
        raise ValueError(
            f"scene graph: card contract status must be one of "
            f"{sorted(CONTRACT_STATUSES)}, got {status!r}"
        )
    route = meta.get("route")
    if route not in CONTRACT_ROUTES:
        raise ValueError(
            f"scene graph: card contract route must be one of "
            f"{sorted(CONTRACT_ROUTES)}, got {route!r}"
        )
    if meta.get("card_id") != graph.get("starter_id"):
        raise ValueError(
            "scene graph: card contract card_id must match graph starter_id"
        )
    if version is not None and meta.get("template_version") != version:
        raise ValueError(
            "scene graph: card contract template_version must match provenance"
        )
    reason = meta.get("reason")
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        raise ValueError("scene graph: card contract reason must be non-empty")
    if status == "contract":
        if reason is not None:
            raise ValueError("scene graph: contract status must not carry a reason")
        if graph.get("kind") != "starter":
            raise ValueError("scene graph: contract status requires a starter graph")
        if route != "starter_design":
            raise ValueError(
                "scene graph: contract status requires route='starter_design'"
            )
        if record is None:
            raise ValueError(
                "scene graph: contract status names a card with no contract record"
            )
        if graph.get("mode") not in record["execution"]["modes"]:
            raise ValueError(
                "scene graph: graph mode is not contract-executable for this card"
            )
    else:
        if not reason:
            raise ValueError(
                "scene graph: non-contract card status needs a reason"
            )
        if status == "fallback":
            if graph.get("kind") != "primitive":
                raise ValueError("scene graph: fallback status requires primitive")
            if route != "starter_design":
                raise ValueError(
                    "scene graph: fallback status requires route='starter_design'"
                )
            if record is None:
                raise ValueError(
                    "scene graph: fallback status names a card with no contract record"
                )
            if graph.get("mode") not in record["execution"]["modes"]:
                raise ValueError(
                    "scene graph: fallback mode is not contract-executable"
                )
            if not isinstance(graph.get("fallback"), str) or not graph["fallback"].strip():
                raise ValueError(
                    "scene graph: fallback status requires graph.fallback reason"
                )
        elif status == "legacy_non_ready":
            if graph.get("kind") != "primitive":
                raise ValueError(
                    "scene graph: legacy_non_ready must be a primitive graph"
                )
            if record is None:
                raise ValueError(
                    "scene graph: legacy_non_ready names a missing record"
                )
            if graph.get("mode") in record["execution"]["modes"]:
                raise ValueError(
                    "scene graph: contract-executable mode marked legacy"
                )
        elif status == "missing_contract_record":
            if graph.get("kind") != "primitive":
                raise ValueError(
                    "scene graph: missing_contract_record must be primitive"
                )
            if record is not None:
                raise ValueError(
                    "scene graph: missing_contract_record but the record exists"
                )
        elif status == "no_contract":
            if record is not None:
                raise ValueError(
                    "scene graph: no_contract but a contract record exists"
                )
    if status in ("contract", "fallback", "legacy_non_ready"):
        if record is None:
            raise ValueError(
                "scene graph: card contract record is missing for this status"
            )
        if meta.get("schema_version") != record["contract_schema_version"]:
            raise ValueError("scene graph: card contract schema_version drifted")
        digest = meta.get("sha256")
        if digest != record["contract_hash"]:
            raise ValueError(
                "scene graph: card contract hash does not match the current "
                "contract; rebuild instead of patching"
            )
        if meta.get("starter_sha256") != record["starter_sha256"]:
            raise ValueError(
                "scene graph: card contract starter hash does not match"
            )
    return str(status)


def _check_data_bindings(
    bindings: Any, graph: dict[str, Any], record: dict[str, Any]
) -> dict[str, str]:
    if not isinstance(bindings, list):
        raise ValueError("scene graph: 'data_bindings' must be a list")
    contract_slots = {
        str(slot["slot_id"]): slot for slot in record["data_slots"]
    }
    seen: set[str] = set()
    visible: dict[str, str] = {}
    visible_layers: dict[str, str] = {}
    for index, binding in enumerate(bindings):
        prefix = f"data_bindings[{index}]"
        if not isinstance(binding, dict):
            raise ValueError(f"scene graph: {prefix} must be an object")
        extra = set(binding) - DATA_BINDING_KEYS
        if extra:
            raise ValueError(
                f"scene graph: {prefix} has unsupported keys {sorted(extra)}"
            )
        slot_id = binding.get("slot_id")
        if not isinstance(slot_id, str) or not slot_id.strip():
            raise ValueError(f"scene graph: {prefix}.slot_id must be a string")
        if slot_id in seen:
            raise ValueError(
                f"scene graph: duplicate data binding {slot_id!r}"
            )
        seen.add(slot_id)
        slot = contract_slots.get(slot_id)
        if slot is None:
            raise ValueError(
                f"scene graph: {prefix} names undeclared slot {slot_id!r}"
            )
        if binding.get("layer_id") != slot["layer_id"]:
            raise ValueError(
                f"scene graph: {prefix}.layer_id must be {slot['layer_id']!r}"
            )
        for key in ("visible", "active", "required"):
            if not isinstance(binding.get(key), bool):
                raise ValueError(f"scene graph: {prefix}.{key} must be bool")
        active = graph.get("mode") in slot["active_modes"]
        required = graph.get("mode") in slot["required_for_modes"]
        if binding["active"] is not active:
            raise ValueError(
                f"scene graph: {prefix}.active disagrees with the contract"
            )
        if binding["required"] is not required:
            raise ValueError(
                f"scene graph: {prefix}.required disagrees with the contract"
            )
        if binding.get("sources") != slot["sources"]:
            raise ValueError(
                f"scene graph: {prefix}.sources disagree with the contract"
            )
        if binding.get("fallback") != slot["fallback"]:
            raise ValueError(
                f"scene graph: {prefix}.fallback disagrees with the contract"
            )
        value = binding.get("value")
        if not isinstance(value, str):
            raise ValueError(f"scene graph: {prefix}.value must be a string")
        is_visible = binding["visible"]
        if is_visible and not value.strip():
            raise ValueError(
                f"scene graph: {prefix} is visible but has no value"
            )
        if not is_visible and value != "":
            raise ValueError(
                f"scene graph: hidden {prefix} must carry an empty value"
            )
        if is_visible and not active:
            raise ValueError(
                f"scene graph: {prefix} cannot be visible in an inactive mode"
            )
        if required and not is_visible:
            raise ValueError(
                f"scene graph: required slot {slot_id!r} is not visible"
            )
        if is_visible:
            visible[slot_id] = value
            visible_layers[str(slot["layer_id"])] = value

    if seen != set(contract_slots):
        missing = sorted(set(contract_slots) - seen)
        extra = sorted(seen - set(contract_slots))
        raise ValueError(
            "scene graph: data_bindings must cover exactly the contract slots; "
            f"missing={missing} extra={extra}"
        )

    graph_slots = graph.get("slots")
    if not isinstance(graph_slots, dict):
        raise ValueError("scene graph: starter graph must freeze 'slots'")
    if set(graph_slots) != set(visible):
        raise ValueError(
            "scene graph: frozen slots must contain exactly the visible data "
            f"slots; missing={sorted(set(visible) - set(graph_slots))} "
            f"extra={sorted(set(graph_slots) - set(visible))}"
        )
    for slot_id, value in visible.items():
        if graph_slots.get(slot_id) != value:
            raise ValueError(
                f"scene graph: slots[{slot_id!r}] disagrees with data binding"
            )
    return visible_layers


def _check_contract_design(
    graph: dict[str, Any],
    record: dict[str, Any],
    bindings: list[dict[str, Any]],
) -> dict[str, str]:
    design_children = _design_children(graph)
    starter_children = _starter_children(record)
    design_by_id: dict[str, dict[str, Any]] = {}
    marker_layers: list[dict[str, Any]] = []
    for child in design_children:
        if not isinstance(child, dict):
            continue
        layer_id = str(child.get("id"))
        if layer_id.startswith(("dot-", "halo-")):
            # The planner hides baked sample markers and inserts winner markers
            # with the same deterministic names. They are decorative figures,
            # never text or pack art; validate them separately.
            marker_layers.append(child)
            continue
        if layer_id in design_by_id:
            raise ValueError(
                f"scene graph: duplicate design layer id {layer_id!r}"
            )
        design_by_id[layer_id] = child
    starter_by_id = {
        str(child.get("id")): child
        for child in starter_children
        if isinstance(child, dict)
        and not str(child.get("id")).startswith(("dot-", "halo-"))
    }
    starter_marker_ids = {
        str(child.get("id")) for child in starter_children
        if isinstance(child, dict)
        and str(child.get("id")).startswith(("dot-", "halo-"))
    }
    for layer_id, starter in starter_by_id.items():
        layer = design_by_id.get(layer_id)
        if layer is None:
            raise ValueError(
                f"scene graph: authored layer {layer_id!r} is missing from design"
            )
        if layer.get("type") != starter.get("type"):
            raise ValueError(
                f"scene graph: authored layer {layer_id!r} changed type"
            )
        if _layer_box(layer) != _layer_box(starter):
            raise ValueError(
                f"scene graph: authored layer {layer_id!r} moved/resized"
            )
        if layer.get("type") != "text":
            for key in ("subType", "fill", "opacity"):
                if layer.get(key) != starter.get(key):
                    raise ValueError(
                        f"scene graph: authored layer {layer_id!r} changed {key}"
                    )
    design_marker_ids = {str(layer.get("id")) for layer in marker_layers}
    missing_markers = starter_marker_ids - design_marker_ids
    if missing_markers:
        raise ValueError(
            "scene graph: authored marker(s) missing from design: "
            f"{sorted(missing_markers)}"
        )

    data_by_layer = {
        str(slot["layer_id"]): slot for slot in record["data_slots"]
    }
    static_by_layer = {
        str(layer["layer_id"]): layer
        for layer in record["static_text_layers"]
    }
    notes_by_layer = {
        str(note["layer_id"]): note for note in record["editor_notes"]
    }
    media_ids = {
        f"media-{slot['slot_id']}" for slot in record["media_slots"]
    }
    binding_by_slot = {
        str(binding["slot_id"]): binding for binding in bindings
    }
    visible_values: dict[str, str] = {}
    for layer_id, slot in data_by_layer.items():
        layer = design_by_id.get(layer_id)
        starter = starter_by_id.get(layer_id)
        if not isinstance(layer, dict) or not isinstance(starter, dict):
            raise ValueError(
                f"scene graph: data slot layer {layer_id!r} is missing"
            )
        if layer.get("type") != "text":
            raise ValueError(
                f"scene graph: data slot layer {layer_id!r} must be text"
            )
        if (layer.get("custom") or {}).get("slot") != slot["slot_id"]:
            raise ValueError(
                f"scene graph: data slot layer {layer_id!r} changed slot id"
            )
        for key in ("fontFamily", "fontWeight", "align"):
            if layer.get(key) != slot["font"][{
                "fontFamily": "family", "fontWeight": "weight", "align": "align",
            }[key]]:
                raise ValueError(
                    f"scene graph: data slot {slot['slot_id']!r} changed {key}"
                )
        size = layer.get("fontSize")
        if not isinstance(size, (int, float)) or isinstance(size, bool):
            raise ValueError(
                f"scene graph: data slot {slot['slot_id']!r} fontSize invalid"
            )
        if not slot["fit"]["min_size_px"] <= int(size) <= slot["font"]["size_px"]:
            raise ValueError(
                f"scene graph: data slot {slot['slot_id']!r} fontSize outside "
                "the authored fit range"
            )
        binding = binding_by_slot[slot["slot_id"]]
        visible = layer.get("showInExport") is not False
        if visible is not binding["visible"]:
            raise ValueError(
                f"scene graph: data slot {slot['slot_id']!r} visibility "
                "disagrees with its binding"
            )
        if visible:
            if str(layer.get("text", "")) != binding["value"]:
                raise ValueError(
                    f"scene graph: data slot {slot['slot_id']!r} text disagrees "
                    "with its binding"
                )
            visible_values[str(layer["id"])] = binding["value"]

    for layer_id, static in static_by_layer.items():
        layer = design_by_id.get(layer_id)
        starter = starter_by_id.get(layer_id)
        if not isinstance(layer, dict) or not isinstance(starter, dict):
            raise ValueError(f"scene graph: static layer {layer_id!r} is missing")
        if layer.get("type") != "text":
            raise ValueError(f"scene graph: static layer {layer_id!r} must be text")
        if str(layer.get("text", "")) != static["text"]:
            raise ValueError(
                f"scene graph: static layer {layer_id!r} text was changed"
            )
        if layer.get("showInExport") is False:
            raise ValueError(
                f"scene graph: static layer {layer_id!r} cannot be hidden"
            )
        for key in ("fontFamily", "fontWeight", "align"):
            if layer.get(key) != static["font"][{
                "fontFamily": "family", "fontWeight": "weight", "align": "align",
            }[key]]:
                raise ValueError(
                    f"scene graph: static layer {layer_id!r} changed {key}"
                )
        size = layer.get("fontSize")
        if not isinstance(size, (int, float)) or isinstance(size, bool):
            raise ValueError(
                f"scene graph: static layer {layer_id!r} fontSize invalid"
            )
        if not static["fit"]["min_size_px"] <= int(size) <= static["font"]["size_px"]:
            raise ValueError(
                f"scene graph: static layer {layer_id!r} fontSize outside range"
            )
        visible_values[layer_id] = static["text"]

    for layer_id, note in notes_by_layer.items():
        layer = design_by_id.get(layer_id)
        if not isinstance(layer, dict):
            raise ValueError(f"scene graph: editor note {layer_id!r} is missing")
        if str(layer.get("text", "")) != note["text"]:
            raise ValueError(
                f"scene graph: editor note {layer_id!r} text was changed"
            )
        if layer.get("showInExport") is not False:
            raise ValueError(
                f"scene graph: editor note {layer_id!r} must stay hidden"
            )

    visible_numeric_rows = {
        str(binding["layer_id"]) for binding in bindings
        if binding["visible"]
        and re.fullmatch(r"m-\d+-(home|away)", str(binding["slot_id"]))
    }
    for layer_id, layer in design_by_id.items():
        if layer_id in starter_by_id or layer_id in media_ids:
            continue
        raise ValueError(
            f"scene graph: undeclared layer {layer_id!r} was added to the design"
        )
    for layer in marker_layers:
        layer_id = str(layer.get("id"))
        if layer_id in starter_marker_ids:
            continue
        base = layer_id.split("-", 1)[1]
        if base not in visible_numeric_rows:
            raise ValueError(
                f"scene graph: generated marker {layer_id!r} has no visible row"
            )
        if layer.get("type") != "figure":
            raise ValueError(
                f"scene graph: generated marker {layer_id!r} must be a figure"
            )
    extra_text = {
        layer_id for layer_id, layer in design_by_id.items()
        if layer.get("type") == "text"
        and layer_id not in data_by_layer
        and layer_id not in static_by_layer
        and layer_id not in notes_by_layer
    }
    if extra_text:
        raise ValueError(
            "scene graph: undeclared text layer(s) were added to the design: "
            f"{sorted(extra_text)}"
        )
    return visible_values


def _check_contract_media(
    record: dict[str, Any],
    graph: dict[str, Any],
    bindings: Any,
) -> None:
    from apps.studio_templates.card_media import media_layer, slot_box_px

    contract_slots = {
        str(slot["slot_id"]): slot for slot in record["media_slots"]
    }
    if not contract_slots:
        if bindings != []:
            raise ValueError(
                "scene graph: card declares no media slots but bindings exist"
            )
        if _media_layers(graph.get("design")):
            raise ValueError(
                "scene graph: card declares no media slots but design has a "
                "media_slot layer"
            )
        return
    if not isinstance(bindings, list):
        raise ValueError(
            "scene graph: card declares media slots but has no media_bindings"
        )
    by_slot = {
        str(binding.get("slot_id")): binding
        for binding in bindings if isinstance(binding, dict)
    }
    if set(by_slot) != set(contract_slots):
        raise ValueError(
            "scene graph: media bindings must cover exactly the contract slots; "
            f"missing={sorted(set(contract_slots) - set(by_slot))} "
            f"extra={sorted(set(by_slot) - set(contract_slots))}"
        )
    canvas = (
        int(graph["canvas"]["width"]), int(graph["canvas"]["height"])
    )
    layers = _media_layers(graph.get("design"))
    for slot_id, slot in contract_slots.items():
        binding = by_slot[slot_id]
        for key in (
            "role", "asset_type", "box_norm", "fit", "focal_point", "mask",
            "min_source_px", "rights", "qa",
        ):
            if binding.get(key) != slot.get(key):
                raise ValueError(
                    f"scene graph: media binding {slot_id!r} changed {key}"
                )
        expected_px = slot_box_px(slot, canvas)
        if binding.get("box_px") != expected_px:
            raise ValueError(
                f"scene graph: media binding {slot_id!r} box disagrees with "
                "the contract"
            )
        expected_layer = media_layer(slot, canvas)
        layer = layers.get(slot_id)
        if layer is None:
            raise ValueError(
                f"scene graph: media layer for {slot_id!r} is missing"
            )
        for key in ("id", "type", "x", "y", "width", "height"):
            if layer.get(key) != expected_layer.get(key):
                raise ValueError(
                    f"scene graph: media layer {slot_id!r} changed {key}"
                )
        if (layer.get("custom") or {}) != (expected_layer.get("custom") or {}):
            raise ValueError(
                f"scene graph: media layer {slot_id!r} changed custom metadata"
            )


def _check_frozen_segments(
    graph: dict[str, Any], visible_values: dict[str, str]
) -> None:
    segments = graph.get("segments")
    if not isinstance(segments, dict):
        raise ValueError("scene graph: starter graph must freeze 'segments'")
    if set(segments) != set(visible_values):
        raise ValueError(
            "scene graph: segments must cover exactly the visible text layers; "
            f"missing={sorted(set(visible_values) - set(segments))} "
            f"extra={sorted(set(segments) - set(visible_values))}"
        )
    for layer_id, value in visible_values.items():
        parts = segments.get(layer_id)
        if not isinstance(parts, list) or not parts:
            raise ValueError(
                f"scene graph: segments[{layer_id!r}] must be a non-empty list"
            )
        joined = "".join(
            str(part.get("text", "")) for part in parts
            if isinstance(part, dict)
        )
        expected = re.sub(r"\*([^*]+)\*", r"\1", value)
        if joined != expected:
            raise ValueError(
                f"scene graph: segments[{layer_id!r}] do not match the frozen "
                "text value"
            )


def _check_card_contract(provenance: dict[str, Any], graph: dict[str, Any]) -> None:
    meta = provenance.get("card_contract")
    if meta is None:
        return
    from apps.studio_templates.card_media import card_contract, contract_hash

    version = provenance.get("template_version")
    record = card_contract(graph.get("starter_id"), version)
    status = _check_contract_meta(meta, graph, record, version)
    if status != "contract":
        return
    assert record is not None
    if contract_hash(version) != meta.get("sha256"):
        raise ValueError(
            "scene graph: card contract hash does not match the current contract"
        )
    data_visible = _check_data_bindings(
        graph.get("data_bindings"), graph, record
    )
    _check_contract_media(record, graph, graph.get("media_bindings"))
    # A graph without graph_hash is already unfrozen/legacy: QA and the
    # renderer must not treat it as ready, but inspection tools still need to
    # read it (e.g. to report clipping). Frozen graphs are held to the exact
    # authored geometry and text segments.
    if isinstance(provenance.get("graph_hash"), str):
        static_visible = _check_contract_design(
            graph, record, graph.get("data_bindings") or []
        )
        _check_frozen_segments(graph, {**data_visible, **static_visible})


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
    bindings = graph.get("media_bindings")
    if bindings is not None:
        _check_media_bindings(bindings, graph)
    elif kind == "starter":
        undeclared = _media_layers(design)
        if undeclared:
            raise ValueError(
                "scene graph: starter design carries media_slot layer(s) "
                f"{sorted(undeclared)} but no 'media_bindings' block"
            )
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
        _check_card_contract(graph["provenance"], graph)
    if "tactical_diagram" in graph and graph["tactical_diagram"] is not None:
        _check_tactical_diagram(graph["tactical_diagram"])
    if "media_caption" in graph and graph["media_caption"] is not None:
        _check_media_caption(graph["media_caption"])
    if "overlays" in graph and graph["overlays"] is not None:
        _check_overlays(graph["overlays"], graph.get("timing"))
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
