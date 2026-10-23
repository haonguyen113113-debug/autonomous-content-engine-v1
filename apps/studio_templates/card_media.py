"""Unified per-card contract: authored text, media and execution route.

The contract (``card-contract.json``, schema 2.0) is part of the released
Template Foundation package. It declares, for every built card:

* ``data_slots`` — each authored text slot, its box/typography/fit limits and
  which planner value(s) may fill it (or that it must keep authored text /
  stay hidden);
* ``media_slots`` — the only authored variable-media regions (empty for cards
  that accept no variable media);
* ``execution`` — whether the Scene Graph starter path may execute the card,
  or the card is explicitly legacy/non-ready.

Boundary:
- The planner (``apps.scene_graph.builder``) reads the contract, maps data and
  freezes the exact text values, media bindings and contract hash into the
  Scene Graph.
- The renderer (``apps.video_renderer`` / ``apps.scene_graph.executor``) only
  draws the frozen layers and paints the asset named by a frozen binding into
  the frozen region. This module performs the deterministic technical
  fit/crop/mask operation; it never chooses a card, asset, region or wording.

No network, no clock, no randomness. Read-only.
"""

from __future__ import annotations

import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from apps.file_digest import file_digest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_FILENAME = "card-contract.json"
DEFAULT_TEMPLATE_VERSION = "12.2.0"
CONTRACT_SCHEMA_VERSION = "2.0"
CONTRACT_ID = "card-contract"
STARTER_DIR = ROOT / "apps" / "studio_templates"
GRAPHIC_TEMPLATES = (
    ROOT
    / "template_foundation"
    / "templates"
    / "allen-knows-ball"
    / DEFAULT_TEMPLATE_VERSION
    / "graphic-templates.json"
)

MASK_SHAPES = frozenset({"rounded_rect", "none"})
FITS = frozenset({"cover", "contain"})
EXECUTION_ROUTES = frozenset(
    {"starter_design", "legacy_generic", "legacy_long", "frame_legacy"}
)
EXECUTION_STATUSES = frozenset({"contract", "partial", "legacy_non_ready"})
FALLBACKS = frozenset({"hide", "authored_text"})
TEXT_ALIGNS = frozenset({"left", "center", "right"})


def contract_path(template_version: str | None = None) -> Path:
    version = str(template_version or DEFAULT_TEMPLATE_VERSION).strip()
    return (
        ROOT
        / "template_foundation"
        / "templates"
        / "allen-knows-ball"
        / version
        / CONTRACT_FILENAME
    )


def _need_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"card contract: '{name}' must be an object")
    return value


def _need_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"card contract: '{name}' must be a non-empty string")
    return value


def _need_int(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"card contract: '{name}' must be an integer >= {minimum}")
    return value


def _need_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"card contract: '{name}' must be a number")
    return float(value)


def _need_box_px(value: Any, name: str) -> list[int]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"card contract: '{name}' must be [x, y, w, h]")
    values = [
        _need_int(item, f"{name}[]", minimum=0) for item in value
    ]
    if values[2] <= 0 or values[3] <= 0:
        raise ValueError(f"card contract: '{name}' width/height must be > 0")
    return values


def _need_box_norm(value: Any, name: str) -> None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"card contract: '{name}' must be [x, y, w, h]")
    values = [_need_number(item, f"{name}[]") for item in value]
    if not all(0.0 <= item <= 1.0 for item in values):
        raise ValueError(f"card contract: '{name}' values must be in [0, 1]")
    if values[2] <= 0.0 or values[3] <= 0.0:
        raise ValueError(f"card contract: '{name}' width/height must be > 0")


def _need_font(value: Any, name: str) -> dict[str, Any]:
    font = _need_object(value, name)
    _need_str(font.get("family"), f"{name}.family")
    size = _need_int(font.get("size_px"), f"{name}.size_px", minimum=1)
    _need_str(font.get("weight"), f"{name}.weight")
    align = _need_str(font.get("align"), f"{name}.align")
    if align not in TEXT_ALIGNS:
        raise ValueError(
            f"card contract: '{name}.align' must be one of {sorted(TEXT_ALIGNS)}"
        )
    return {"size_px": size}


def _need_fit(value: Any, name: str, *, font_size: int) -> None:
    fit = _need_object(value, name)
    if fit.get("mode") != "shrink":
        raise ValueError(f"card contract: '{name}.mode' must be 'shrink'")
    minimum = _need_int(fit.get("min_size_px"), f"{name}.min_size_px", minimum=1)
    if minimum > font_size:
        raise ValueError(
            f"card contract: '{name}.min_size_px' must be <= font.size_px"
        )


def _need_string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"card contract: '{name}' must be a non-empty string list")
    if len(set(value)) != len(value):
        raise ValueError(f"card contract: '{name}' must not contain duplicates")
    return list(value)


def _canonical_hash(document: dict[str, Any]) -> str:
    payload = dict(document)
    payload.pop("contract_hash", None)
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    """Canonical digest: text artifacts are newline-normalised (see file_digest).

    Contract pins must not depend on the checkout's line endings, otherwise a
    contract generated on Windows fails every validation on an LF checkout.
    """
    return file_digest(path)


