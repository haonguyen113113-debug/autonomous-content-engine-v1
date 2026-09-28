from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Any

from .source_registry import (
    get_current_source_revision,
    get_source_revision,
    ensure_source_schema,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def content_hash(value: Any) -> str:
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


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
    source_revision_id: str | None = None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }


def ensure_observation_schema(conn: sqlite3.Connection) -> None:
    ensure_source_schema(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS observations (
            observation_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            source_revision_id TEXT,
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
            UNIQUE(
                source_id,
                subject_type,
                subject_id,
                field,
                observed_at,
                content_hash
            )
        )
        """
    )

    if "source_revision_id" not in _table_columns(
        conn,
        "observations",
    ):
        conn.execute(
            "ALTER TABLE observations ADD COLUMN source_revision_id TEXT"
        )

    # Backfill historical observations with the source snapshot available
    # during the hardening migration. Earlier source-history detail may not
    # be reconstructable if it never existed before this migration.
    rows = conn.execute(
        """
        SELECT observation_id, source_id
        FROM observations
        WHERE source_revision_id IS NULL
        ORDER BY observation_id
        """
    ).fetchall()
    for row in rows:
        revision = get_current_source_revision(conn, row[1])
        if revision is not None:
            conn.execute(
                """
                UPDATE observations
                SET source_revision_id = ?
                WHERE observation_id = ?
                """,
                (revision.revision_id, row[0]),
            )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_observations_subject_field
        ON observations(subject_type, subject_id, field, observed_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_observations_source_revision
        ON observations(source_revision_id)
        """
    )
    conn.commit()


def _existing_observation(
    conn: sqlite3.Connection,
    observation_id: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT observation_id, source_id, source_revision_id,
               subject_type, subject_id, field,
               value_json, observed_at, effective_from,
               effective_to, locator, content_hash, recorded_at
        FROM observations
        WHERE observation_id = ?
        """,
        (observation_id,),
    ).fetchone()


def upsert_observation(
    conn: sqlite3.Connection,
    observation: Observation,
) -> None:
    ensure_observation_schema(conn)

    if not observation.source_id.strip():
        raise ValueError("source_id is required")
    if not observation.locator.strip():
        raise ValueError("locator is required")

    computed_hash = content_hash(observation.value)
    if (
        observation.content_hash is not None
        and observation.content_hash != computed_hash
    ):
        raise ValueError("content_hash does not match observation value")

    current_revision = get_current_source_revision(
        conn,
        observation.source_id,
    )
    source_revision_id = (
        observation.source_revision_id
        or (
            current_revision.revision_id
            if current_revision is not None
            else None
        )
    )
    if source_revision_id is None:
        raise ValueError(
            f"source has no registry revision: {observation.source_id}"
        )

    revision = get_source_revision(conn, source_revision_id)
    if revision is None or revision.source_id != observation.source_id:
        raise ValueError(
            "source_revision_id does not belong to observation.source_id"
        )

    recorded = observation.recorded_at or utc_now()
    existing = _existing_observation(
        conn,
        observation.observation_id,
    )

    value_json = canonical_json(observation.value)

    if existing is not None:
        immutable_match = (
            existing[1] == observation.source_id
            and existing[2] == source_revision_id
            and existing[3] == observation.subject_type
            and existing[4] == observation.subject_id
            and existing[5] == observation.field
            and existing[6] == value_json
            and existing[7] == observation.observed_at
            and existing[8] == observation.effective_from
            and existing[9] == observation.effective_to
            and existing[10] == observation.locator
            and existing[11] == computed_hash
        )

        recorded_match = (
            observation.recorded_at is None
            or existing[12] == observation.recorded_at
        )

        if immutable_match and recorded_match:
            return

        raise ValueError(
            "Observation is immutable: "
            f"observation_id={observation.observation_id} already exists "
            "with different evidence."
        )

    conn.execute(
        """
        INSERT INTO observations (
            observation_id, source_id, source_revision_id,
            subject_type, subject_id, field,
            value_json, observed_at, effective_from, effective_to,
            locator, content_hash, recorded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            observation.observation_id,
            observation.source_id,
            source_revision_id,
            observation.subject_type,
            observation.subject_id,
            observation.field,
            value_json,
            observation.observed_at,
            observation.effective_from,
            observation.effective_to,
            observation.locator,
            computed_hash,
            recorded,
        ),
    )
    conn.commit()


def count_observations(conn: sqlite3.Connection) -> int:
    ensure_observation_schema(conn)
    row = conn.execute("SELECT COUNT(*) FROM observations").fetchone()
    return int(row[0])


def list_observations(
    conn: sqlite3.Connection,
    subject_id: str,
) -> list[Observation]:
    ensure_observation_schema(conn)
    rows = conn.execute(
        """
        SELECT observation_id, source_id, source_revision_id,
               subject_type, subject_id, field,
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
            source_revision_id=row[2],
            subject_type=row[3],
            subject_id=row[4],
            field=row[5],
            value=json.loads(row[6]),
            observed_at=row[7],
            effective_from=row[8],
            effective_to=row[9],
            locator=row[10],
            content_hash=row[11],
            recorded_at=row[12],
        )
        for row in rows
    ]
