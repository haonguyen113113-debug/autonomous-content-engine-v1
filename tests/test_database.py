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

    assert get_schema_version(conn) == SCHEMA_VERSION == 2

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

    # Domain-pack tables are intentionally not bootstrapped by core DB init.
    assert "competitions" not in tables
