import sqlite3

import pytest

from apps.asset_library.source_registry import (
    Source,
    count_source_revisions,
    count_sources,
    ensure_source_schema,
    get_current_source_revision,
    get_source,
    get_source_revision,
    upsert_source,
)


def test_source_upsert_is_idempotent_and_creates_one_revision():
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
    assert count_source_revisions(conn) == 1
    current = get_current_source_revision(conn, "src:uefa")
    assert current is not None
    assert current.revision_number == 1
    assert get_source(conn, "src:uefa").current_revision_id == current.revision_id


def test_source_revision_preserves_previous_trust_state():
    conn = sqlite3.connect(":memory:")
    ensure_source_schema(conn)

    upsert_source(
        conn,
        Source(
            source_id="src:a",
            provider="Example",
            source_type="official_competition",
            scope="football/a",
            locator="https://example.test/source-a",
            default_trust_tier="primary",
        ),
    )
    first = get_current_source_revision(conn, "src:a")
    assert first is not None

    upsert_source(
        conn,
        Source(
            source_id="src:a",
            provider="Example",
            source_type="official_competition",
            scope="football/a",
            locator="https://example.test/source-a",
            default_trust_tier="secondary",
        ),
    )

    second = get_current_source_revision(conn, "src:a")
    assert second is not None
    assert second.revision_number == 2
    assert second.default_trust_tier == "secondary"

    preserved = get_source_revision(conn, first.revision_id)
    assert preserved.default_trust_tier == "primary"
    assert preserved.valid_to is not None


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
