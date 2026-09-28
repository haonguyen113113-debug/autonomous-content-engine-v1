from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import sqlite3
import uuid

from .belief import Belief, ensure_belief_schema, resolve_belief
from .change_detection import (
    EVENT_TYPE,
    ChangeEvent,
    ensure_change_detection_schema,
)
from .source_registry import ensure_source_schema

ORCHESTRATOR_VERSION = "resolution-orchestrator-v0.2"
RESOLUTION_STATUSES = {"FAILED", "RESOLVED", "DEAD_LETTER"}
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_LEASE_SECONDS = 60
DEFAULT_BACKOFF_BASE_SECONDS = 5
DEFAULT_BACKOFF_MAX_SECONDS = 300


class LeaseLostError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_timestamp(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _future_timestamp(base: str, seconds: int) -> str:
    return (
        _parse_timestamp(base) + timedelta(seconds=seconds)
    ).replace(microsecond=0).isoformat()


def _backoff_seconds(
    attempts: int,
    *,
    base_seconds: int,
    max_seconds: int,
) -> int:
    if base_seconds <= 0:
        return 0
    if max_seconds < base_seconds:
        max_seconds = base_seconds
    return min(
        max_seconds,
        base_seconds * (2 ** max(attempts - 1, 0)),
    )


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
    lease_owner: str | None = None
    lease_until: str | None = None
    next_attempt_at: str | None = None
    max_attempts: int = DEFAULT_MAX_ATTEMPTS


@dataclass(frozen=True)
class ResolutionResult:
    change_event_id: str
    status: str
    attempts: int
    belief_id: str | None = None
    error_type: str | None = None
    error_message: str | None = None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {
        row[1]
        for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }


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
            lease_owner TEXT,
            lease_until TEXT,
            next_attempt_at TEXT,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            CHECK(status IN ('FAILED', 'RESOLVED', 'DEAD_LETTER')),
            CHECK(attempts >= 0),
            CHECK(max_attempts > 0)
        )
        """
    )

    columns = _table_columns(conn, "change_event_resolutions")
    additions = {
        "lease_owner": "ALTER TABLE change_event_resolutions ADD COLUMN lease_owner TEXT",
        "lease_until": "ALTER TABLE change_event_resolutions ADD COLUMN lease_until TEXT",
        "next_attempt_at": "ALTER TABLE change_event_resolutions ADD COLUMN next_attempt_at TEXT",
        "max_attempts": "ALTER TABLE change_event_resolutions ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 5",
    }
    for column, sql in additions.items():
        if column not in columns:
            conn.execute(sql)

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_change_event_resolutions_status
        ON change_event_resolutions(status)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_change_event_resolutions_lease
        ON change_event_resolutions(lease_until)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_change_event_resolutions_next_attempt
        ON change_event_resolutions(next_attempt_at)
        """
    )
    conn.commit()


def _read_resolution_status(
    row: sqlite3.Row | tuple,
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
        lease_owner=row[12],
        lease_until=row[13],
        next_attempt_at=row[14],
        max_attempts=int(row[15]),
    )




def _read_resolution_status_row(row: sqlite3.Row | tuple) -> ResolutionStatus:
    return _read_resolution_status(row)


def _get_resolution_status_no_ensure(
    conn: sqlite3.Connection,
    change_event_id: str,
) -> ResolutionStatus | None:
    row = conn.execute(
        """
        SELECT change_event_id, status, attempts,
               first_attempt_at, last_attempt_at, resolved_at,
               result_belief_id, error_type, error_message,
               orchestrator_version, created_at, updated_at,
               lease_owner, lease_until, next_attempt_at,
               max_attempts
        FROM change_event_resolutions
        WHERE change_event_id = ?
        """,
        (change_event_id,),
    ).fetchone()
    return None if row is None else _read_resolution_status_row(row)

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
               orchestrator_version, created_at, updated_at,
               lease_owner, lease_until, next_attempt_at,
               max_attempts
        FROM change_event_resolutions
        WHERE change_event_id = ?
        """,
        (change_event_id,),
    ).fetchone()
    return None if row is None else _read_resolution_status(row)


def _read_change_event(
    row: sqlite3.Row | tuple,
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
    *,
    now: str,
    exclude_event_ids: set[str] | None = None,
) -> list[ChangeEvent]:
    params: list[object] = [EVENT_TYPE, now, now]
    exclude_sql = ""
    if exclude_event_ids:
        placeholders = ", ".join("?" for _ in exclude_event_ids)
        exclude_sql = f" AND ce.change_event_id NOT IN ({placeholders})"
        params.extend(sorted(exclude_event_ids))
    params.append(limit)

    rows = conn.execute(
        f"""
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
              OR (
                  cer.status = 'FAILED'
                  AND cer.attempts < cer.max_attempts
                  AND (
                      cer.next_attempt_at IS NULL
                      OR cer.next_attempt_at <= ?
                  )
                  AND (
                      cer.lease_until IS NULL
                      OR cer.lease_until <= ?
                  )
              )
          )
          {exclude_sql}
        ORDER BY ce.detected_at ASC, ce.change_event_id ASC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [_read_change_event(row) for row in rows]


