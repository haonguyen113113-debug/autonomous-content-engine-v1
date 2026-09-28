from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Any

from .belief import Belief, get_current_belief, ensure_belief_schema
from .observation import (
    Observation,
    canonical_json,
    ensure_observation_schema,
    list_observations,
)
from .source_registry import (
    TRUST_TIERS,
    ensure_source_schema,
    get_source_revision,
    get_source,
)

DETECTOR_VERSION = "change-detector-v0.1"
EVENT_TYPE = "REASSESSMENT_REQUIRED"
# Semantic contract:
# - Change Detection classifies evidence that requires reassessment.
# - VALUE_CHANGE means the new observation differs from the previous
#   observation; it does not assert that the real-world state changed.
# - BELIEF_MISMATCH means the new observation disagrees with the current
#   belief.
# - EVIDENCE_UPDATE means the value is unchanged but the new evidence has
#   a stronger trust tier than the evidence supporting the current belief.
# - BELIEF_STATUS_REQUIRES_REASSESSMENT means the current belief is no
#   longer in a resolved state.
# - Passing time alone does not emit a ChangeEvent. A new observation is
#   required for the detector to evaluate new evidence.
REASON_CODES = {
    "INITIAL_OBSERVATION",
    "VALUE_CHANGE",
    "BELIEF_MISMATCH",
    "EVIDENCE_UPDATE",
    "BELIEF_STATUS_REQUIRES_REASSESSMENT",
}
TRUST_RANKS = {"primary": 3, "secondary": 2, "discovery_only": 1}


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


def _event_id(
    observation_id: str,
    subject_type: str,
    subject_id: str,
    field: str,
    reasons: tuple[str, ...],
    belief_id: str | None,
) -> str:
    signature = {
        "observation_id": observation_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "field": field,
        "reasons": reasons,
        "belief_id": belief_id,
        "detector_version": DETECTOR_VERSION,
    }
    digest = hashlib.sha256(
        canonical_json(signature).encode("utf-8")
    ).hexdigest()
    return f"change:{digest[:24]}"


@dataclass(frozen=True)
class ChangeEvent:
    change_event_id: str
    observation_id: str
    subject_type: str
    subject_id: str
    field: str
    event_type: str
    reason_codes: tuple[str, ...]
    previous_observation_id: str | None
    previous_value: Any
    observed_value: Any
    current_belief_id: str | None
    current_belief_value: Any
    detected_at: str
    detector_version: str


