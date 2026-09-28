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
    current_revision_id: str | None = None


@dataclass(frozen=True)
class SourceRevision:
    revision_id: str
    source_id: str
    revision_number: int
    provider: str
    source_type: str
    scope: str
    locator: str
    default_trust_tier: str
    active: bool
    valid_from: str
    valid_to: str | None
    created_at: str


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }


def _create_revision(
    conn: sqlite3.Connection,
    source: Source,
    *,
    revision_number: int,
    valid_from: str,
    revision_id: str | None = None,
) -> SourceRevision:
    revision = SourceRevision(
        revision_id=revision_id or f"source-revision:{source.source_id}:{revision_number}",
        source_id=source.source_id,
        revision_number=revision_number,
        provider=source.provider,
        source_type=source.source_type,
        scope=source.scope,
        locator=source.locator,
        default_trust_tier=source.default_trust_tier,
        active=source.active,
        valid_from=valid_from,
        valid_to=None,
        created_at=source.created_at or valid_from,
    )
    conn.execute(
        """
        INSERT INTO source_revisions (
            revision_id, source_id, revision_number,
            provider, source_type, scope, locator,
            default_trust_tier, active,
            valid_from, valid_to, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            revision.revision_id,
            revision.source_id,
            revision.revision_number,
            revision.provider,
            revision.source_type,
            revision.scope,
            revision.locator,
            revision.default_trust_tier,
            1 if revision.active else 0,
            revision.valid_from,
            revision.valid_to,
            revision.created_at,
        ),
    )
    return revision


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
            current_revision_id TEXT,
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

    columns = _table_columns(conn, "sources")
    if "current_revision_id" not in columns:
        conn.execute(
            "ALTER TABLE sources ADD COLUMN current_revision_id TEXT"
        )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS source_revisions (
            revision_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            revision_number INTEGER NOT NULL,
            provider TEXT NOT NULL,
            source_type TEXT NOT NULL,
            scope TEXT NOT NULL,
            locator TEXT NOT NULL,
            default_trust_tier TEXT NOT NULL,
            active INTEGER NOT NULL,
            valid_from TEXT NOT NULL,
            valid_to TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(source_id, revision_number),
            UNIQUE(provider, locator, revision_number),
            CHECK(default_trust_tier IN (
                'primary',
                'secondary',
                'discovery_only'
            ))
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_source_revisions_source
        ON source_revisions(source_id, revision_number)
        """
    )

    # Backfill a deterministic migration snapshot for pre-revision sources.
    rows = conn.execute(
        """
        SELECT source_id, provider, source_type, scope, locator,
               default_trust_tier, active, created_at, updated_at,
               current_revision_id
        FROM sources
        ORDER BY source_id
        """
    ).fetchall()
    for row in rows:
        if row[9]:
            continue

        existing = conn.execute(
            """
            SELECT revision_id
            FROM source_revisions
            WHERE source_id = ?
            ORDER BY revision_number DESC
            LIMIT 1
            """,
            (row[0],),
        ).fetchone()

        if existing is None:
            source = Source(
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
            revision = _create_revision(
                conn,
                source,
                revision_number=1,
                valid_from=row[7] or row[8] or utc_now(),
                revision_id=f"source-revision:{row[0]}:migration-1",
            )
            current_revision_id = revision.revision_id
        else:
            current_revision_id = existing[0]

        conn.execute(
            """
            UPDATE sources
            SET current_revision_id = ?
            WHERE source_id = ?
            """,
            (current_revision_id, row[0]),
        )

    conn.commit()


def _validate_source(source: Source) -> None:
    if source.source_type not in SOURCE_TYPES:
        raise ValueError(f"unsupported source_type: {source.source_type}")
    if source.default_trust_tier not in TRUST_TIERS:
        raise ValueError(
            f"unsupported default_trust_tier: {source.default_trust_tier}"
        )
    if not source.source_id.strip():
        raise ValueError("source_id is required")
    if not source.provider.strip():
        raise ValueError("provider is required")
    if not source.locator.strip():
        raise ValueError("locator is required")


def upsert_source(conn: sqlite3.Connection, source: Source) -> None:
    _validate_source(source)
    ensure_source_schema(conn)

    now = source.updated_at or utc_now()
    created = source.created_at or now

    locator_owner = conn.execute(
        "SELECT source_id FROM sources WHERE provider = ? AND locator = ?",
        (source.provider, source.locator),
    ).fetchone()
    if locator_owner is not None and locator_owner[0] != source.source_id:
        raise ValueError(
            f"Source locator conflict: {source.provider}:{source.locator} "
            f"already belongs to {locator_owner[0]}"
        )

    existing = conn.execute(
        """
        SELECT source_id, provider, source_type, scope, locator,
               default_trust_tier, active, created_at, updated_at,
               current_revision_id
        FROM sources
        WHERE source_id = ?
        """,
        (source.source_id,),
    ).fetchone()

    if existing is None:
        conn.execute(
            """
            INSERT INTO sources (
                source_id, provider, source_type, scope,
                locator, default_trust_tier, active,
                created_at, updated_at, current_revision_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
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
        revision = _create_revision(
            conn,
            source,
            revision_number=1,
            valid_from=now,
        )
        conn.execute(
            """
            UPDATE sources
            SET current_revision_id = ?
            WHERE source_id = ?
            """,
            (revision.revision_id, source.source_id),
        )
        conn.commit()
        return

    unchanged = (
        existing[1] == source.provider
        and existing[2] == source.source_type
        and existing[3] == source.scope
        and existing[4] == source.locator
        and existing[5] == source.default_trust_tier
        and bool(existing[6]) == source.active
    )
    if unchanged:
        return

    current_revision = get_current_source_revision(
        conn,
        source.source_id,
    )
    next_revision_number = (
        1 if current_revision is None else current_revision.revision_number + 1
    )

    conn.execute(
        """
        UPDATE source_revisions
        SET valid_to = ?
        WHERE source_id = ?
          AND revision_number = ?
          AND valid_to IS NULL
        """,
        (now, source.source_id, next_revision_number - 1),
    )

    conn.execute(
        """
        UPDATE sources
        SET provider = ?,
            source_type = ?,
            scope = ?,
            locator = ?,
            default_trust_tier = ?,
            active = ?,
            updated_at = ?
        WHERE source_id = ?
        """,
        (
            source.provider,
            source.source_type,
            source.scope,
            source.locator,
            source.default_trust_tier,
            1 if source.active else 0,
            now,
            source.source_id,
        ),
    )

    revision = _create_revision(
        conn,
        source,
        revision_number=next_revision_number,
        valid_from=now,
    )
    conn.execute(
        """
        UPDATE sources
        SET current_revision_id = ?
        WHERE source_id = ?
        """,
        (revision.revision_id, source.source_id),
    )
    conn.commit()


def _read_source(row: sqlite3.Row | tuple) -> Source:
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
        current_revision_id=row[9],
    )


def get_source(conn: sqlite3.Connection, source_id: str) -> Source | None:
    ensure_source_schema(conn)
    row = conn.execute(
        """
        SELECT source_id, provider, source_type, scope, locator,
               default_trust_tier, active, created_at, updated_at,
               current_revision_id
        FROM sources
        WHERE source_id = ?
        """,
        (source_id,),
    ).fetchone()
    return None if row is None else _read_source(row)


def get_source_revision(
    conn: sqlite3.Connection,
    revision_id: str,
) -> SourceRevision | None:
    ensure_source_schema(conn)
    row = conn.execute(
        """
        SELECT revision_id, source_id, revision_number,
               provider, source_type, scope, locator,
               default_trust_tier, active,
               valid_from, valid_to, created_at
        FROM source_revisions
        WHERE revision_id = ?
        """,
        (revision_id,),
    ).fetchone()
    if row is None:
        return None
    return SourceRevision(
        revision_id=row[0],
        source_id=row[1],
        revision_number=int(row[2]),
        provider=row[3],
        source_type=row[4],
        scope=row[5],
        locator=row[6],
        default_trust_tier=row[7],
        active=bool(row[8]),
        valid_from=row[9],
        valid_to=row[10],
        created_at=row[11],
    )


def get_current_source_revision(
    conn: sqlite3.Connection,
    source_id: str,
) -> SourceRevision | None:
    source = get_source(conn, source_id)
    if source is None or source.current_revision_id is None:
        return None
    return get_source_revision(conn, source.current_revision_id)


def count_sources(conn: sqlite3.Connection) -> int:
    ensure_source_schema(conn)
    row = conn.execute("SELECT COUNT(*) FROM sources").fetchone()
    return int(row[0])


def count_source_revisions(conn: sqlite3.Connection) -> int:
    ensure_source_schema(conn)
    row = conn.execute("SELECT COUNT(*) FROM source_revisions").fetchone()
    return int(row[0])
