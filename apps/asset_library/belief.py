from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import sqlite3
from typing import Any

from .observation import Observation, canonical_json, list_observations
from .source_registry import TRUST_TIERS

RESOLVER_VERSION = "belief-resolver-v0.1"
BELIEF_STATUSES = {"RESOLVED", "CONFLICTED", "UNCERTAIN", "STALE"}
BELIEF_ROLES = {"SUPPORT", "CONFLICT", "COMPETING"}
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


def _observation_sort_key(
    observation: Observation,
    trust_tier: str,
) -> tuple[int, datetime, str]:
    if trust_tier not in TRUST_TIERS:
        raise ValueError(f"unsupported trust tier: {trust_tier}")
    return (
        TRUST_RANKS[trust_tier],
        _parse_timestamp(observation.observed_at),
        observation.observation_id,
    )


def _belief_id(signature: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(signature).encode("utf-8")).hexdigest()
    return f"belief:{digest[:24]}"


def _belief_signature(
    *,
    subject_type: str,
    subject_id: str,
    field: str,
    current_value: Any,
    status: str,
    confidence: float,
    valid_from: str | None,
    valid_to: str | None,
    resolver_version: str,
    evidence: list[tuple[str, str]],
) -> dict[str, Any]:
    return {
        "subject_type": subject_type,
        "subject_id": subject_id,
        "field": field,
        "current_value": current_value,
        "status": status,
        "confidence": confidence,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "resolver_version": resolver_version,
        "evidence": sorted(evidence),
    }


@dataclass(frozen=True)
class Belief:
    belief_id: str
    subject_type: str
    subject_id: str
    field: str
    current_value: Any
    status: str
    confidence: float
    valid_from: str | None
    valid_to: str | None
    resolved_at: str
    resolver_version: str
    resolution_reason: str
    created_at: str
    is_current: bool = True


