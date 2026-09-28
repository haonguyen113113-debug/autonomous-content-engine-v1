from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3

SOURCE_TYPES = {
    "official_competition",
    "official_federation",
    "official_club",
    "structured_secondary",
    "discovery_only",
}
TRUST_TIERS = {"primary", "secondary", "discovery_only"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class Source:
    source_id: str
    provider: str
    source_type: str
    scope: str
    locator: str
    default_trust_tier: str
    active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


def ensure_source_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sources (
            source_id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            source_type TEXT NOT NULL,
            scope TEXT NOT NULL,
            locator TEXT NOT NULL,
            default_trust_tier TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(provider, locator),
            CHECK(source_type IN (
                'official_competition',
                'official_federation',
                'official_club',
                'structured_secondary',
                'discovery_only'
            )),
            CHECK(default_trust_tier IN (
                'primary',
                'secondary',
                'discovery_only'
            ))
        )
        """
    )
    conn.commit()


def upsert_source(conn: sqlite3.Connection, source: Source) -> None:
    if source.source_type not in SOURCE_TYPES:
        raise ValueError(f"unsupported source_type: {source.source_type}")
    if source.default_trust_tier not in TRUST_TIERS:
        raise ValueError(
            f"unsupported default_trust_tier: {source.default_trust_tier}"
        )

    now = source.updated_at or utc_now()
    created = source.created_at or now

    existing = conn.execute(
        "SELECT source_id FROM sources WHERE provider = ? AND locator = ?",
        (source.provider, source.locator),
    ).fetchone()

    if existing and existing[0] != source.source_id:
        raise ValueError(
            f"Source locator conflict: {source.provider}:{source.locator} "
            f"already belongs to {existing[0]}"
        )

    conn.execute(
        """
        INSERT INTO sources (
            source_id, provider, source_type, scope,
            locator, default_trust_tier, active,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            provider = excluded.provider,
            source_type = excluded.source_type,
            scope = excluded.scope,
            locator = excluded.locator,
            default_trust_tier = excluded.default_trust_tier,
            active = excluded.active,
            updated_at = excluded.updated_at
        """,
        (
            source.source_id,
            source.provider,
            source.source_type,
            source.scope,
            source.locator,
            source.default_trust_tier,
            1 if source.active else 0,
            created,
            now,
        ),
    )
    conn.commit()


def get_source(conn: sqlite3.Connection, source_id: str) -> Source | None:
    row = conn.execute(
        """
        SELECT source_id, provider, source_type, scope, locator,
               default_trust_tier, active, created_at, updated_at
        FROM sources
        WHERE source_id = ?
        """,
        (source_id,),
    ).fetchone()

    if row is None:
        return None

    return Source(
        source_id=row[0],
        provider=row[1],
        source_type=row[2],
        scope=row[3],
        locator=row[4],
        default_trust_tier=row[5],
        active=bool(row[6]),
        created_at=row[7],
        updated_at=row[8],
    )


def count_sources(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM sources").fetchone()
    return int(row[0])
