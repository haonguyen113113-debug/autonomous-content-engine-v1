from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Observation:
    observation_id: str
    source_id: str
    subject_type: str
    subject_id: str
    field: str
    value: Any
    observed_at: str
    locator: str
    effective_from: str | None = None
    effective_to: str | None = None
    recorded_at: str | None = None
    content_hash: str | None = None


def ensure_observation_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS observations (
            observation_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            subject_type TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            field TEXT NOT NULL,
            value_json TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            effective_from TEXT,
            effective_to TEXT,
            locator TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            UNIQUE(source_id, subject_type, subject_id, field, observed_at, content_hash)
        )
        """
    )
    conn.commit()


def upsert_observation(conn: sqlite3.Connection, observation: Observation) -> None:
    if not observation.source_id.strip():
        raise ValueError("source_id is required")
    if not observation.locator.strip():
        raise ValueError("locator is required")

    value_hash = observation.content_hash or content_hash(observation.value)
    recorded = observation.recorded_at or utc_now()

    conn.execute(
        """
        INSERT INTO observations (
            observation_id, source_id, subject_type, subject_id, field,
            value_json, observed_at, effective_from, effective_to,
            locator, content_hash, recorded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(observation_id) DO UPDATE SET
            source_id = excluded.source_id,
            subject_type = excluded.subject_type,
            subject_id = excluded.subject_id,
            field = excluded.field,
            value_json = excluded.value_json,
            observed_at = excluded.observed_at,
            effective_from = excluded.effective_from,
            effective_to = excluded.effective_to,
            locator = excluded.locator,
            content_hash = excluded.content_hash
        """,
        (
            observation.observation_id,
            observation.source_id,
            observation.subject_type,
            observation.subject_id,
            observation.field,
            canonical_json(observation.value),
            observation.observed_at,
            observation.effective_from,
            observation.effective_to,
            observation.locator,
            value_hash,
            recorded,
        ),
    )
    conn.commit()


def count_observations(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM observations").fetchone()
    return int(row[0])


def list_observations(conn: sqlite3.Connection, subject_id: str) -> list[Observation]:
    rows = conn.execute(
        """
        SELECT observation_id, source_id, subject_type, subject_id, field,
               value_json, observed_at, effective_from, effective_to,
               locator, content_hash, recorded_at
        FROM observations
        WHERE subject_id = ?
        ORDER BY observed_at ASC, observation_id ASC
        """,
        (subject_id,),
    ).fetchall()

    return [
        Observation(
            observation_id=row[0],
            source_id=row[1],
            subject_type=row[2],
            subject_id=row[3],
            field=row[4],
            value=json.loads(row[5]),
            observed_at=row[6],
            effective_from=row[7],
            effective_to=row[8],
            locator=row[9],
            content_hash=row[10],
            recorded_at=row[11],
        )
        for row in rows
    ]
