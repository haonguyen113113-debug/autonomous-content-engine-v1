import sqlite3

from apps.asset_library.database import (
    SCHEMA_VERSION,
    get_schema_version,
    initialize_database,
)
from apps.asset_library.registry import ensure_asset_schema


def test_database_bootstrap_is_versioned_and_idempotent():
    conn = sqlite3.connect(":memory:")
    ensure_asset_schema(conn)

    initialize_database(conn)
    initialize_database(conn)

    assert get_schema_version(conn) == SCHEMA_VERSION == 3

    tables = {
        row[0]
        for row in conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
    }

    assert "schema_migrations" in tables
    assert "source_revisions" in tables
    assert "observations" in tables
    assert "beliefs" in tables
    assert "change_events" in tables
    assert "change_event_resolutions" in tables
    assert "entities" in tables
    assert "competitions" not in tables


def test_database_applies_orchestrator_reliability_migration():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
    conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (2, '2026-09-28T00:00:00+00:00')")
    conn.execute("""
        CREATE TABLE change_event_resolutions (
            change_event_id TEXT PRIMARY KEY, status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0, first_attempt_at TEXT,
            last_attempt_at TEXT, resolved_at TEXT, result_belief_id TEXT,
            error_type TEXT, error_message TEXT, orchestrator_version TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)

    initialize_database(conn)

    assert get_schema_version(conn) == 3
    columns = {row[1] for row in conn.execute("PRAGMA table_info(change_event_resolutions)").fetchall()}
    assert {"lease_owner", "lease_until", "next_attempt_at", "max_attempts"} <= columns