def _starter_box(child: dict[str, Any]) -> list[int]:
    values = [
        child.get("x", 0), child.get("y", 0),
        child.get("width", 0), child.get("height", 0),
    ]
    return [
        int(round(float(value))) if isinstance(value, (int, float)) else 0
        for value in values
    ]


def _starter_font(child: dict[str, Any]) -> dict[str, Any]:
    return {
        "family": str(child.get("fontFamily", "Be Vietnam Pro")),
        "size_px": int(child.get("fontSize", 40)),
        "weight": str(child.get("fontWeight", "normal")),
        "align": str(child.get("align", "left")),
    }


def _validate_media_slot(
    slot: Any, prefix: str, card_id: str, seen_slots: set[str]
) -> None:
    slot = _need_object(slot, prefix)
    slot_id = _need_str(slot.get("slot_id"), f"{prefix}.slot_id")
    if slot_id in seen_slots:
        raise ValueError(
            f"card contract: duplicate slot_id {slot_id!r} on {card_id}"
        )
    seen_slots.add(slot_id)
    _need_str(slot.get("role"), f"{prefix}.role")
    if slot.get("asset_type") not in ("image", "video"):
        raise ValueError(
            f"card contract: {prefix}.asset_type must be image/video"
        )
    if slot.get("subject_rule") is not None:
        _need_str(slot.get("subject_rule"), f"{prefix}.subject_rule")
    rights = _need_object(slot.get("rights"), f"{prefix}.rights")
    required_rights = {
        "requires_verified", "requires_active",
        "requires_persisted_human_grant", "purpose_specific",
        "human_review_required",
    }
    if set(rights) != required_rights:
        raise ValueError(
            f"card contract: {prefix}.rights must declare exactly "
            f"{sorted(required_rights)}"
        )
    for key in required_rights:
        if rights.get(key) is not True:
            raise ValueError(f"card contract: {prefix}.rights.{key} must be true")
    if not isinstance(slot.get("required"), bool):
        raise ValueError(f"card contract: {prefix}.required must be bool")
    _need_box_norm(slot.get("box_norm"), f"{prefix}.box_norm")
    if slot.get("fit") not in FITS:
        raise ValueError(
            f"card contract: {prefix}.fit must be one of {sorted(FITS)}"
        )
    focal = slot.get("focal_point")
    if not isinstance(focal, (list, tuple)) or len(focal) != 2:
        raise ValueError(f"card contract: {prefix}.focal_point must be [x, y]")
    fx, fy = (_need_number(item, f"{prefix}.focal_point[]") for item in focal)
    if not (0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0):
        raise ValueError(
            f"card contract: {prefix}.focal_point must be in [0, 1]"
        )
    mask = _need_object(slot.get("mask"), f"{prefix}.mask")
    if mask.get("shape") not in MASK_SHAPES:
        raise ValueError(
            f"card contract: {prefix}.mask.shape must be one of "
            f"{sorted(MASK_SHAPES)}"
        )
    radii = mask.get("corner_radii_px", [0, 0, 0, 0])
    if not isinstance(radii, list) or len(radii) != 4:
        raise ValueError(
            f"card contract: {prefix}.mask.corner_radii_px "
            "must be [tl, tr, br, bl]"
        )
    for radius_index, radius in enumerate(radii):
        _need_int(radius, f"{prefix}.mask.corner_radii_px[{radius_index}]")
    _need_str(slot.get("z_after_layer_id"), f"{prefix}.z_after_layer_id")
    min_source = slot.get("min_source_px", [1, 1])
    if not isinstance(min_source, list) or len(min_source) != 2:
        raise ValueError(f"card contract: {prefix}.min_source_px must be [w, h]")
    for size_index, size in enumerate(min_source):
        _need_int(size, f"{prefix}.min_source_px[{size_index}]", minimum=1)
    qa = _need_object(slot.get("qa"), f"{prefix}.qa")
    fraction = _need_number(
        qa.get("min_painted_fraction"), f"{prefix}.qa.min_painted_fraction"
    )
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(
            f"card contract: {prefix}.qa.min_painted_fraction must be in [0, 1]"
        )
    _need_int(
        qa.get("max_outside_leak_pixels"),
        f"{prefix}.qa.max_outside_leak_pixels",
    )
    fallback = _need_object(slot.get("fallback"), f"{prefix}.fallback")
    _need_str(fallback.get("behavior"), f"{prefix}.fallback.behavior")
    _need_str(fallback.get("reason"), f"{prefix}.fallback.reason")


