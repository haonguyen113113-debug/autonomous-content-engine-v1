"""File-backed job queue for the worker (spec section 10).

The in-memory ``job_queue`` cannot cross processes: the web server and a
separate worker process never see each other's jobs. This store persists every job
under ``runtime/queue/{queued,claimed,done,failed}/<job_id>.json`` so a
producer (UI/API) and any number of worker processes share one queue, and
a worker restart never loses a job — stale claims are recovered, never
silently dropped.

Job record: {id, type, status, payload, attempts, max_attempts, worker_id,
created_at, claimed_at, finished_at, result, error}. Times are UTC ISO.
Writes are atomic (tmp file + os.replace). All functions raise ValueError
on invalid input and OSError on I/O failure — never silent.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATES = ("queued", "claimed", "done", "failed")

SUPPORTED_TYPES = ("draft",)

MAX_BATCH = 20
MAX_ATTEMPTS_CAP = 5
STALE_CLAIM_SECONDS = 1800


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _queue_root(root: Path | str) -> Path:
    return Path(root) / "runtime" / "queue"


def _read_record(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Unreadable job file: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Job file must contain an object: {path.name}")
    return value


def _write_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _new_id(queue_root: Path) -> str:
    for _ in range(8):
        candidate = uuid.uuid4().hex[:12]
        if not any((queue_root / state / f"{candidate}.json").exists() for state in STATES):
            return candidate
    raise ValueError("Could not allocate a unique job id.")


def validate_draft_payload(payload: Any) -> dict[str, Any]:
    """Clean one draft payload; raises ValueError naming the first problem."""
    if not isinstance(payload, dict):
        raise ValueError("Each job must be an object with topic/story_form/evidence.")
    topic = payload.get("topic", "")
    topic = topic.strip() if isinstance(topic, str) else ""
    if not 4 <= len(topic) <= 500:
        raise ValueError("Job topic must be 4-500 characters.")
    content_type = str(payload.get("content_type", "short")).strip().lower() or "short"
    if content_type not in {"short", "long"}:
        raise ValueError("Job content_type must be short or long.")
    try:
        max_attempts = int(payload.get("max_attempts", 3) or 3)
    except (TypeError, ValueError):
        raise ValueError("Job max_attempts must be an integer.") from None
    max_attempts = max(1, min(max_attempts, MAX_ATTEMPTS_CAP))
    story_form = payload.get("story_form", "")
    story_form = story_form.strip() if isinstance(story_form, str) else ""
    evidence = payload.get("evidence", "")
    evidence = evidence if isinstance(evidence, str) else ""
    colorway = payload.get("colorway", "")
    colorway = colorway.strip() if isinstance(colorway, str) else ""
    return {
        "topic": topic,
        "story_form": story_form,
        "evidence": evidence,
        "content_type": content_type,
        "colorway": colorway or "cyber-pitch",
        "max_attempts": max_attempts,
    }


def enqueue_job(root: Path | str, job_type: str, payload: Any) -> dict[str, Any]:
    """Persist one job as queued. The whole batch caller validates first."""
    if job_type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported job type: {job_type!r}.")
    clean = validate_draft_payload(payload)
    queue_root = _queue_root(root)
    record = {
        "id": _new_id(queue_root),
        "type": job_type,
        "status": "queued",
        "payload": clean,
        "attempts": 0,
        "max_attempts": clean["max_attempts"],
        "worker_id": None,
        "created_at": _now(),
        "claimed_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }
    _write_record(queue_root / "queued" / f"{record['id']}.json", record)
    return record


def claim_job(
    root: Path | str, worker_id: str, *, stale_seconds: int = STALE_CLAIM_SECONDS,
) -> dict[str, Any] | None:
    """Atomically move the oldest queued job to claimed. None when empty."""
    recover_stale_claims(root, worker_id, stale_seconds=stale_seconds)
    queue_root = _queue_root(root)
    queued_dir = queue_root / "queued"
    if not queued_dir.is_dir():
        return None
    candidates = []
    for path in queued_dir.glob("*.json"):
        try:
            candidates.append((path.stat().st_mtime, path))
        except OSError:
            continue
    for _, path in sorted(candidates):
        try:
            record = _read_record(path)
        except ValueError:
            continue
        record["status"] = "claimed"
        record["worker_id"] = worker_id
        record["claimed_at"] = _now()
        record["attempts"] = int(record.get("attempts", 0) or 0) + 1
        target = queue_root / "claimed" / path.name
        try:
            _write_record(target, record)
            path.unlink()
        except OSError:
            continue
        return record
    return None


def finish_job(
    root: Path | str, job_id: str, status: str, result: Any = None, error: str | None = None,
) -> dict[str, Any]:
    """Move a claimed job to done/failed with its outcome recorded."""
    if status not in {"done", "failed"}:
        raise ValueError("finish status must be done or failed.")
    queue_root = _queue_root(root)
    path = queue_root / "claimed" / f"{job_id}.json"
    if not path.is_file():
        raise ValueError(f"No claimed job to finish: {job_id}.")
    record = _read_record(path)
    record["status"] = status
    record["finished_at"] = _now()
    record["result"] = result
    record["error"] = error
    _write_record(queue_root / status / path.name, record)
    path.unlink()
    return record


def recover_stale_claims(
    root: Path | str, worker_id: str, *, stale_seconds: int = STALE_CLAIM_SECONDS,
) -> list[dict[str, Any]]:
    """Re-queue claims older than the threshold (crashed workers).

    Claims that already exhausted max_attempts go to failed instead, with
    the reason recorded. Returns the recovered/failed records.
    """
    queue_root = _queue_root(root)
    claimed_dir = queue_root / "claimed"
    if not claimed_dir.is_dir():
        return []
    recovered: list[dict[str, Any]] = []
    try:
        now = datetime.now(timezone.utc).timestamp()
    except Exception:  # noqa: BLE001 - clock must never break recovery
        return []
    for path in sorted(claimed_dir.glob("*.json")):
        try:
            record = _read_record(path)
            claimed_at = datetime.fromisoformat(str(record.get("claimed_at") or "")).timestamp()
        except (ValueError, TypeError):
            continue
        if now - claimed_at < max(60, stale_seconds):
            continue
        attempts = int(record.get("attempts", 0) or 0)
        if attempts >= int(record.get("max_attempts", 3) or 3):
            record["status"] = "failed"
            record["finished_at"] = _now()
            record["error"] = "Stale claim recovered after attempts exhausted."
            _write_record(queue_root / "failed" / path.name, record)
        else:
            record["status"] = "queued"
            record["worker_id"] = None
            record["claimed_at"] = None
            _write_record(queue_root / "queued" / path.name, record)
        try:
            path.unlink()
        except OSError:
            continue
        recovered.append(record)
    return recovered


def list_jobs(root: Path | str, *, limit: int = 100) -> list[dict[str, Any]]:
    """Newest-first overview across queued/claimed/done/failed (read-only)."""
    queue_root = _queue_root(root)
    records: list[dict[str, Any]] = []
    for state in STATES:
        state_dir = queue_root / state
        if not state_dir.is_dir():
            continue
        for path in state_dir.glob("*.json"):
            try:
                record = _read_record(path)
            except ValueError:
                continue
            record.setdefault("status", state)
            records.append(record)
    records.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return records[:max(1, limit)]
