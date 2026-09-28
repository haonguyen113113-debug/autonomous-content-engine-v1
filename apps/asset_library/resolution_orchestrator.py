from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any

from .belief import Belief, ensure_belief_schema, resolve_belief
from .change_detection import (
    EVENT_TYPE,
    ChangeEvent,
    ensure_change_detection_schema,
)
from .source_registry import ensure_source_schema

ORCHESTRATOR_VERSION = "resolution-orchestrator-v0.1"
RESOLUTION_STATUSES = {"FAILED", "RESOLVED"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class ResolutionStatus:
    change_event_id: str
    status: str
    attempts: int
    first_attempt_at: str | None
    last_attempt_at: str | None
    resolved_at: str | None
    result_belief_id: str | None
    error_type: str | None
    error_message: str | None
    orchestrator_version: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ResolutionResult:
    change_event_id: str
    status: str
    attempts: int
    belief_id: str | None = None
    error_type: str | None = None
    error_message: str | None = None


def ensure_resolution_schema(conn: sqlite3.Connection) -> None:
    ensure_source_schema(conn)
    ensure_change_detection_schema(conn)
    ensure_belief_schema(conn)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS change_event_resolutions (
            change_event_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            first_attempt_at TEXT,
            last_attempt_at TEXT,
            resolved_at TEXT,
            result_belief_id TEXT,
            error_type TEXT,
            error_message TEXT,
            orchestrator_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK(status IN ('FAILED', 'RESOLVED')),
            CHECK(attempts >= 0)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_change_event_resolutions_status
        ON change_event_resolutions(status)
        """
    )
    conn.commit()


def _read_resolution_status(
    row: sqlite3.Row | tuple[Any, ...],
) -> ResolutionStatus:
    return ResolutionStatus(
        change_event_id=row[0],
        status=row[1],
        attempts=int(row[2]),
        first_attempt_at=row[3],
        last_attempt_at=row[4],
        resolved_at=row[5],
        result_belief_id=row[6],
        error_type=row[7],
        error_message=row[8],
        orchestrator_version=row[9],
        created_at=row[10],
        updated_at=row[11],
    )


def get_resolution_status(
    conn: sqlite3.Connection,
    change_event_id: str,
) -> ResolutionStatus | None:
    ensure_resolution_schema(conn)
    row = conn.execute(
        """
        SELECT change_event_id, status, attempts,
               first_attempt_at, last_attempt_at, resolved_at,
               result_belief_id, error_type, error_message,
               orchestrator_version, created_at, updated_at
        FROM change_event_resolutions
        WHERE change_event_id = ?
        """,
        (change_event_id,),
    ).fetchone()
    return None if row is None else _read_resolution_status(row)


def _read_change_event(
    row: sqlite3.Row | tuple[Any, ...],
) -> ChangeEvent:
    return ChangeEvent(
        change_event_id=row[0],
        observation_id=row[1],
        subject_type=row[2],
        subject_id=row[3],
        field=row[4],
        event_type=row[5],
        reason_codes=tuple(json.loads(row[6])),
        previous_observation_id=row[7],
        previous_value=json.loads(row[8]) if row[8] is not None else None,
        observed_value=json.loads(row[9]),
        current_belief_id=row[10],
        current_belief_value=(
            json.loads(row[11]) if row[11] is not None else None
        ),
        detected_at=row[12],
        detector_version=row[13],
    )


def _pending_change_events(
    conn: sqlite3.Connection,
    limit: int,
) -> list[ChangeEvent]:
    rows = conn.execute(
        """
        SELECT ce.change_event_id,
               ce.observation_id,
               ce.subject_type,
               ce.subject_id,
               ce.field,
               ce.event_type,
               ce.reason_codes_json,
               ce.previous_observation_id,
               ce.previous_value_json,
               ce.observed_value_json,
               ce.current_belief_id,
               ce.current_belief_value_json,
               ce.detected_at,
               ce.detector_version
        FROM change_events ce
        LEFT JOIN change_event_resolutions cer
          ON cer.change_event_id = ce.change_event_id
        WHERE ce.event_type = ?
          AND (
              cer.change_event_id IS NULL
              OR cer.status = 'FAILED'
          )
        ORDER BY ce.detected_at ASC, ce.change_event_id ASC
        LIMIT ?
        """,
        (EVENT_TYPE, limit),
    ).fetchall()
    return [_read_change_event(row) for row in rows]


def _record_attempt(
    conn: sqlite3.Connection,
    change_event_id: str,
    *,
    attempted_at: str,
) -> int:
    current = get_resolution_status(conn, change_event_id)
    attempts = 1 if current is None else current.attempts + 1
    first_attempt_at = (
        attempted_at
        if current is None or current.first_attempt_at is None
        else current.first_attempt_at
    )
    created_at = (
        attempted_at if current is None else current.created_at
    )

    conn.execute(
        """
        INSERT INTO change_event_resolutions (
            change_event_id, status, attempts,
            first_attempt_at, last_attempt_at,
            resolved_at, result_belief_id,
            error_type, error_message,
            orchestrator_version,
            created_at, updated_at
        )
        VALUES (?, 'FAILED', ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?, ?)
        ON CONFLICT(change_event_id) DO UPDATE SET
            status = 'FAILED',
            attempts = excluded.attempts,
            first_attempt_at = excluded.first_attempt_at,
            last_attempt_at = excluded.last_attempt_at,
            resolved_at = NULL,
            result_belief_id = NULL,
            error_type = NULL,
            error_message = NULL,
            orchestrator_version = excluded.orchestrator_version,
            updated_at = excluded.updated_at
        """,
        (
            change_event_id,
            attempts,
            first_attempt_at,
            attempted_at,
            ORCHESTRATOR_VERSION,
            created_at,
            attempted_at,
        ),
    )
    conn.commit()
    return attempts


def _mark_success(
    conn: sqlite3.Connection,
    change_event_id: str,
    belief_id: str,
    resolved_at: str,
) -> None:
    conn.execute(
        """
        UPDATE change_event_resolutions
        SET status = 'RESOLVED',
            resolved_at = ?,
            result_belief_id = ?,
            error_type = NULL,
            error_message = NULL,
            updated_at = ?
        WHERE change_event_id = ?
        """,
        (
            resolved_at,
            belief_id,
            resolved_at,
            change_event_id,
        ),
    )
    conn.commit()


def _mark_failure(
    conn: sqlite3.Connection,
    change_event_id: str,
    error: Exception,
) -> ResolutionStatus:
    now = utc_now()
    conn.execute(
        """
        UPDATE change_event_resolutions
        SET status = 'FAILED',
            error_type = ?,
            error_message = ?,
            updated_at = ?
        WHERE change_event_id = ?
        """,
        (
            error.__class__.__name__,
            str(error),
            now,
            change_event_id,
        ),
    )
    conn.commit()

    status = get_resolution_status(conn, change_event_id)
    if status is None:
        raise RuntimeError(
            f"missing resolution status after failure for {change_event_id}"
        )
    return status


def resolve_change_event(
    conn: sqlite3.Connection,
    event: ChangeEvent,
    *,
    as_of: str | None = None,
    stale_after_days: int | None = None,
) -> ResolutionResult:
    if event.event_type != EVENT_TYPE:
        raise ValueError(
            f"unsupported change event type: {event.event_type}"
        )

    ensure_resolution_schema(conn)
    existing = get_resolution_status(conn, event.change_event_id)
    if existing is not None and existing.status == "RESOLVED":
        return ResolutionResult(
            change_event_id=event.change_event_id,
            status="SKIPPED",
            attempts=existing.attempts,
            belief_id=existing.result_belief_id,
        )

    attempted_at = utc_now()
    attempts = _record_attempt(
        conn,
        event.change_event_id,
        attempted_at=attempted_at,
    )

    try:
        belief = resolve_belief(
            conn,
            event.subject_type,
            event.subject_id,
            event.field,
            as_of=as_of or attempted_at,
            stale_after_days=stale_after_days,
        )
        if belief is None:
            raise RuntimeError(
                "resolver returned no Belief for a ChangeEvent backed by "
                f"observation {event.observation_id}"
            )

        resolved_at = utc_now()
        _mark_success(
            conn,
            event.change_event_id,
            belief.belief_id,
            resolved_at,
        )
        return ResolutionResult(
            change_event_id=event.change_event_id,
            status="RESOLVED",
            attempts=attempts,
            belief_id=belief.belief_id,
        )
    except Exception as error:
        status = _mark_failure(
            conn,
            event.change_event_id,
            error,
        )
        return ResolutionResult(
            change_event_id=event.change_event_id,
            status="FAILED",
            attempts=status.attempts,
            error_type=status.error_type,
            error_message=status.error_message,
        )


def process_pending_change_events(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    as_of: str | None = None,
    stale_after_days: int | None = None,
) -> list[ResolutionResult]:
    if limit <= 0:
        raise ValueError("limit must be > 0")
    if stale_after_days is not None and stale_after_days < 0:
        raise ValueError("stale_after_days must be >= 0")

    ensure_resolution_schema(conn)

    run_as_of = as_of or utc_now()
    events = _pending_change_events(conn, limit)

    results: list[ResolutionResult] = []
    for event in events:
        result = resolve_change_event(
            conn,
            event,
            as_of=run_as_of,
            stale_after_days=stale_after_days,
        )
        results.append(result)

    return results