def _validate_data_slot(
    slot: Any, prefix: str, card_id: str, modes: set[str],
    seen_slots: set[str], seen_layers: set[str]
) -> None:
    slot = _need_object(slot, prefix)
    slot_id = _need_str(slot.get("slot_id"), f"{prefix}.slot_id")
    layer_id = _need_str(slot.get("layer_id"), f"{prefix}.layer_id")
    if slot_id in seen_slots:
        raise ValueError(
            f"card contract: duplicate data slot_id {slot_id!r} on {card_id}"
        )
    if layer_id in seen_layers:
        raise ValueError(
            f"card contract: duplicate data layer_id {layer_id!r} on {card_id}"
        )
    seen_slots.add(slot_id)
    seen_layers.add(layer_id)
    _need_str(slot.get("role"), f"{prefix}.role")
    if slot.get("type") != "text":
        raise ValueError(f"card contract: '{prefix}.type' must be 'text'")

    active = slot.get("active_modes")
    if not isinstance(active, list) or not all(isinstance(m, str) for m in active):
        raise ValueError(f"card contract: '{prefix}.active_modes' must be a list")
    if len(set(active)) != len(active):
        raise ValueError(f"card contract: '{prefix}.active_modes' duplicates")
    if not set(active) <= modes:
        raise ValueError(
            f"card contract: '{prefix}.active_modes' names unknown mode(s)"
        )
    required_modes = slot.get("required_for_modes")
    if not isinstance(required_modes, list) or not all(
        isinstance(m, str) for m in required_modes
    ):
        raise ValueError(
            f"card contract: '{prefix}.required_for_modes' must be a list"
        )
    if len(set(required_modes)) != len(required_modes):
        raise ValueError(f"card contract: '{prefix}.required_for_modes' duplicates")
    if not set(required_modes) <= set(active):
        raise ValueError(
            f"card contract: '{prefix}.required_for_modes' must be active"
        )

    sources = slot.get("sources")
    if not isinstance(sources, list) or not all(
        isinstance(item, str) and item.strip() for item in sources
    ):
        raise ValueError(f"card contract: '{prefix}.sources' must be a string list")
    if len(set(sources)) != len(sources):
        raise ValueError(f"card contract: '{prefix}.sources' duplicates")
    join = slot.get("join")
    if join is not None:
        if not isinstance(join, str) or not join.strip():
            raise ValueError(
                f"card contract: '{prefix}.join' must be a non-empty string"
            )
        if len(sources) < 2:
            raise ValueError(
                f"card contract: '{prefix}.join' requires at least two sources"
            )
    transform = slot.get("transform")
    if transform not in (None, "upper"):
        raise ValueError(f"card contract: '{prefix}.transform' must be null/upper")
    fallback = slot.get("fallback")
    if fallback not in FALLBACKS:
        raise ValueError(
            f"card contract: '{prefix}.fallback' must be one of {sorted(FALLBACKS)}"
        )
    if not isinstance(slot.get("required"), bool):
        raise ValueError(f"card contract: '{prefix}.required' must be bool")
    if slot["required"] != bool(required_modes):
        raise ValueError(
            f"card contract: '{prefix}.required' must match required_for_modes"
        )

    box = _need_box_px(slot.get("box_px"), f"{prefix}.box_px")
    font = _need_font(slot.get("font"), f"{prefix}.font")
    _need_fit(slot.get("fit"), f"{prefix}.fit", font_size=font["size_px"])
    max_lines = _need_int(slot.get("max_lines"), f"{prefix}.max_lines", minimum=1)
    max_words = _need_int(slot.get("max_words"), f"{prefix}.max_words", minimum=1)
    max_chars = _need_int(slot.get("max_chars"), f"{prefix}.max_chars", minimum=1)
    validation = _need_object(slot.get("validation"), f"{prefix}.validation")
    if validation.get("non_empty") is not bool(required_modes):
        raise ValueError(
            f"card contract: '{prefix}.validation.non_empty' must match required"
        )
    if validation.get("max_chars") != max_chars:
        raise ValueError(
            f"card contract: '{prefix}.validation.max_chars' must match max_chars"
        )
    if validation.get("max_words") != max_words:
        raise ValueError(
            f"card contract: '{prefix}.validation.max_words' must match max_words"
        )
    if validation.get("max_lines") != max_lines:
        raise ValueError(
            f"card contract: '{prefix}.validation.max_lines' must match max_lines"
        )
    pattern = validation.get("pattern")
    if pattern is not None and not isinstance(pattern, str):
        raise ValueError(f"card contract: '{prefix}.validation.pattern' must be null/str")
    if not box:
        raise ValueError(f"card contract: '{prefix}.box_px' is invalid")


def _validate_static_layer(
    layer: Any, prefix: str, seen_layers: set[str]
) -> None:
    layer = _need_object(layer, prefix)
    layer_id = _need_str(layer.get("layer_id"), f"{prefix}.layer_id")
    if layer_id in seen_layers:
        raise ValueError(f"card contract: duplicate layer_id {layer_id!r}")
    seen_layers.add(layer_id)
    if not isinstance(layer.get("text"), str):
        raise ValueError(f"card contract: '{prefix}.text' must be a string")
    _need_box_px(layer.get("box_px"), f"{prefix}.box_px")
    font = _need_font(layer.get("font"), f"{prefix}.font")
    _need_fit(layer.get("fit"), f"{prefix}.fit", font_size=font["size_px"])


