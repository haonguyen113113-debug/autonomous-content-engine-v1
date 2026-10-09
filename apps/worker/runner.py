from __future__ import annotations

"""Real job execution with bounded retries and backoff (spec section 10).

Routine operational work — discovery, production, retries, rate-limit
handling, state persistence — must be automated. Only auth failures,
irrecoverable errors, and approval gates stop the worker loudly.
"""

import time
from pathlib import Path
from typing import Any


MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 5


def _is_retryable(error: Exception) -> bool:
    # Validation errors never succeed on retry; transport/server errors might.
    if isinstance(error, (ValueError, TypeError)):
        return False
    message = str(error).lower()
    if "invalid" in message or "not found" in message or "required" in message:
        return False
    return True


def process_draft_job(root: Path, db_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Run one content draft with bounded retries. Raises on final failure."""
    from apps.content_workflow import run_content_agent

    attempts = 0
    max_attempts = int(payload.get("max_attempts", MAX_ATTEMPTS) or MAX_ATTEMPTS)
    last_error: Exception | None = None
    while attempts < max(1, max_attempts):
        attempts += 1
        try:
            run = run_content_agent(
                Path(root), Path(db_path),
                str(payload.get("topic", "")),
                str(payload.get("story_form", "")),
                str(payload.get("evidence", "")),
                str(payload.get("content_type", "short")),
                str(payload.get("colorway", "match-night")),
            )
            return {"status": "DONE", "run_id": run.get("run_id"), "attempts": attempts}
        except Exception as error:  # noqa: BLE001 - worker must record anything
            last_error = error
            if not _is_retryable(error) or attempts >= max(1, max_attempts):
                break
            time.sleep(BACKOFF_BASE_SECONDS * (2 ** (attempts - 1)))
    raise RuntimeError(f"Draft job failed after {attempts} attempt(s): {last_error}")


def process_job(root: Path, db_path: Path, job: Any) -> dict[str, Any]:
    """Dispatch one queued job. Unknown types fail loudly, never silently."""
    job_type = getattr(job, "type", "")
    payload = getattr(job, "payload", {}) or {}
    if job_type == "draft":
        return process_draft_job(root, db_path, payload)
    raise ValueError(f"Unsupported job type: {job_type!r}.")
