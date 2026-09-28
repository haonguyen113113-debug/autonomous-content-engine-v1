from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

SCHEMA_VERSION = 3


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_migration_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
    ).fetchone()
    return int(row[0])


def _record_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_migrations(version, applied_at)
        VALUES (?, ?)
        """,
        (version, utc_now()),
    )
    conn.commit()


def _migration_1(conn: sqlite3.Connection) -> None:
    from .registry import ensure_asset_schema
    from .catalog import init_entity_schema
    from .source_registry import ensure_source_schema
    from .observation import ensure_observation_schema
    from .belief import ensure_belief_schema
    from .change_detection import ensure_change_detection_schema
    from .resolution_orchestrator import ensure_resolution_schema

    ensure_asset_schema(conn)
    init_entity_schema(conn)
    ensure_source_schema(conn)
    ensure_observation_schema(conn)
    ensure_belief_schema(conn)
    ensure_change_detection_schema(conn)
    ensure_resolution_schema(conn)


def _migration_2(conn: sqlite3.Connection) -> None:
    from .registry import ensure_asset_schema
    from .source_registry import ensure_source_schema
    from .observation import ensure_observation_schema

    ensure_source_schema(conn)
    ensure_observation_schema(conn)
    ensure_asset_schema(conn)


def _migration_3(conn: sqlite3.Connection) -> None:
    from .resolution_orchestrator import ensure_resolution_schema

    ensure_resolution_schema(conn)


def initialize_database(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    _ensure_migration_table(conn)
    current = _current_version(conn)

    migrations = {
        1: _migration_1,
        2: _migration_2,
        3: _migration_3,
    }

    for version in range(current + 1, SCHEMA_VERSION + 1):
        migrations[version](conn)
        _record_version(conn, version)

    _migration_3(conn)


def get_schema_version(conn: sqlite3.Connection) -> int:
    _ensure_migration_table(conn)
    return _current_version(conn)
