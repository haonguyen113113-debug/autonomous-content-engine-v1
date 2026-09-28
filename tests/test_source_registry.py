import sqlite3
import pytest

from apps.asset_library.source_registry import (
    Source,
    count_sources,
    ensure_source_schema,
    get_source,
    upsert_source,
)


def test_source_upsert_is_idempotent():
    conn = sqlite3.connect(":memory:")
    ensure_source_schema(conn)

    source = Source(
        source_id="src:uefa",
        provider="UEFA",
        source_type="official_competition",
        scope="football/champions-league",
        locator="https://example.test/uefa",
        default_trust_tier="primary",
    )

    upsert_source(conn, source)
    upsert_source(conn, source)

    assert count_sources(conn) == 1
    assert get_source(conn, "src:uefa").provider == "UEFA"


def test_source_locator_conflict_is_blocked():
    conn = sqlite3.connect(":memory:")
    ensure_source_schema(conn)

    upsert_source(
        conn,
        Source(
            source_id="src:a",
            provider="Example",
            source_type="official_competition",
            scope="football/a",
            locator="https://example.test/source",
            default_trust_tier="primary",
        ),
    )

    with pytest.raises(ValueError, match="Source locator conflict"):
        upsert_source(
            conn,
            Source(
                source_id="src:b",
                provider="Example",
                source_type="official_competition",
                scope="football/b",
                locator="https://example.test/source",
                default_trust_tier="primary",
            ),
        )
