"""The R4 gate fixture must stay planner-consistent.

The planner assigns beat roles positionally (first = hook, last = takeaway), so
a gate run that starts on a tactical beat silently re-plans that beat as a hook
card and renders a fallback primitive. That happened once; this test keeps the
encoded run ordered hook -> reading -> conclusion.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.card_selector import select_cards  # noqa: E402


def test_gate_run_keeps_planner_roles_positional():
    from tools.r4_gate import build_run

    run = build_run("4a4f0c1d2e3b")
    out = select_cards(
        [dict(segment) for segment in run["draft"]["segments"]],
        content_type="short",
    )
    decisions = out["decisions"]

    assert [d["grammar"]["role"] for d in decisions] == [
        "hook", "tactical", "takeaway"
    ]
    assert [d["starter_id"] for d in decisions] == ["C-11", "C-12", "C-13"]
    assert [d["card_execution"] for d in decisions] == ["contract"] * 3
    assert all(d["production_ready"] for d in decisions)


def test_gate_run_duration_is_inside_the_short_template_range():
    from tools.r4_gate import build_run

    run = build_run("4a4f0c1d2e3b")
    assert run["draft"]["duration_target_seconds"] >= 20
    for segment in run["draft"]["segments"]:
        assert segment["end_seconds"] > segment["start_seconds"]