def ensure_change_detection_schema(conn: sqlite3.Connection) -> None:
    ensure_source_schema(conn)
    ensure_observation_schema(conn)
    ensure_belief_schema(conn)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS change_events (
            change_event_id TEXT PRIMARY KEY,
            observation_id TEXT NOT NULL,
            subject_type TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            field TEXT NOT NULL,
            event_type TEXT NOT NULL,
            reason_codes_json TEXT NOT NULL,
            previous_observation_id TEXT,
            previous_value_json TEXT,
            observed_value_json TEXT NOT NULL,
            current_belief_id TEXT,
            current_belief_value_json TEXT,
            detected_at TEXT NOT NULL,
            detector_version TEXT NOT NULL,
            UNIQUE(observation_id, detector_version)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_change_events_subject_field
        ON change_events(subject_type, subject_id, field)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_change_events_observation
        ON change_events(observation_id)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS change_detection_cursors (
            detector_scope TEXT PRIMARY KEY,
            last_recorded_at TEXT NOT NULL,
            last_observation_id TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _read_event(row: sqlite3.Row | tuple[Any, ...]) -> ChangeEvent:
    return ChangeEvent(
        change_event_id=row[0],
        observation_id=row[1],
        subject_type=row[2],
        subject_id=row[3],
        field=row[4],
        event_type=row[5],
        reason_codes=tuple(json.loads(row[6])),
        previous_observation_id=row[7],
        previous_value=(
            json.loads(row[8]) if row[8] is not None else None
        ),
        observed_value=json.loads(row[9]),
        current_belief_id=row[10],
        current_belief_value=(
            json.loads(row[11]) if row[11] is not None else None
        ),
        detected_at=row[12],
        detector_version=row[13],
    )


def list_change_events(
    conn: sqlite3.Connection,
    subject_type: str,
    subject_id: str,
    field: str,
) -> list[ChangeEvent]:
    ensure_change_detection_schema(conn)
    rows = conn.execute(
        """
        SELECT change_event_id, observation_id, subject_type, subject_id,
               field, event_type, reason_codes_json,
               previous_observation_id, previous_value_json,
               observed_value_json, current_belief_id,
               current_belief_value_json, detected_at,
               detector_version
        FROM change_events
        WHERE subject_type = ?
          AND subject_id = ?
          AND field = ?
        ORDER BY detected_at ASC, change_event_id ASC
        """,
        (subject_type, subject_id, field),
    ).fetchall()
    return [_read_event(row) for row in rows]


def count_change_events(conn: sqlite3.Connection) -> int:
    ensure_change_detection_schema(conn)
    row = conn.execute("SELECT COUNT(*) FROM change_events").fetchone()
    return int(row[0])


def _observation_trust_rank(
    conn: sqlite3.Connection,
    observation: Observation,
) -> int:
    if observation.source_revision_id:
        revision = get_source_revision(
            conn,
            observation.source_revision_id,
        )
        if revision is None:
            raise ValueError(
                "missing source revision: "
                f"{observation.source_revision_id}"
            )
        return TRUST_RANKS[revision.default_trust_tier]

    source = get_source(conn, observation.source_id)
    if source is None:
        raise ValueError(
            f"missing source registry record: {observation.source_id}"
        )
    return TRUST_RANKS[source.default_trust_tier]


def _supporting_trust_rank(
    conn: sqlite3.Connection,
    belief_id: str,
) -> int:
    rows = conn.execute(
        """
        SELECT o.source_revision_id, o.source_id
        FROM belief_observations bo
        JOIN observations o
          ON o.observation_id = bo.observation_id
        WHERE bo.belief_id = ?
          AND bo.role = 'SUPPORT'
        """,
        (belief_id,),
    ).fetchall()

    ranks: list[int] = []
    for row in rows:
        if row[0]:
            revision = get_source_revision(conn, row[0])
            if revision is not None:
                ranks.append(TRUST_RANKS[revision.default_trust_tier])
                continue
        source = get_source(conn, row[1])
        if source is not None:
            ranks.append(TRUST_RANKS[source.default_trust_tier])

    return max(ranks, default=0)


def _scope_id(
    subject_type: str,
    subject_id: str,
    field: str,
) -> str:
    return f"{subject_type}:{subject_id}:{field}"


def _get_cursor(
    conn: sqlite3.Connection,
    scope_id: str,
) -> tuple[str, str] | None:
    row = conn.execute(
        """
        SELECT last_recorded_at, last_observation_id
        FROM change_detection_cursors
        WHERE detector_scope = ?
        """,
        (scope_id,),
    ).fetchone()
    return None if row is None else (row[0], row[1])


def _save_cursor(
    conn: sqlite3.Connection,
    scope_id: str,
    observation: Observation,
) -> None:
    recorded_at = observation.recorded_at or observation.observed_at
    conn.execute(
        """
        INSERT INTO change_detection_cursors (
            detector_scope, last_recorded_at,
            last_observation_id, updated_at
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(detector_scope) DO UPDATE SET
            last_recorded_at = excluded.last_recorded_at,
            last_observation_id = excluded.last_observation_id,
            updated_at = excluded.updated_at
        """,
        (
            scope_id,
            recorded_at,
            observation.observation_id,
            utc_now(),
        ),
    )


def _is_after_cursor(
    observation: Observation,
    cursor: tuple[str, str] | None,
) -> bool:
    if cursor is None:
        return True

    recorded_at = observation.recorded_at or observation.observed_at
    current_key = (
        _parse_timestamp(recorded_at),
        observation.observation_id,
    )
    cursor_key = (
        _parse_timestamp(cursor[0]),
        cursor[1],
    )
    return current_key > cursor_key


def _previous_observation(
    observations: list[Observation],
    target: Observation,
) -> Observation | None:
    ordered = sorted(
        observations,
        key=lambda observation: (
            _parse_timestamp(
                observation.recorded_at or observation.observed_at
            ),
            observation.observation_id,
        ),
    )
    previous: Observation | None = None
    for observation in ordered:
        if observation.observation_id == target.observation_id:
            break
        previous = observation
    return previous


def _build_reason_codes(
    conn: sqlite3.Connection,
    observation: Observation,
    previous: Observation | None,
    belief: Belief | None,
) -> tuple[str, ...]:
    reasons: set[str] = set()

    if previous is None:
        reasons.add("INITIAL_OBSERVATION")
    elif canonical_json(previous.value) != canonical_json(observation.value):
        reasons.add("VALUE_CHANGE")

    if belief is None:
        pass
    else:
        if canonical_json(belief.current_value) != canonical_json(
            observation.value
        ):
            reasons.add("BELIEF_MISMATCH")

        if belief.status != "RESOLVED":
            reasons.add("BELIEF_STATUS_REQUIRES_REASSESSMENT")

        if (
            belief.status == "RESOLVED"
            and canonical_json(belief.current_value)
            == canonical_json(observation.value)
        ):
            new_rank = _observation_trust_rank(
                conn,
                observation,
            )
            existing_rank = _supporting_trust_rank(
                conn,
                belief.belief_id,
            )
            if new_rank > existing_rank:
                reasons.add("EVIDENCE_UPDATE")

    return tuple(sorted(reasons))


def detect_changes(
    conn: sqlite3.Connection,
    subject_type: str,
    subject_id: str,
    field: str,
    *,
    detector_version: str = DETECTOR_VERSION,
) -> list[ChangeEvent]:
    if detector_version != DETECTOR_VERSION:
        raise ValueError(
            f"unsupported detector_version: {detector_version}"
        )

    ensure_change_detection_schema(conn)

    scope_id = _scope_id(subject_type, subject_id, field)
    cursor = _get_cursor(conn, scope_id)

    observations = [
        observation
        for observation in list_observations(conn, subject_id)
        if observation.subject_type == subject_type
        and observation.field == field
    ]

    new_observations = sorted(
        [
            observation
            for observation in observations
            if _is_after_cursor(observation, cursor)
        ],
        key=lambda item: (
            _parse_timestamp(item.recorded_at or item.observed_at),
            item.observation_id,
        ),
    )

    if not new_observations:
        return []

    created_events: list[ChangeEvent] = []

    for observation in new_observations:
        previous = _previous_observation(
            observations,
            observation,
        )
        belief = get_current_belief(
            conn,
            subject_type,
            subject_id,
            field,
        )
        reasons = _build_reason_codes(
            conn,
            observation,
            previous,
            belief,
        )

        if reasons:
            event = ChangeEvent(
                change_event_id=_event_id(
                    observation.observation_id,
                    subject_type,
                    subject_id,
                    field,
                    reasons,
                    belief.belief_id if belief else None,
                ),
                observation_id=observation.observation_id,
                subject_type=subject_type,
                subject_id=subject_id,
                field=field,
                event_type=EVENT_TYPE,
                reason_codes=reasons,
                previous_observation_id=(
                    previous.observation_id
                    if previous
                    else None
                ),
                previous_value=(
                    previous.value if previous else None
                ),
                observed_value=observation.value,
                current_belief_id=(
                    belief.belief_id if belief else None
                ),
                current_belief_value=(
                    belief.current_value if belief else None
                ),
                detected_at=utc_now(),
                detector_version=detector_version,
            )

            conn.execute(
                """
                INSERT OR IGNORE INTO change_events (
                    change_event_id, observation_id,
                    subject_type, subject_id, field,
                    event_type, reason_codes_json,
                    previous_observation_id,
                    previous_value_json, observed_value_json,
                    current_belief_id, current_belief_value_json,
                    detected_at, detector_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.change_event_id,
                    event.observation_id,
                    event.subject_type,
                    event.subject_id,
                    event.field,
                    event.event_type,
                    canonical_json(list(event.reason_codes)),
                    event.previous_observation_id,
                    (
                        canonical_json(event.previous_value)
                        if event.previous_value is not None
                        else None
                    ),
                    canonical_json(event.observed_value),
                    event.current_belief_id,
                    (
                        canonical_json(event.current_belief_value)
                        if event.current_belief_value is not None
                        else None
                    ),
                    event.detected_at,
                    event.detector_version,
                ),
            )
            created_events.append(event)

        _save_cursor(
            conn,
            scope_id,
            observation,
        )

    conn.commit()
    return created_events
