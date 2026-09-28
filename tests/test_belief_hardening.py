import sqlite3

from apps.asset_library.belief import resolve_belief
from apps.asset_library.observation import (
    Observation,
    ensure_observation_schema,
    upsert_observation,
)
from apps.asset_library.source_registry import (
    Source,
    ensure_source_schema,
    upsert_source,
)


def test_belief_replay_uses_observation_bound_source_revision():
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

    upsert_observation(
        conn,
        Observation(
            observation_id="obs:old",
            source_id="src:official",
            subject_type="player",
            subject_id="player:1",
            field="club",
            value={"entity_id": "club:arsenal"},
            observed_at="2026-09-28T09:00:00+00:00",
            locator="https://example.test/old",
        ),
    )

    upsert_source(
        conn,
        Source(
            source_id="src:official",
            provider="Official",
            source_type="official_club",
            scope="football/test",
            locator="https://example.test/source",
            default_trust_tier="secondary",
        ),
    )

    upsert_observation(
        conn,
        Observation(
            observation_id="obs:new",
            source_id="src:official",
            subject_type="player",
            subject_id="player:1",
            field="club",
            value={"entity_id": "club:liverpool"},
            observed_at="2026-09-29T09:00:00+00:00",
            locator="https://example.test/new",
        ),
    )

    belief = resolve_belief(
        conn,
        "player",
        "player:1",
        "club",
        as_of="2026-09-29T10:00:00+00:00",
    )

    assert belief is not None
    assert belief.current_value == {"entity_id": "club:arsenal"}
    assert belief.confidence == 1.0
