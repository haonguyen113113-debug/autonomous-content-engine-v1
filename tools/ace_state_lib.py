"""ACE state collector: machine-readable truth, part 1 of 2 (collectors)."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COORD = REPO / "docs" / "coordinator"
STATE_PATH = COORD / "STATE.json"
PROGRESS_PATH = COORD / "PROGRESS.md"
SCHEMA_VERSION = "ace-state/1.0"


def _run(cmd: list[str], timeout: int = 30) -> str:
    try:
        out = subprocess.run(
            cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


def git_facts() -> dict:
    branch = _run(["git", "branch", "--show-current"])
    commit = _run(["git", "rev-parse", "--short", "HEAD"])
    full = _run(["git", "rev-parse", "HEAD"])
    status = _run(["git", "status", "--short"])
    wt_raw = _run(["git", "worktree", "list", "--porcelain"])
    worktrees = [l[9:] for l in wt_raw.splitlines() if l.startswith("worktree ")]
    log = _run(["git", "log", "--oneline", "-3"])
    return {
        "branch": branch or "unknown",
        "commit": commit or "unknown",
        "full_commit": full or "unknown",
        "dirty_files": [l for l in status.splitlines() if l.strip()],
        "worktrees": worktrees,
        "recent_log": [l for l in log.splitlines() if l.strip()],
    }


def contracts() -> list[dict]:
    out: list[dict] = []
    cdir = COORD / "contracts"
    if not cdir.is_dir():
        return out
    for path in sorted(cdir.glob("c*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        heading = next((line for line in text.splitlines() if line.startswith("# ")), "")
        match = re.search(r"\bv(\d+\.\d+)\b", heading)
        if match:
            ver = match.group(1)
        else:
            ver = "1.0" if "1.0" in text else "unknown"
        out.append({
            "id": path.stem,
            "version": ver,
            "path": str(path.relative_to(REPO)).replace("\\", "/"),
            "sha8": hashlib.sha256(text.encode()).hexdigest()[:8],
        })
    return out


def tasks() -> list[dict]:
    out: list[dict] = []
    tdir = COORD / "tasks"
    if not tdir.is_dir():
        return out
    for td in sorted(tdir.iterdir()):
        if not td.is_dir():
            continue
        packet, report = td / "packet.md", td / "report.md"
        status = "NOT_STARTED"
        if report.is_file():
            body = report.read_text(encoding="utf-8", errors="replace")
            status = "REPORTED"
            for m in ("DONE", "BLOCKED", "NEEDS_REVIEW", "IN_PROGRESS"):
                if m in body:
                    status = m
                    break
        elif packet.is_file():
            status = "PACKET_READY"
        out.append({
            "task_id": td.name,
            "status": status,
            "packet": str(packet.relative_to(REPO)).replace("\\", "/")
            if packet.is_file() else None,
            "report": str(report.relative_to(REPO)).replace("\\", "/")
            if report.is_file() else None,
        })
    return out


def test_index() -> list[str]:
    tdir = REPO / "tests"
    if not tdir.is_dir():
        return []
    return sorted(p.name for p in tdir.glob("test_*.py") if p.is_file())


def render_index(limit: int = 5) -> list[dict]:
    rdir = REPO / "runtime" / "renders"
    if not rdir.is_dir():
        return []
    runs = []
    subs = sorted(
        (d for d in rdir.iterdir() if d.is_dir()),
        key=lambda d: d.stat().st_mtime, reverse=True,
    )[:limit]
    for rd in subs:
        runs.append({
            "run_id": rd.name,
            "mp4": [p.name for p in rd.glob("*.mp4")],
            "report": [p.name for p in rd.glob("*.json")],
            "contact": [p.name for p in rd.glob("*.png")
                        if "contact" in p.name or "audit" in p.name],
        })
    return runs