def ensure_belief_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS beliefs (
            belief_id TEXT PRIMARY KEY,
            subject_type TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            field TEXT NOT NULL,
            current_value_json TEXT,
            status TEXT NOT NULL,
            confidence REAL NOT NULL,
            valid_from TEXT,
            valid_to TEXT,
            resolved_at TEXT NOT NULL,
            resolver_version TEXT NOT NULL,
            resolution_reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_current INTEGER NOT NULL DEFAULT 1,
            CHECK(status IN ('RESOLVED', 'CONFLICTED', 'UNCERTAIN', 'STALE')),
            CHECK(confidence >= 0.0 AND confidence <= 1.0)
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_current_belief
        ON beliefs(subject_type, subject_id, field)
        WHERE is_current = 1
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_beliefs_subject_field
        ON beliefs(subject_type, subject_id, field)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS belief_observations (
            belief_id TEXT NOT NULL,
            observation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            PRIMARY KEY(belief_id, observation_id),
            CHECK(role IN ('SUPPORT', 'CONFLICT', 'COMPETING'))
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_belief_observations_observation
        ON belief_observations(observation_id)
        """
    )
    conn.commit()


def _read_belief(row: sqlite3.Row | tuple[Any, ...]) -> Belief:
    value = json.loads(row[4]) if row[4] is not None else None
    return Belief(
        belief_id=row[0],
        subject_type=row[1],
        subject_id=row[2],
        field=row[3],
        current_value=value,
        status=row[5],
        confidence=float(row[6]),
        valid_from=row[7],
        valid_to=row[8],
        resolved_at=row[9],
        resolver_version=row[10],
        resolution_reason=row[11],
        created_at=row[12],
        is_current=bool(row[13]),
    )


def get_current_belief(
    conn: sqlite3.Connection,
    subject_type: str,
    subject_id: str,
    field: str,
) -> Belief | None:
    row = conn.execute(
        """
        SELECT belief_id, subject_type, subject_id, field,
               current_value_json, status, confidence,
               valid_from, valid_to, resolved_at,
               resolver_version, resolution_reason, created_at,
               is_current
        FROM beliefs
        WHERE subject_type = ?
          AND subject_id = ?
          AND field = ?
          AND is_current = 1
        """,
        (subject_type, subject_id, field),
    ).fetchone()
    return None if row is None else _read_belief(row)


def list_belief_history(
    conn: sqlite3.Connection,
    subject_type: str,
    subject_id: str,
    field: str,
) -> list[Belief]:
    rows = conn.execute(
        """
        SELECT belief_id, subject_type, subject_id, field,
               current_value_json, status, confidence,
               valid_from, valid_to, resolved_at,
               resolver_version, resolution_reason, created_at,
               is_current
        FROM beliefs
        WHERE subject_type = ?
          AND subject_id = ?
          AND field = ?
        ORDER BY created_at ASC, belief_id ASC
        """,
        (subject_type, subject_id, field),
    ).fetchall()
    return [_read_belief(row) for row in rows]


def list_belief_observations(
    conn: sqlite3.Connection,
    belief_id: str,
) -> list[tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT observation_id, role
        FROM belief_observations
        WHERE belief_id = ?
        ORDER BY observation_id ASC
        """,
        (belief_id,),
    ).fetchall()
    return [(row[0], row[1]) for row in rows]


def _source_state(
    conn: sqlite3.Connection,
    source_id: str,
) -> tuple[str, bool]:
    row = conn.execute(
        """
        SELECT default_trust_tier, active
        FROM sources
        WHERE source_id = ?
        """,
        (source_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"missing source registry record: {source_id}")
    trust_tier = row[0]
    if trust_tier not in TRUST_TIERS:
        raise ValueError(
            f"unsupported source trust tier for {source_id}: {trust_tier}"
        )
    return trust_tier, bool(row[1])


def _applicable(observation: Observation, as_of: datetime) -> bool:
    if observation.effective_from is not None:
        if as_of < _parse_timestamp(observation.effective_from):
            return False
    if observation.effective_to is not None:
        if as_of > _parse_timestamp(observation.effective_to):
            return False
    return True


def _insert_belief_version(
    conn: sqlite3.Connection,
    belief: Belief,
    evidence: list[tuple[str, str]],
) -> None:
    current = get_current_belief(
        conn,
        belief.subject_type,
        belief.subject_id,
        belief.field,
    )
    if current is not None:
        conn.execute(
            """
            UPDATE beliefs
            SET is_current = 0,
                valid_to = CASE
                    WHEN valid_to IS NULL THEN ?
                    ELSE valid_to
                END
            WHERE belief_id = ?
            """,
            (belief.resolved_at, current.belief_id),
        )

    conn.execute(
        """
        INSERT INTO beliefs (
            belief_id, subject_type, subject_id, field,
            current_value_json, status, confidence,
            valid_from, valid_to, resolved_at,
            resolver_version, resolution_reason,
            created_at, is_current
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            belief.belief_id,
            belief.subject_type,
            belief.subject_id,
            belief.field,
            None
            if belief.current_value is None
            else canonical_json(belief.current_value),
            belief.status,
            belief.confidence,
            belief.valid_from,
            belief.valid_to,
            belief.resolved_at,
            belief.resolver_version,
            belief.resolution_reason,
            belief.created_at,
        ),
    )

    conn.executemany(
        """
        INSERT INTO belief_observations (
            belief_id, observation_id, role
        )
        VALUES (?, ?, ?)
        """,
        [
            (belief.belief_id, observation_id, role)
            for observation_id, role in evidence
        ],
    )
    conn.commit()


def resolve_belief(
    conn: sqlite3.Connection,
    subject_type: str,
    subject_id: str,
    field: str,
    *,
    as_of: str | None = None,
    stale_after_days: int | None = None,
    resolver_version: str = RESOLVER_VERSION,
) -> Belief | None:
    if stale_after_days is not None and stale_after_days < 0:
        raise ValueError("stale_after_days must be >= 0")

    ensure_belief_schema(conn)
    as_of_dt = _parse_timestamp(as_of or utc_now())

    observations = [
        observation
        for observation in list_observations(conn, subject_id)
        if observation.subject_type == subject_type
        and observation.field == field
    ]
    if not observations:
        return None

    source_meta: dict[str, tuple[str, bool]] = {}
    for observation in observations:
        source_meta[observation.source_id] = _source_state(
            conn,
            observation.source_id,
        )

    applicable = [
        observation
        for observation in observations
        if _applicable(observation, as_of_dt)
    ]
    active = [
        observation
        for observation in applicable
        if source_meta[observation.source_id][1]
    ]

    if not active:
        latest_observed = max(
            observations,
            key=lambda item: _parse_timestamp(item.observed_at),
        )
        status = "UNCERTAIN"
        current_value = latest_observed.value
        confidence = 0.0
        valid_from = (
            latest_observed.effective_from
            or latest_observed.observed_at
        )
        valid_to = latest_observed.effective_to
        resolution_reason = (
            "No currently applicable observation has an active source."
        )
        evidence = [
            (obs.observation_id, "COMPETING")
            for obs in observations
        ]
    else:
        grouped: dict[str, list[Observation]] = {}
        for observation in active:
            grouped.setdefault(
                canonical_json(observation.value),
                [],
            ).append(observation)

        best_by_value: list[tuple[Observation, str]] = []
        for value_key, group in grouped.items():
            best = max(
                group,
                key=lambda item: _observation_sort_key(
                    item,
                    source_meta[item.source_id][0],
                ),
            )
            best_by_value.append((best, value_key))

        best_by_value.sort(
            key=lambda item: _observation_sort_key(
                item[0],
                source_meta[item[0].source_id][0],
            ),
            reverse=True,
        )

        winning_observation, winning_value_key = best_by_value[0]
        winning_tier = source_meta[winning_observation.source_id][0]

        conflicted = False
        if len(best_by_value) > 1:
            second_observation, _ = best_by_value[1]
            second_tier = source_meta[second_observation.source_id][0]
            conflicted = (
                TRUST_RANKS[winning_tier] == TRUST_RANKS[second_tier]
                and _parse_timestamp(
                    winning_observation.observed_at
                )
                == _parse_timestamp(second_observation.observed_at)
            )

        winning_age = as_of_dt - _parse_timestamp(
            winning_observation.observed_at
        )

        if conflicted:
            status = "CONFLICTED"
            current_value = None
            confidence = 0.0
            valid_from = None
            valid_to = None
            resolution_reason = (
                "Multiple active observations have different values with "
                "the same trust tier and observed_at timestamp."
            )
            evidence = [
                (observation.observation_id, "COMPETING")
                for observation in active
            ]
        elif stale_after_days is not None and winning_age > timedelta(
            days=stale_after_days
        ):
            status = "STALE"
            current_value = winning_observation.value
            confidence = (
                TRUST_RANKS[winning_tier] / max(TRUST_RANKS.values())
            )
            valid_from = (
                winning_observation.effective_from
                or winning_observation.observed_at
            )
            valid_to = winning_observation.effective_to
            resolution_reason = (
                f"Latest winning observation is {winning_age.days} day(s) old, "
                f"exceeding stale_after_days={stale_after_days}."
            )
            evidence = [
                (
                    observation.observation_id,
                    "SUPPORT"
                    if canonical_json(observation.value) == winning_value_key
                    else "CONFLICT",
                )
                for observation in active
            ]
        else:
            status = "RESOLVED"
            current_value = winning_observation.value
            confidence = (
                TRUST_RANKS[winning_tier] / max(TRUST_RANKS.values())
            )
            valid_from = (
                winning_observation.effective_from
                or winning_observation.observed_at
            )
            valid_to = winning_observation.effective_to
            resolution_reason = (
                f"Selected {winning_observation.observation_id} from "
                f"{winning_tier} evidence using trust tier first, then "
                "observed_at, then observation_id."
            )
            evidence = [
                (
                    observation.observation_id,
                    "SUPPORT"
                    if canonical_json(observation.value) == winning_value_key
                    else "CONFLICT",
                )
                for observation in active
            ]

    signature = _belief_signature(
        subject_type=subject_type,
        subject_id=subject_id,
        field=field,
        current_value=current_value,
        status=status,
        confidence=confidence,
        valid_from=valid_from,
        valid_to=valid_to,
        resolver_version=resolver_version,
        evidence=evidence,
    )
    belief = Belief(
        belief_id=_belief_id(signature),
        subject_type=subject_type,
        subject_id=subject_id,
        field=field,
        current_value=current_value,
        status=status,
        confidence=confidence,
        valid_from=valid_from,
        valid_to=valid_to,
        resolved_at=as_of_dt.replace(microsecond=0).isoformat(),
        resolver_version=resolver_version,
        resolution_reason=resolution_reason,
        created_at=utc_now(),
    )

    current = get_current_belief(
        conn,
        subject_type,
        subject_id,
        field,
    )
    if current is not None:
        current_signature = _belief_signature(
            subject_type=current.subject_type,
            subject_id=current.subject_id,
            field=current.field,
            current_value=current.current_value,
            status=current.status,
            confidence=current.confidence,
            valid_from=current.valid_from,
            valid_to=current.valid_to,
            resolver_version=current.resolver_version,
            evidence=list_belief_observations(conn, current.belief_id),
        )
        if current_signature == signature:
            return current

    _insert_belief_version(conn, belief, evidence)
    return belief