def _validate_card(raw_card: Any, index: int, template_version: str, canvas: dict[str, int]) -> None:
    prefix = f"cards[{index}]"
    card = _need_object(raw_card, prefix)
    card_id = _need_str(card.get("card_id"), f"{prefix}.card_id")
    starter_id = _need_str(card.get("starter_id"), f"{prefix}.starter_id")
    if starter_id != card_id:
        raise ValueError(
            f"card contract: {prefix}.starter_id must equal card_id "
            f"({starter_id!r} != {card_id!r})"
        )
    if card.get("aspect") not in ("short", "long"):
        raise ValueError(f"card contract: {prefix}.aspect must be short/long")
    card_canvas = _need_object(card.get("canvas"), f"{prefix}.canvas")
    card_width = _need_int(card_canvas.get("width"), f"{prefix}.canvas.width", minimum=1)
    card_height = _need_int(card_canvas.get("height"), f"{prefix}.canvas.height", minimum=1)
    expected_canvas = (1080, 1920) if card["aspect"] == "short" else (1920, 1080)
    if (card_width, card_height) != expected_canvas:
        raise ValueError(
            f"card contract: {prefix}.canvas must be "
            f"{expected_canvas[0]}x{expected_canvas[1]}"
        )
    if card.get("family") is not None:
        _need_str(card.get("family"), f"{prefix}.family")
    starter_file = _need_str(card.get("starter_file"), f"{prefix}.starter_file")
    if "/" in starter_file or "\\" in starter_file:
        raise ValueError(f"card contract: {prefix}.starter_file must be a filename")
    digest = _need_str(card.get("starter_sha256"), f"{prefix}.starter_sha256")
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError(f"card contract: {prefix}.starter_sha256 must be sha256")
    if card.get("template_version") != template_version:
        raise ValueError(f"card contract: {prefix}.template_version mismatch")
    modes = card.get("modes")
    if not isinstance(modes, list) or not modes or not all(
        isinstance(mode, str) and mode.strip() for mode in modes
    ):
        raise ValueError(f"card contract: {prefix}.modes must be a non-empty list")
    if len(set(modes)) != len(modes):
        raise ValueError(f"card contract: {prefix}.modes must not repeat")
    mode_set = set(modes)

    route = _need_object(card.get("renderer_route"), f"{prefix}.renderer_route")
    if route.get("kind") not in ("generic", "frame", "starter"):
        raise ValueError(f"card contract: {prefix}.renderer_route.kind invalid")
    if route.get("kind") == "generic":
        _need_str(route.get("mode"), f"{prefix}.renderer_route.mode")
    elif route.get("mode") is not None:
        raise ValueError(f"card contract: {prefix}.renderer_route.mode must be null")

    execution = _need_object(card.get("execution"), f"{prefix}.execution")
    if execution.get("route") not in EXECUTION_ROUTES:
        raise ValueError(f"card contract: {prefix}.execution.route invalid")
    if execution.get("status") not in EXECUTION_STATUSES:
        raise ValueError(f"card contract: {prefix}.execution.status invalid")
    exec_modes = execution.get("modes")
    legacy_modes = execution.get("legacy_modes")
    for name, value in (("modes", exec_modes), ("legacy_modes", legacy_modes)):
        if not isinstance(value, list) or not all(isinstance(m, str) for m in value):
            raise ValueError(f"card contract: {prefix}.execution.{name} must be list")
        if len(set(value)) != len(value):
            raise ValueError(f"card contract: {prefix}.execution.{name} repeats")
    if set(exec_modes) & set(legacy_modes):
        raise ValueError(f"card contract: {prefix}.execution modes overlap")
    if set(exec_modes) | set(legacy_modes) != mode_set:
        raise ValueError(
            f"card contract: {prefix}.execution modes must partition card modes"
        )
    if execution["route"] == "starter_design":
        if card["aspect"] != "short":
            raise ValueError(
                f"card contract: {prefix} starter execution must be short"
            )
        if execution["status"] not in ("contract", "partial"):
            raise ValueError(f"card contract: {prefix}.execution.status mismatch")
        if not exec_modes:
            raise ValueError(f"card contract: {prefix}.execution has no modes")
    else:
        if execution["status"] != "legacy_non_ready":
            raise ValueError(f"card contract: {prefix}.execution must be non-ready")
        if exec_modes:
            raise ValueError(f"card contract: {prefix}.execution modes must be empty")
    reason = execution.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise ValueError(f"card contract: {prefix}.execution.reason must be str/null")
    if execution["status"] != "contract" and not reason:
        raise ValueError(f"card contract: {prefix}.execution.reason required")

    if card.get("pack_layer_id") is not None:
        _need_str(card.get("pack_layer_id"), f"{prefix}.pack_layer_id")
    if not isinstance(card.get("data_slots"), list):
        raise ValueError(f"card contract: {prefix}.data_slots must be a list")
    if not isinstance(card.get("static_text_layers"), list):
        raise ValueError(f"card contract: {prefix}.static_text_layers must be a list")
    if not isinstance(card.get("editor_notes"), list):
        raise ValueError(f"card contract: {prefix}.editor_notes must be a list")
    if not isinstance(card.get("media_slots"), list):
        raise ValueError(f"card contract: {prefix}.media_slots must be a list")

    seen_slots: set[str] = set()
    seen_layers: set[str] = set()
    for slot_index, slot in enumerate(card["data_slots"]):
        _validate_data_slot(
            slot, f"{prefix}.data_slots[{slot_index}]", card_id,
            mode_set, seen_slots, seen_layers,
        )
    for layer_index, layer in enumerate(card["static_text_layers"]):
        _validate_static_layer(
            layer, f"{prefix}.static_text_layers[{layer_index}]", seen_layers
        )
    for note_index, note in enumerate(card["editor_notes"]):
        note = _need_object(note, f"{prefix}.editor_notes[{note_index}]")
        note_id = _need_str(
            note.get("layer_id"), f"{prefix}.editor_notes[{note_index}].layer_id"
        )
        if note_id in seen_layers:
            raise ValueError(
                f"card contract: editor note layer {note_id!r} collides"
            )
        seen_layers.add(note_id)
        if not isinstance(note.get("text"), str):
            raise ValueError(
                f"card contract: {prefix}.editor_notes[{note_index}].text invalid"
            )

    seen_media: set[str] = set()
    for slot_index, slot in enumerate(card["media_slots"]):
        _validate_media_slot(
            slot, f"{prefix}.media_slots[{slot_index}]", card_id, seen_media
        )
        box = slot.get("box_norm")
        _need_box_norm(box, "box_norm")
        x, y, w, h = (float(value) for value in box)
        if x + w > 1.0 + 1e-9 or y + h > 1.0 + 1e-9:
            raise ValueError(
                f"card contract: {prefix}.media_slots box exceeds canvas"
            )


