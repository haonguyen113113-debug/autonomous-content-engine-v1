"""Beat intent vocabulary (LLM meaning only — never layout).

The LLM owns exactly four meaning fields per beat:

- image_goal: what the frame must communicate
- focus_subject: who/what the frame focuses on (free text, <=120 chars)
- evidence_type: what kind of sourced evidence backs the beat
- emphasis_level: how hard the beat lands (guides intensity, not layout)

The LLM must NEVER choose layout, starter, camera, motion, transition,
colors, or fonts. The planner (card_selector composition + scene-graph
builder freeze) determines composition from this intent plus
suitable/approved assets plus the locked template pack.

Leaf module: stdlib only, so both apps.content_workflow (LLM side) and
apps.scene_graph.builder (freeze side) import it without cycles.
"""

from __future__ import annotations

from typing import Any

IMAGE_GOALS = frozenset({
    "establish_moment",
    "show_evidence",
    "compare_numbers",
    "introduce_player",
    "set_context",
    "land_takeaway",
})

EVIDENCE_TYPES = frozenset({
    "sourced_stat",
    "sourced_quote",
    "match_event",
    "table_standing",
    "tactical_observation",
    "none",
})

EMPHASIS_LEVELS = frozenset({
    "quiet",
    "standard",
    "hero",
})

MAX_FOCUS_CHARS = 120

_DEFAULT_GOAL_BY_MODE: dict[str, str] = {
    "hook_card": "establish_moment",
    "score_card": "show_evidence",
    "goal_card": "show_evidence",
    "duel_columns": "compare_numbers",
    "comparison_duel": "compare_numbers",
    "statline_scorecard": "show_evidence",
    "stat_leader": "compare_numbers",
    "chart_comparison": "compare_numbers",
    "chart_timeline": "show_evidence",
    "player_card": "introduce_player",
    "player_poster": "introduce_player",
    "player_poster_side": "introduce_player",
    "player_poster_top": "introduce_player",
    "potm_card": "introduce_player",
    "fixture_card": "set_context",
    "fixture_list": "set_context",
    "source_card": "show_evidence",
    "quote_card": "show_evidence",
    "tactical_explainer": "show_evidence",
    "media_b_roll": "land_takeaway",
    "discipline_card": "show_evidence",
    "welcome_card": "set_context",
}


def _default_evidence_type(mode: str, graphic_data: dict[str, Any]) -> str:
    data = graphic_data if isinstance(graphic_data, dict) else {}
    if mode == "tactical_explainer":
        return "tactical_observation" if data else "none"
    for key in ("metrics", "stats", "values", "hero"):
        value = data.get(key)
        if isinstance(value, (list, dict)) and bool(value):
            return "sourced_stat"
    if data.get("score"):
        return "match_event"
    if data.get("fixtures"):
        return "table_standing"
    if data.get("claim") or data.get("hook_text"):
        return "sourced_quote"
    return "none"


def normalize_beat_intent(
    raw: Any,
    *,
    mode: str = "",
    index: int = 0,
    graphic_data: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Normalize LLM-supplied beat intent. Never raises, never invents facts.

    Invalid/missing fields fall back deterministically from the frozen
    mode + reviewed graphic_data shape. focus_subject is truncated, never
    padded with invented detail.
    """
    data = graphic_data if isinstance(graphic_data, dict) else {}
    raw = raw if isinstance(raw, dict) else {}

    goal = raw.get("image_goal")
    if goal not in IMAGE_GOALS:
        goal = _DEFAULT_GOAL_BY_MODE.get(mode, "set_context")

    focus = raw.get("focus_subject", "")
    focus = str(focus).strip()[:MAX_FOCUS_CHARS]

    evidence_type = raw.get("evidence_type")
    if evidence_type not in EVIDENCE_TYPES:
        evidence_type = _default_evidence_type(mode, data)

    emphasis = raw.get("emphasis_level")
    if emphasis not in EMPHASIS_LEVELS:
        emphasis = "hero" if index == 0 else "standard"

    return {
        "image_goal": str(goal),
        "focus_subject": focus,
        "evidence_type": str(evidence_type),
        "emphasis_level": str(emphasis),
    }


__all__ = [
    "IMAGE_GOALS",
    "EVIDENCE_TYPES",
    "EMPHASIS_LEVELS",
    "MAX_FOCUS_CHARS",
    "normalize_beat_intent",
]
