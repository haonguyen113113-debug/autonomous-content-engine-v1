"""ACE state CLI: refresh STATE.json + PROGRESS.md, or print a worker brief."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ace_state_lib import (
    COORD, PROGRESS_PATH, REPO, SCHEMA_VERSION, STATE_PATH,
    contracts, git_facts, render_index, tasks, test_index,
)


def collect() -> dict:
    git = git_facts()
    rubric = COORD / "AUDIT_RUBRIC_STRICT_V1.md"
    goal = COORD / "GOAL_AND_THRESHOLDS.md"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0).isoformat(),
        "repo_root": str(REPO).replace("\\", "/"),
        "git": git,
        "goal": {
            "priority": "beautiful render + image QA, STRICT",
            "scope": "short-form 9:16; latest pinned pack 12.1.0; long-form later",
            "pass_gate": "human eyes on contact sheet + MP4 required",
            "goal_file": "docs/coordinator/GOAL_AND_THRESHOLDS.md"
            if goal.is_file() else None,
            "rubric_file": "docs/coordinator/AUDIT_RUBRIC_STRICT_V1.md"
            if rubric.is_file() else None,
        },
        "contracts": contracts(),
        "tasks": tasks(),
        "tests": test_index(),
        "recent_renders": render_index(),
        "must_read": [
            "docs/ENGINE_STATE.md",
            "docs/coordinator/GOAL_AND_THRESHOLDS.md",
            "docs/coordinator/AUDIT_RUBRIC_STRICT_V1.md",
            "docs/coordinator/contracts/README.md",
            "docs/coordinator/source-card-c9-12-1-0-2026-10-20.md",
        ],
        "forbidden": ["runtime/", ".env", "credentials",
                      "docs/ENGINE_STATE.md (coordinator owns)"],
    }


def render_progress(state: dict) -> str:
    from pathlib import Path as _P
    L: list[str] = []
    L.append("# ACE Progress — auto-generated reference")
    L.append("")
    L.append(f"> Generated {state['generated_at']}. "
             "Workers read STATE.json; humans read this. "
             "Refresh with `python tools/ace_state.py --write`.")
    L.append("")
    g = state["git"]
    L.append(f"Repo `{state['repo_root']}` @ `{g['branch']}/{g['commit']}`")
    L.append("")
    L.append("## Tasks")
    for t in state["tasks"]:
        L.append(f"- {t['task_id']}: **{t['status']}**")
    L.append("")
    L.append("## Contracts")
    for c in state["contracts"]:
        L.append(f"- {c['id']} v{c['version']} sha:{c['sha8']}")
    L.append("")
    L.append("## Recent renders (reference only)")
    for r in state["recent_renders"]:
        L.append(f"- {r['run_id']}: mp4={r['mp4'] or '-'}")
    L.append("")
    L.append("## Dirty files")
    if g["dirty_files"]:
        for f in g["dirty_files"][:20]:
            L.append(f"- {f}")
    else:
        L.append("- clean")
    L.append("")
    hand = _P(__file__).resolve().parent.parent / "docs" / "ENGINE_STATE.md"
    if hand.is_file():
        L.append("## Handoff prose (from docs/ENGINE_STATE.md, coordinator-owned)")
        L.append("")
        for line in hand.read_text(encoding="utf-8").splitlines():
            L.append(f"> {line}" if line.strip() else ">")
    return "\n".join(L) + "\n"


def brief(state: dict, task_id: str) -> str:
    t = next((x for x in state["tasks"] if x["task_id"] == task_id), None)
    g = state["git"]
    cons = ", ".join(f"{c['id']} v{c['version']}" for c in state["contracts"])
    return "\n".join([
        f"# Worker brief: {task_id}",
        f"Repo {state['repo_root']} @ {g['branch']}/{g['commit']}",
        f"Packet docs/coordinator/tasks/{task_id}/packet.md (follow exactly)",
        f"Contracts: {cons}",
        f"Status: {t['status'] if t else 'UNKNOWN'}",
        "Read packet, ENGINE_STATE.md, named contracts. "
        f"Write docs/coordinator/tasks/{task_id}/report.md and stop. "
        "Then run python tools/ace_state.py --write.",
    ]) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="ACE state collector")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--brief", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    state = collect()
    if a.brief:
        print(brief(state, a.brief))
        return 0
    if a.check:
        if not STATE_PATH.is_file():
            print("STALE: STATE.json missing, run --write")
            return 1
        old = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if old.get("git", {}).get("full_commit") != state["git"]["full_commit"]:
            print("STALE: commit changed, run --write")
            return 1
        if old.get("git", {}).get("dirty_files") != state["git"]["dirty_files"]:
            print("STALE: tree changed, run --write")
            return 1
        print("FRESH")
        return 0
    if a.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    if a.write:
        STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        PROGRESS_PATH.write_text(render_progress(state), encoding="utf-8")
        print(f"wrote {STATE_PATH}")
        print(f"wrote {PROGRESS_PATH}")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