def _starter_signature(template_version: str | None = None) -> str:
    grammar = contract_path(template_version).parent / "graphic-templates.json"
    if not grammar.is_file():
        grammar = GRAPHIC_TEMPLATES
    paths = sorted(STARTER_DIR.glob("*.short.json")) + sorted(
        STARTER_DIR.glob("*.long.json")
    )
    parts = [str(grammar.stat().st_mtime_ns)]
    for path in paths:
        stat = path.stat()
        parts.append(f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}")
    return "|".join(parts)


def _load_starter(card: dict[str, Any]) -> dict[str, Any]:
    path = STARTER_DIR / str(card["starter_file"])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"card contract: cannot read {path}: {error}") from error
    return data


def _validate_against_starter(card: dict[str, Any]) -> None:
    card_id = card["card_id"]
    path = STARTER_DIR / str(card["starter_file"])
    if not path.is_file():
        raise ValueError(f"card contract: starter missing for {card_id}: {path}")
    if _sha256_file(path) != card["starter_sha256"]:
        raise ValueError(
            f"card contract: {card_id} starter_sha256 drifted; regenerate "
            "the contract"
        )
    data = _load_starter(card)
    canvas = card["canvas"]
    if (data.get("width"), data.get("height")) != (
        canvas["width"], canvas["height"]
    ):
        raise ValueError(f"card contract: {card_id} starter canvas mismatch")
    children = data.get("pages", [{}])[0].get("children") or []
    exported = [
        child for child in children
        if isinstance(child, dict) and child.get("type") == "text"
        and child.get("showInExport") is not False
    ]
    slotted = [
        child for child in exported if (child.get("custom") or {}).get("slot")
    ]
    static = [
        child for child in exported if not (child.get("custom") or {}).get("slot")
    ]
    notes = [
        child for child in children
        if isinstance(child, dict) and child.get("type") == "text"
        and child.get("showInExport") is False
    ]
    by_layer = {str(child.get("id")): child for child in slotted}
    if {str(child.get("id")) for child in slotted} != {
        slot["layer_id"] for slot in card["data_slots"]
    }:
        raise ValueError(
            f"card contract: {card_id} data_slots do not cover authored slots"
        )
    for slot in card["data_slots"]:
        child = by_layer[slot["layer_id"]]
        if str((child.get("custom") or {}).get("slot")) != slot["slot_id"]:
            raise ValueError(
                f"card contract: {card_id}/{slot['slot_id']} authored slot drifted"
            )
        if _starter_box(child) != slot["box_px"]:
            raise ValueError(
                f"card contract: {card_id}/{slot['slot_id']} box drifted"
            )
        authored_font = _starter_font(child)
        for key in ("family", "size_px", "weight", "align"):
            if authored_font[key] != slot["font"][key]:
                raise ValueError(
                    f"card contract: {card_id}/{slot['slot_id']} font drifted"
                )
    by_static = {str(child.get("id")): child for child in static}
    if set(by_static) != {
        layer["layer_id"] for layer in card["static_text_layers"]
    }:
        raise ValueError(
            f"card contract: {card_id} static_text_layers do not cover authored text"
        )
    for layer in card["static_text_layers"]:
        child = by_static[layer["layer_id"]]
        if str(child.get("text", "")) != layer["text"]:
            raise ValueError(
                f"card contract: {card_id}/{layer['layer_id']} static text drifted"
            )
        if _starter_box(child) != layer["box_px"]:
            raise ValueError(
                f"card contract: {card_id}/{layer['layer_id']} static box drifted"
            )
        authored_font = _starter_font(child)
        for key in ("family", "size_px", "weight", "align"):
            if authored_font[key] != layer["font"][key]:
                raise ValueError(
                    f"card contract: {card_id}/{layer['layer_id']} static font drifted"
                )
    by_note = {str(child.get("id")): child for child in notes}
    if set(by_note) != {note["layer_id"] for note in card["editor_notes"]}:
        raise ValueError(
            f"card contract: {card_id} editor_notes do not cover hidden text"
        )
    for note in card["editor_notes"]:
        if str(by_note[note["layer_id"]].get("text", "")) != note["text"]:
            raise ValueError(
                f"card contract: {card_id}/{note['layer_id']} editor note drifted"
            )
    images = {
        str(child.get("id")) for child in children
        if isinstance(child, dict) and child.get("type") == "image"
    }
    if card["pack_layer_id"] is not None and card["pack_layer_id"] not in images:
        raise ValueError(
            f"card contract: {card_id} pack_layer_id is not an authored image"
        )
    layer_ids = {str(child.get("id")) for child in children}
    if any(child.get("type") == "media_slot" for child in children):
        raise ValueError(
            f"card contract: {card_id} authored starter must not contain media_slot"
        )
    for slot in card["media_slots"]:
        if slot["z_after_layer_id"] not in layer_ids:
            raise ValueError(
                f"card contract: {card_id} media anchor "
                f"{slot['z_after_layer_id']!r} missing"
            )


