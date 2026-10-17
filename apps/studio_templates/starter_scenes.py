"""Render video scenes from authored starter JSONs (single source of truth).

Short-form video previously drew generic pack boxes (arbitrary geometry).
This module renders the SAME starter scenes Studio and proofs use: load
STARTERS_SHORT[mode], substitute reviewed graphic_data into slotted texts,
hide slots with no data, render pixel-exact via render_design (two-tone
*accent* renders base fill + magenta). Any failure returns None so the
caller falls back to the generic path; it never raises.

Canonical layout logic lives in apps.scene_graph.builder (Scene Graph
boundary: planner picks composition, renderer only executes absolute
layers). This module is a thin backward-compatible wrapper over the
builder so legacy callers (video_renderer) keep byte-identical output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apps.scene_graph.builder import (
    _compose_design as _builder_compose,
)
from apps.scene_graph.builder import (
    _crest_monogram,
    _fill_score,
    _initials,
    _load_starter_design,
    _parse_score,
    _source_date,
    _substitutions,
)

ROOT = Path(__file__).resolve().parent.parent.parent
TPL = ROOT / "apps" / "studio_templates"

__all__ = [
    "_initials",
    "_crest_monogram",
    "_source_date",
    "_parse_score",
    "_fill_score",
    "_substitutions",
    "_prepare",
    "_compose",
    "render_starter_scene",
    "render_starter_layers",
]


def _prepare(mode: str, graphic_data: dict[str, Any],
             evidence: list[Any], starter_id: str | None) -> dict[str, Any] | None:
    """Load starter JSON + substitute reviewed values. None on any miss."""
    if not starter_id:
        try:
            from apps.card_selector import STARTERS_SHORT
        except Exception:
            return None
        starter_id = STARTERS_SHORT.get(mode)
    if not starter_id:
        return None
    data = _load_starter_design(starter_id)
    if data is None:
        return None
    slots = _substitutions(mode, graphic_data or {}, evidence or [])
    if slots is None:
        return None
    return data, slots


def _compose(data: dict[str, Any], slots: dict[str, str]) -> dict[str, Any]:
    """Substitute reviewed values + data-driven decor. Mutates and returns."""
    composed, _segments = _builder_compose(data, slots)
    return composed


def render_starter_scene(mode: str, graphic_data: dict[str, Any],
                         evidence: list[Any], starter_id: str | None) -> Any | None:
    """Render the authored starter with reviewed values. None on any miss."""
    try:
        from apps.studio_templates.render_starters import render_design
        prepared = _prepare(mode, graphic_data, evidence, starter_id)
        if prepared is None:
            return None
        return render_design(_compose(*prepared))
    except Exception:
        return None


def render_starter_layers(mode: str, graphic_data: dict[str, Any],
                          evidence: list[Any],
                          starter_id: str | None) -> tuple[Any, Any] | None:
    """Background + text layers so video can entrance type after the plate.
    Returns (bg_image, text_image_or_None). None on any miss."""
    try:
        from apps.studio_templates.render_starters import render_design
        prepared = _prepare(mode, graphic_data, evidence, starter_id)
        if prepared is None:
            return None
        data = _compose(*prepared)
        bg = render_design(data, texts=False)
        has_text = any(isinstance(c, dict) and c.get("type") == "text"
                       and c.get("showInExport") is not False
                       for c in data["pages"][0]["children"])
        text = render_design(data, decor=False, transparent=True) if has_text else None
        return bg, text
    except Exception:
        return None
