from __future__ import annotations

"""Portfolio learning (PROJECT_SPEC sections 3, 5, 12).

Recommendations only: the engine proposes promotion, demotion, pause, or
retirement with evidence, but lifecycle changes stay owner decisions.
Frequent change is not a goal; weak signals stay in exploration.
"""

from typing import Any


CORE_LIMIT = 4
MIN_RUNS_FOR_CORE = 3
MIN_VIEWS_FOR_CORE = 500


def recommend_allocation(
    channel_summaries: list[dict[str, Any]],
    *,
    core_limit: int = CORE_LIMIT,
) -> dict[str, Any]:
    """Rank channels into core / exploration / retire-review with reasons."""
    ranked = sorted(
        channel_summaries,
        key=lambda c: (
            float(c.get("payout_verified_usd", 0.0) or 0.0),
            int(c.get("views", 0) or 0),
            int(c.get("run_count", 0) or 0),
        ),
        reverse=True,
    )
    core, exploration, retire_review = [], [], []
    for channel in ranked:
        runs = int(channel.get("run_count", 0) or 0)
        views = int(channel.get("views", 0) or 0)
        paid = float(channel.get("payout_verified_usd", 0.0) or 0.0)
        name = str(channel.get("channel_id", "unknown"))
        if runs >= MIN_RUNS_FOR_CORE and (views >= MIN_VIEWS_FOR_CORE or paid > 0):
            if len(core) < core_limit:
                core.append({"channel_id": name,
                             "reason": f"{runs} runs, {views} views, ${paid:.2f} verified"})
                continue
        if runs > 0 and views == 0 and paid == 0 and runs >= MIN_RUNS_FOR_CORE:
            retire_review.append({"channel_id": name,
                                  "reason": f"{runs} runs with zero response; review for pause/retire"})
            continue
        exploration.append({"channel_id": name,
                            "reason": "insufficient evidence for core; keep limited exploration"})
    return {"core": core, "exploration": exploration, "retire_review": retire_review,
            "core_limit": core_limit}


def recommend_lifecycle(channel: dict[str, Any]) -> dict[str, Any]:
    """Candidate -> testing -> core/exploration -> paused -> retired (advisory)."""
    runs = int(channel.get("run_count", 0) or 0)
    views = int(channel.get("views", 0) or 0)
    paid = float(channel.get("payout_verified_usd", 0.0) or 0.0)
    state = str(channel.get("lifecycle_state", "candidate"))
    if state == "candidate" and runs > 0:
        return {"from": state, "to": "testing", "reason": "first runs started"}
    if state == "testing":
        if runs >= MIN_RUNS_FOR_CORE and (views >= MIN_VIEWS_FOR_CORE or paid > 0):
            return {"from": state, "to": "core", "reason": "validated response"}
        if runs >= MIN_RUNS_FOR_CORE:
            return {"from": state, "to": "exploration",
                    "reason": "no validation yet; limit allocation"}
        return {"from": state, "to": "testing", "reason": "keep observing"}
    if state in {"core", "exploration"} and runs >= MIN_RUNS_FOR_CORE and views == 0 and paid == 0:
        return {"from": state, "to": "paused", "reason": "zero response; pause before retire"}
    return {"from": state, "to": state, "reason": "do not change without signal"}