def _validate_against_registry(card: dict[str, Any], index: int) -> None:
    from apps.studio_templates.card_registry import cards_for_version

    registry = {
        str(item["id"]): item
        for item in cards_for_version(str(card.get("template_version") or ""))
    }
    card_id = card["card_id"]
    if card_id not in registry:
        raise ValueError(
            f"card contract: cards[{index}] {card_id!r} is not a built card"
        )
    expected = registry[card_id]
    if card["aspect"] != expected["aspect"]:
        raise ValueError(f"card contract: {card_id} aspect drifted from registry")
    if card.get("family") != expected.get("family"):
        raise ValueError(f"card contract: {card_id} family drifted from registry")
    renderer = expected.get("renderer") or ("generic", None)
    route = card["renderer_route"]
    if (route["kind"], route.get("mode")) != (renderer[0], renderer[1]):
        raise ValueError(f"card contract: {card_id} renderer route drifted")


def _validate_layout_grammar(contract: dict[str, Any]) -> None:
    grammar = contract.get("layout_grammar")
    grammar = _need_object(grammar, "layout_grammar")
    path = ROOT / str(grammar.get("path", ""))
    if not path.is_file():
        raise ValueError(f"card contract: layout grammar missing: {path}")
    if _sha256_file(path) != grammar.get("sha256"):
        raise ValueError(
            "card contract: graphic-templates.json drifted; regenerate the "
            "contract"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    layout_ids = {
        str(layout.get("id")) for layout in data.get("layouts") or []
        if isinstance(layout, dict) and layout.get("id")
    }
    contract_ids = {card["card_id"] for card in contract["cards"]}
    for layout in data.get("layouts") or []:
        if not isinstance(layout, dict):
            continue
        for card_id in layout.get("cards") or []:
            if str(card_id) not in contract_ids:
                raise ValueError(
                    f"card contract: layout {layout.get('id')!r} names unknown "
                    f"card {card_id!r}"
                )
        for card_id in (layout.get("card_slots") or {}):
            if str(card_id) not in contract_ids:
                raise ValueError(
                    f"card contract: layout {layout.get('id')!r} card_slots "
                    f"names unknown card {card_id!r}"
                )
    known_modes = set(layout_ids)
    for card in contract["cards"]:
        unknown = set(card["modes"]) - known_modes - {
            "media_b_roll", "tactical_explainer", "frame",
        }
        if unknown:
            raise ValueError(
                f"card contract: {card['card_id']} has unknown mode(s) "
                f"{sorted(unknown)}"
            )


def validate_contract(data: Any, *, check_drift: bool = True) -> dict[str, Any]:
    """Validate a contract document. Raises ValueError on any violation."""
    contract = _need_object(data, "root")
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError(
            "card contract: schema_version must be "
            f"{CONTRACT_SCHEMA_VERSION!r}, got {contract.get('schema_version')!r}"
        )
    if contract.get("contract_id") != CONTRACT_ID:
        raise ValueError(
            f"card contract: contract_id must be {CONTRACT_ID!r}, got "
            f"{contract.get('contract_id')!r}"
        )
    template_version = _need_str(
        contract.get("template_version"), "template_version"
    )
    canvas = _need_object(contract.get("canvas"), "canvas")
    width = _need_int(canvas.get("width"), "canvas.width", minimum=1)
    height = _need_int(canvas.get("height"), "canvas.height", minimum=1)
    _need_object(contract.get("source_of_truth"), "source_of_truth")
    cards = contract.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ValueError("card contract: 'cards' must be a non-empty list")
    digest = contract.get("contract_hash")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("card contract: contract_hash must be sha256")
    if digest != _canonical_hash(contract):
        raise ValueError(
            "card contract: contract_hash does not match the document; "
            "regenerate with tools/build_card_contract.py"
        )

    seen_cards: set[str] = set()
    for index, raw_card in enumerate(cards):
        card = _need_object(raw_card, f"cards[{index}]")
        card_id = _need_str(card.get("card_id"), f"cards[{index}].card_id")
        if card_id in seen_cards:
            raise ValueError(f"card contract: duplicate card_id {card_id!r}")
        seen_cards.add(card_id)
        _validate_card(
            card, index, template_version,
            {"width": width, "height": height},
        )
        if check_drift:
            _validate_against_registry(card, index)
            _validate_against_starter(card)

    if check_drift:
        from apps.studio_templates.card_registry import cards_for_version

        expected = {
            str(item["id"])
            for item in cards_for_version(str(contract.get("template_version") or ""))
        }
        if seen_cards != expected:
            missing = sorted(expected - seen_cards)
            extra = sorted(seen_cards - expected)
            raise ValueError(
                "card contract: must have exactly one record per built card; "
                f"missing={missing} extra={extra}"
            )
        _validate_layout_grammar(contract)
    return contract


@lru_cache(maxsize=16)
def _load_cached(
    path_text: str, mtime_ns: int, size: int, signature: str
) -> dict[str, Any]:
    _ = (mtime_ns, size, signature)  # cache key only: a changed file re-reads
    path = Path(path_text)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"card contract unreadable: {path}: {error}") from error
    return validate_contract(data)


