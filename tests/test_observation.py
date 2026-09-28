import sqlite3

import pytest

from apps.asset_library.observation import (
    Observation,
    count_observations,
    ensure_observation_schema,
    list_observations,
    upsert_observation,
)
from apps.asset_library.source_registry import (
    Source,
    ensure_source_schema,
    upsert_source,
)


def make_observation(**overrides):
    payload = dict(
        observation_id="obs:player-1:club",
        source_id="src:official",
        subject_type="player",
        subject_id="player:1",
        field="club",
        value={"entity_id": "club:arsenal"},
        observed_at="2026-09-28T10:00:00+00:00",
        locator="https://example.test/player-1",
    )
    payload.update(overrides)
    return Observation(**payload)


def setup_db():
    conn = sqlite3.connect(":memory:")
    ensure_source_schema(conn)
    ensure_observation_schema(conn)
    upsert_source(
        conn,
        Source(
            source_id="src:official",
            provider="Official",
            source_type="official_club",
            scope="football/test",
            locator="https://example.test/source",
            default_trust_tier="primary",
        ),
    )
    return conn


def test_observation_is_idempotent_and_preserves_history():
    conn = setup_db()

    first = make_observation()
    later = make_observation(
        observation_id="obs:player-1:club:later",
        observed_at="2026-09-29T10:00:00+00:00",
        value={"entity_id": "club:liverpool"},
    )

    upsert_observation(conn, first)
    upsert_observation(conn, first)
    upsert_observation(conn, later)

    assert count_observations(conn) == 2
    history = list_observations(conn, "player:1")
    assert history[0].value["entity_id"] == "club:arsenal"
    assert history[1].value["entity_id"] == "club:liverpool"
    assert history[0].source_revision_id is not None


def test_observation_rejects_mutation_under_same_id():
    conn = setup_db()

    upsert_observation(conn, make_observation())

    with pytest.raises(ValueError, match="Observation is immutable"):
        upsert_observation(
            conn,
            make_observation(value={"entity_id": "club:liverpool"}),
        )


def test_observation_rejects_invalid_content_hash():
    conn = setup_db()

    with pytest.raises(
        ValueError,
        match="content_hash does not match",
    ):
        upsert_observation(
            conn,
            make_observation(content_hash="not-a-real-hash"),
        )


def test_observation_requires_source_and_locator():
    conn = setup_db()

    with pytest.raises(ValueError, match="source_id is required"):
        upsert_observation(conn, make_observation(source_id=""))

    with pytest.raises(ValueError, match="locator is required"):
        upsert_observation(conn, make_observation(locator=""))