def _begin_claim(conn: sqlite3.Connection) -> None:
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")


def _claim_event_row(
    conn: sqlite3.Connection,
    event: ChangeEvent,
    *,
    worker_id: str,
    lease_seconds: int,
    max_attempts: int,
    backoff_base_seconds: int,
    backoff_max_seconds: int,
    now: str,
) -> ResolutionStatus | None:
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be > 0")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be > 0")
    if backoff_base_seconds < 0:
        raise ValueError("backoff_base_seconds must be >= 0")
    if backoff_max_seconds < 0:
        raise ValueError("backoff_max_seconds must be >= 0")

    current = _get_resolution_status_no_ensure(
        conn,
        event.change_event_id,
    )
    if current is not None and current.status == "RESOLVED":
        conn.commit()
        return current
    if current is not None and current.status == "DEAD_LETTER":
        conn.commit()
        return current

    if current is not None:
        if current.lease_until is not None and _parse_timestamp(
            current.lease_until
        ) > _parse_timestamp(now):
            conn.commit()
            return current
        if current.next_attempt_at is not None and _parse_timestamp(
            current.next_attempt_at
        ) > _parse_timestamp(now):
            conn.commit()
            return current
        effective_max = current.max_attempts
        attempts = current.attempts
        first_attempt_at = current.first_attempt_at
        created_at = current.created_at
    else:
        effective_max = max_attempts
        attempts = 0
        first_attempt_at = None
        created_at = now

    if attempts >= effective_max:
        if current is None:
            raise RuntimeError(
                f"cannot dead-letter uninitialized event {event.change_event_id}"
            )
        conn.execute(
            """
            UPDATE change_event_resolutions
            SET status = 'DEAD_LETTER',
                lease_owner = NULL,
                lease_until = NULL,
                next_attempt_at = NULL,
                updated_at = ?
            WHERE change_event_id = ?
            """,
            (now, event.change_event_id),
        )
        conn.commit()
        return get_resolution_status(conn, event.change_event_id)

    attempts += 1
    first_attempt_at = first_attempt_at or now
    lease_until = _future_timestamp(now, lease_seconds)

    conn.execute(
        """
        INSERT INTO change_event_resolutions (
            change_event_id, status, attempts,
            first_attempt_at, last_attempt_at,
            resolved_at, result_belief_id,
            error_type, error_message,
            orchestrator_version, created_at, updated_at,
            lease_owner, lease_until, next_attempt_at, max_attempts
        )
        VALUES (?, 'FAILED', ?, ?, ?, NULL, NULL, NULL, NULL,
                ?, ?, ?, ?, ?, NULL, ?)
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
            updated_at = excluded.updated_at,
            lease_owner = excluded.lease_owner,
            lease_until = excluded.lease_until,
            next_attempt_at = NULL,
            max_attempts = excluded.max_attempts
        """,
        (
            event.change_event_id,
            attempts,
            first_attempt_at,
            now,
            ORCHESTRATOR_VERSION,
            created_at,
            now,
            worker_id,
            lease_until,
            effective_max,
        ),
    )
    conn.commit()
    return get_resolution_status(conn, event.change_event_id)