def load_contract(template_version: str | None = None) -> dict[str, Any] | None:
    """Load + validate the contract for a template version.

    Returns None when the version ships no contract (older packs). A present
    but invalid/drifted contract raises: the planner must not silently ignore
    a malformed authored contract.
    """
    path = contract_path(template_version)
    if not path.is_file():
        return None
    stat = path.stat()
    return copy.deepcopy(
        _load_cached(
            str(path), stat.st_mtime_ns, stat.st_size,
            _starter_signature(template_version),
        )
    )


def contract_hash(template_version: str | None = None) -> str | None:
    contract = load_contract(template_version)
    return contract["contract_hash"] if contract is not None else None


def card_contract(
    card_id: str | None, template_version: str | None = None
) -> dict[str, Any] | None:
    if not isinstance(card_id, str) or not card_id.strip():
        return None
    contract = load_contract(template_version)
    if contract is None:
        return None
    for card in contract["cards"]:
        if card["card_id"] == card_id:
            record = copy.deepcopy(card)
            record["contract_hash"] = contract["contract_hash"]
            record["contract_id"] = contract["contract_id"]
            record["contract_schema_version"] = contract["schema_version"]
            return record
    return None


def is_executable(
    card_id: str | None, mode: str | None, template_version: str | None = None
) -> bool:
    card = card_contract(card_id, template_version)
    if card is None or mode is None:
        return False
    return str(mode) in card["execution"]["modes"]


def data_slots(
    card_id: str | None,
    template_version: str | None = None,
    *,
    mode: str | None = None,
) -> list[dict[str, Any]]:
    """Declared data slots for a card, optionally filtered by mode."""
    card = card_contract(card_id, template_version)
    if card is None:
        return []
    slots = card["data_slots"]
    if mode is None:
        return copy.deepcopy(slots)
    return copy.deepcopy(
        [slot for slot in slots if str(mode) in slot["active_modes"]]
    )


def media_slots(
    card_id: str | None,
    template_version: str | None = None,
    *,
    mode: str | None = None,
) -> list[dict[str, Any]]:
    """Declared media slots for a card, optionally filtered by visual mode."""
    card = card_contract(card_id, template_version)
    if card is None:
        return []
    if mode is not None and str(mode) not in card["modes"]:
        return []
    return copy.deepcopy(card["media_slots"])


def slot_box_px(
    slot: dict[str, Any], canvas: tuple[int, int] | list[int]
) -> list[int]:
    """Normalized authored box -> integer absolute pixel box."""
    width, height = int(canvas[0]), int(canvas[1])
    x, y, w, h = (float(value) for value in slot["box_norm"])
    return [
        round(x * width),
        round(y * height),
        round(w * width),
        round(h * height),
    ]


def media_layer(slot: dict[str, Any], canvas: tuple[int, int] | list[int]) -> dict[str, Any]:
    """The authored z-order layer frozen into the starter design.

    The renderer sees a normal absolute layer; the absence of a routed
    asset leaves it transparent so the pack artwork underneath remains.
    """
    x, y, w, h = slot_box_px(slot, canvas)
    slot_id = str(slot["slot_id"])
    return {
        "id": f"media-{slot_id}",
        "type": "media_slot",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "custom": {"slot_id": slot_id, "role": str(slot["role"])},
        "selectable": False,
        "draggable": False,
        "resizable": False,
        "removable": False,
    }


def _rounded_mask(
    width: int, height: int, radii: list[int], supersample: int = 4
) -> Any:
    from PIL import Image, ImageDraw

    scale = supersample
    mask = Image.new("L", (width * scale, height * scale), 0)
    draw = ImageDraw.Draw(mask)
    tl, tr, br, bl = (max(0, min(int(r), width // 2, height // 2)) for r in radii)
    # Middle columns + rows, then one pie slice per rounded corner.
    draw.rectangle(
        [tl * scale, 0, (width - tr) * scale, height * scale], fill=255
    )
    draw.rectangle(
        [0, tl * scale, width * scale, (height - bl) * scale], fill=255
    )
    if tl:
        draw.pieslice([0, 0, 2 * tl * scale, 2 * tl * scale], 180, 270, fill=255)
    if tr:
        draw.pieslice(
            [(width - 2 * tr) * scale, 0, width * scale, 2 * tr * scale],
            270,
            360,
            fill=255,
        )
    if br:
        draw.pieslice(
            [
                (width - 2 * br) * scale,
                (height - 2 * br) * scale,
                width * scale,
                height * scale,
            ],
            0,
            90,
            fill=255,
        )
    if bl:
        draw.pieslice(
            [0, (height - 2 * bl) * scale, 2 * bl * scale, height * scale],
            90,
            180,
            fill=255,
        )
    return mask.resize((width, height), Image.Resampling.LANCZOS)


def apply_mask(image: Any, mask: dict[str, Any] | None) -> Any:
    """Apply the contract mask to an RGBA image (alpha multiplied)."""
    from PIL import Image

    if not isinstance(mask, dict) or mask.get("shape") != "rounded_rect":
        return image
    width, height = image.size
    radii = list(mask.get("corner_radii_px") or [0, 0, 0, 0])
    alpha = _rounded_mask(width, height, radii)
    out = image.convert("RGBA")
    out.putalpha(Image.composite(out.getchannel("A"), Image.new("L", (width, height), 0), alpha))
    return out


def place_image(
    source: Any,
    target_size: tuple[int, int] | list[int],
    *,
    fit: str = "cover",
    focal_point: list[float] | tuple[float, float] = (0.5, 0.5),
    mask: dict[str, Any] | None = None,
    min_source_px: list[int] | tuple[int, int] | None = None,
) -> Any:
    """Deterministic crop/fit into a declared media box.

    No composition choice: fit, focal point, box, mask and minimum source
    size all arrive from the frozen contract/binding.
    """
    from PIL import Image, ImageOps

    if fit not in FITS:
        raise ValueError(f"card media: unsupported fit {fit!r}")
    target_w, target_h = int(target_size[0]), int(target_size[1])
    if target_w <= 0 or target_h <= 0:
        raise ValueError("card media: target box must be positive")
    photo = ImageOps.exif_transpose(source).convert("RGB")
    if min_source_px is not None:
        min_w, min_h = int(min_source_px[0]), int(min_source_px[1])
        if photo.width < min_w or photo.height < min_h:
            raise ValueError(
                f"card media: source image {photo.width}x{photo.height} is below "
                f"the contract minimum {min_w}x{min_h}"
            )
    if fit == "cover":
        scale = max(target_w / photo.width, target_h / photo.height)
    else:
        scale = min(target_w / photo.width, target_h / photo.height)
    resized_w = max(1, round(photo.width * scale))
    resized_h = max(1, round(photo.height * scale))
    resized = photo.resize((resized_w, resized_h), Image.Resampling.LANCZOS)
    if fit == "cover":
        fx = min(max(0.0, float(focal_point[0])), 1.0)
        fy = min(max(0.0, float(focal_point[1])), 1.0)
        left = round(fx * resized_w - target_w / 2)
        top = round(fy * resized_h - target_h / 2)
        left = max(0, min(left, resized_w - target_w))
        top = max(0, min(top, resized_h - target_h))
        fitted = resized.crop(
            (left, top, left + target_w, top + target_h)
        ).convert("RGBA")
    else:
        fitted = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        fitted.alpha_composite(
            resized.convert("RGBA"),
            ((target_w - resized_w) // 2, (target_h - resized_h) // 2),
        )
    return apply_mask(fitted, mask)


def composite_media_layer(
    base: Any,
    payload: dict[str, Any] | None,
    box_px: tuple[float, float, float, float] | list[float],
    *,
    opacity: float = 1.0,
) -> None:
    """Open the frozen asset and composite it into its authored box.

    Mutates ``base``. A missing payload paints nothing (declared fallback);
    a present payload that cannot be read raises — the renderer must not
    silently replace a bound portrait with pack artwork.
    """
    if not payload:
        return
    from PIL import Image

    path = payload.get("path")
    if not path:
        raise ValueError("card media: bound media payload has no path")
    try:
        with Image.open(path) as opened:
            photo = opened.copy()
    except (OSError, ValueError) as error:
        raise ValueError(f"card media: cannot read bound asset {path}: {error}") from error
    x, y, w, h = (int(round(float(value))) for value in box_px)
    placed = place_image(
        photo,
        (w, h),
        fit=str(payload.get("fit", "cover")),
        focal_point=payload.get("focal_point") or (0.5, 0.5),
        mask=payload.get("mask"),
        min_source_px=payload.get("min_source_px"),
    )
    if opacity < 1.0:
        alpha = placed.getchannel("A").point(lambda value: int(value * opacity))
        placed.putalpha(alpha)
    base.alpha_composite(placed, (x, y))


__all__ = [
    "CONTRACT_FILENAME",
    "CONTRACT_SCHEMA_VERSION",
    "DEFAULT_TEMPLATE_VERSION",
    "FITS",
    "MASK_SHAPES",
    "apply_mask",
    "card_contract",
    "composite_media_layer",
    "contract_hash",
    "contract_path",
    "data_slots",
    "is_executable",
    "load_contract",
    "media_layer",
    "media_slots",
    "place_image",
    "slot_box_px",
    "validate_contract",
]