def claim_change_event(
    conn: sqlite3.Connection,
    event: ChangeEvent,
    *,
    worker_id: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> ResolutionStatus | None:
    ensure_resolution_schema(conn)
    now = utc_now()
    _begin_claim(conn)
    try:
        return _claim_event_row(
            conn,
            event,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            max_attempts=max_attempts,
            backoff_base_seconds=DEFAULT_BACKOFF_BASE_SECONDS,
            backoff_max_seconds=DEFAULT_BACKOFF_MAX_SECONDS,
            now=now,
        )
    except Exception:
        conn.rollback()
        raise


def claim_pending_change_event(
    conn: sqlite3.Connection,
    *,
    worker_id: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    exclude_event_ids: set[str] | None = None,
) -> ChangeEvent | None:
    ensure_resolution_schema(conn)
    now = utc_now()
    _begin_claim(conn)
    try:
        candidates = _pending_change_events(
            conn,
            1,
            now=now,
            exclude_event_ids=exclude_event_ids,
        )
        if not candidates:
            conn.rollback()
            return None
        event = candidates[0]
        status = _claim_event_row(
            conn,
            event,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            max_attempts=max_attempts,
            backoff_base_seconds=DEFAULT_BACKOFF_BASE_SECONDS,
            backoff_max_seconds=DEFAULT_BACKOFF_MAX_SECONDS,
            now=now,
        )
        if status is None or status.lease_owner != worker_id:
            conn.rollback()
            return None
        return event
    except Exception:
        conn.rollback()
        raise


def renew_change_event_lease(
    conn: sqlite3.Connection,
    change_event_id: str,
    *,
    worker_id: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> ResolutionStatus:
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be > 0")
    ensure_resolution_schema(conn)
    now = utc_now()
    lease_until = _future_timestamp(now, lease_seconds)
    cur = conn.execute(
        """
        UPDATE change_event_resolutions
        SET lease_until = ?, updated_at = ?
        WHERE change_event_id = ?
          AND lease_owner = ?
          AND status = 'FAILED'
          AND lease_until IS NOT NULL
        """,
        (lease_until, now, change_event_id, worker_id),
    )
    conn.commit()
    if cur.rowcount != 1:
        raise LeaseLostError(
            f"worker {worker_id} does not own lease for {change_event_id}"
        )
    status = get_resolution_status(conn, change_event_id)
    if status is None:
        raise RuntimeError(
            f"missing resolution status after lease renewal for {change_event_id}"
        )
    return status


def _mark_success(
    conn: sqlite3.Connection,
    change_event_id: str,
    belief_id: str,
    resolved_at: str,
    *,
    worker_id: str,
) -> None:
    cur = conn.execute(
        """
        UPDATE change_event_resolutions
        SET status = 'RESOLVED',
            resolved_at = ?,
            result_belief_id = ?,
            error_type = NULL,
            error_message = NULL,
            lease_owner = NULL,
            lease_until = NULL,
            next_attempt_at = NULL,
            updated_at = ?
        WHERE change_event_id = ?
          AND lease_owner = ?
          AND status = 'FAILED'
        """,
        (
            resolved_at,
            belief_id,
            resolved_at,
            change_event_id,
            worker_id,
        ),
    )
    conn.commit()
    if cur.rowcount != 1:
        raise LeaseLostError(
            f"worker {worker_id} lost lease for {change_event_id}"
        )


def _mark_failure(
    conn: sqlite3.Connection,
    change_event_id: str,
    error: Exception,
    *,
    worker_id: str,
    backoff_base_seconds: int,
    backoff_max_seconds: int,
) -> ResolutionStatus:
    now = utc_now()
    current = get_resolution_status(conn, change_event_id)
    if current is None:
        raise RuntimeError(
            f"missing resolution status after failure for {change_event_id}"
        )
    next_attempt_at = None
    next_status = "FAILED"
    if current.attempts >= current.max_attempts:
        next_status = "DEAD_LETTER"
    else:
        delay = _backoff_seconds(
            current.attempts,
            base_seconds=backoff_base_seconds,
            max_seconds=backoff_max_seconds,
        )
        next_attempt_at = _future_timestamp(now, delay) if delay else now

    cur = conn.execute(
        """
        UPDATE change_event_resolutions
        SET status = ?,
            error_type = ?,
            error_message = ?,
            lease_owner = NULL,
            lease_until = NULL,
            next_attempt_at = ?,
            updated_at = ?
        WHERE change_event_id = ?
          AND lease_owner = ?
          AND status = 'FAILED'
        """,
        (
            next_status,
            error.__class__.__name__,
            str(error),
            next_attempt_at,
            now,
            change_event_id,
            worker_id,
        ),
    )
    conn.commit()
    if cur.rowcount != 1:
        raise LeaseLostError(
            f"worker {worker_id} lost lease for {change_event_id}"
        )

    status = get_resolution_status(conn, change_event_id)
    if status is None:
        raise RuntimeError(
            f"missing resolution status after failure for {change_event_id}"
        )
    return status


def _resolve_claimed_change_event(
    conn: sqlite3.Connection,
    event: ChangeEvent,
    *,
    worker_id: str,
    as_of: str | None,
    stale_after_days: int | None,
    backoff_base_seconds: int,
    backoff_max_seconds: int,
) -> ResolutionResult:
    status = get_resolution_status(conn, event.change_event_id)
    if status is None or status.lease_owner != worker_id:
        raise LeaseLostError(
            f"worker {worker_id} does not own lease for {event.change_event_id}"
        )

    try:
        belief = resolve_belief(
            conn,
            event.subject_type,
            event.subject_id,
            event.field,
            as_of=as_of or utc_now(),
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
            worker_id=worker_id,
        )
        return ResolutionResult(
            change_event_id=event.change_event_id,
            status="RESOLVED",
            attempts=status.attempts,
            belief_id=belief.belief_id,
        )
    except Exception as error:
        failed = _mark_failure(
            conn,
            event.change_event_id,
            error,
            worker_id=worker_id,
            backoff_base_seconds=backoff_base_seconds,
            backoff_max_seconds=backoff_max_seconds,
        )
        return ResolutionResult(
            change_event_id=event.change_event_id,
            status=failed.status,
            attempts=failed.attempts,
            error_type=failed.error_type,
            error_message=failed.error_message,
        )


def resolve_change_event(
    conn: sqlite3.Connection,
    event: ChangeEvent,
    *,
    as_of: str | None = None,
    stale_after_days: int | None = None,
    worker_id: str | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_base_seconds: int = DEFAULT_BACKOFF_BASE_SECONDS,
    backoff_max_seconds: int = DEFAULT_BACKOFF_MAX_SECONDS,
) -> ResolutionResult:
    if event.event_type != EVENT_TYPE:
        raise ValueError(
            f"unsupported change event type: {event.event_type}"
        )
    if stale_after_days is not None and stale_after_days < 0:
        raise ValueError("stale_after_days must be >= 0")
    if backoff_base_seconds < 0:
        raise ValueError("backoff_base_seconds must be >= 0")
    if backoff_max_seconds < 0:
        raise ValueError("backoff_max_seconds must be >= 0")

    ensure_resolution_schema(conn)
    owner = worker_id or f"direct:{uuid.uuid4().hex}"
    now = utc_now()

    _begin_claim(conn)
    try:
        claimed = _claim_event_row(
            conn,
            event,
            worker_id=owner,
            lease_seconds=lease_seconds,
            max_attempts=max_attempts,
            backoff_base_seconds=backoff_base_seconds,
            backoff_max_seconds=backoff_max_seconds,
            now=now,
        )
        if claimed is None:
            raise RuntimeError(
                f"unable to claim change event {event.change_event_id}"
            )
    except Exception:
        conn.rollback()
        raise

    if claimed.status == "RESOLVED":
        return ResolutionResult(
            change_event_id=event.change_event_id,
            status="SKIPPED",
            attempts=claimed.attempts,
            belief_id=claimed.result_belief_id,
        )
    if claimed.status == "DEAD_LETTER":
        return ResolutionResult(
            change_event_id=event.change_event_id,
            status="DEAD_LETTER",
            attempts=claimed.attempts,
            error_type=claimed.error_type,
            error_message=claimed.error_message,
        )
    if claimed.lease_owner != owner:
        return ResolutionResult(
            change_event_id=event.change_event_id,
            status="SKIPPED",
            attempts=claimed.attempts,
            error_type="LeaseBusy",
            error_message="change event is currently leased by another worker",
        )
    if claimed.next_attempt_at is not None and _parse_timestamp(
        claimed.next_attempt_at
    ) > _parse_timestamp(now):
        return ResolutionResult(
            change_event_id=event.change_event_id,
            status="SKIPPED",
            attempts=claimed.attempts,
            error_type="RetryBackoff",
            error_message="change event is waiting for its retry backoff",
        )

    return _resolve_claimed_change_event(
        conn,
        event,
        worker_id=owner,
        as_of=as_of,
        stale_after_days=stale_after_days,
        backoff_base_seconds=backoff_base_seconds,
        backoff_max_seconds=backoff_max_seconds,
    )


def process_pending_change_events(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    as_of: str | None = None,
    stale_after_days: int | None = None,
    worker_id: str | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_base_seconds: int = DEFAULT_BACKOFF_BASE_SECONDS,
    backoff_max_seconds: int = DEFAULT_BACKOFF_MAX_SECONDS,
) -> list[ResolutionResult]:
    if limit <= 0:
        raise ValueError("limit must be > 0")
    if stale_after_days is not None and stale_after_days < 0:
        raise ValueError("stale_after_days must be >= 0")
    if backoff_base_seconds < 0:
        raise ValueError("backoff_base_seconds must be >= 0")
    if backoff_max_seconds < 0:
        raise ValueError("backoff_max_seconds must be >= 0")

    ensure_resolution_schema(conn)
    owner = worker_id or f"worker:{uuid.uuid4().hex}"
    run_as_of = as_of or utc_now()

    results: list[ResolutionResult] = []
    processed_event_ids: set[str] = set()
    while len(results) < limit:
        event = claim_pending_change_event(
            conn,
            worker_id=owner,
            lease_seconds=lease_seconds,
            max_attempts=max_attempts,
            exclude_event_ids=processed_event_ids,
        )
        if event is None:
            break
        result = _resolve_claimed_change_event(
            conn,
            event,
            worker_id=owner,
            as_of=run_as_of,
            stale_after_days=stale_after_days,
            backoff_base_seconds=backoff_base_seconds,
            backoff_max_seconds=backoff_max_seconds,
        )
        results.append(result)
        processed_event_ids.add(event.change_event_id)

    return results
