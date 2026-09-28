import sqlite3

from apps.asset_library.belief import (
    get_current_belief,
    list_belief_history,
    list_belief_observations,
    resolve_belief,
)
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


def setup_db():
    conn = sqlite3.connect(":memory:")
    ensure_source_schema(conn)
    ensure_observation_schema(conn)
    return conn


def add_source(conn, source_id, provider, trust_tier, active=True):
    upsert_source(
        conn,
        Source(
            source_id=source_id,
            provider=provider,
            source_type="official_club",
            scope="football/test",
            locator=f"https://example.test/{source_id}",
            default_trust_tier=trust_tier,
            active=active,
        ),
    )


def add_observation(
    conn,
    observation_id,
    source_id,
    value,
    observed_at,
    *,
    effective_from=None,
    effective_to=None,
):
    upsert_observation(
        conn,
        Observation(
            observation_id=observation_id,
            source_id=source_id,
            subject_type="player",
            subject_id="player:1",
            field="club",
            value={"entity_id": value},
            observed_at=observed_at,
            locator=f"https://example.test/{observation_id}",
            effective_from=effective_from,
            effective_to=effective_to,
        ),
    )


def test_resolver_prefers_trust_then_recency_and_preserves_evidence():
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")
    add_source(conn, "src:secondary", "Secondary", "secondary")

    add_observation(
        conn,
        "obs:arsenal",
        "src:primary",
        "club:arsenal",
        "2026-09-28T09:00:00+00:00",
    )
    add_observation(
        conn,
        "obs:liverpool",
        "src:secondary",
        "club:liverpool",
        "2026-09-29T09:00:00+00:00",
    )

    belief = resolve_belief(
        conn,
        "player",
        "player:1",
        "club",
        as_of="2026-09-29T10:00:00+00:00",
    )

    assert belief.status == "RESOLVED"
    assert belief.current_value == {"entity_id": "club:arsenal"}
    assert belief.confidence == 1.0
    assert list_belief_observations(conn, belief.belief_id) == [
        ("obs:arsenal", "SUPPORT"),
        ("obs:liverpool", "CONFLICT"),
    ]


def test_resolver_marks_equal_top_evidence_as_conflicted():
    conn = setup_db()
    add_source(conn, "src:a", "Official A", "primary")
    add_source(conn, "src:b", "Official B", "primary")

    timestamp = "2026-09-29T09:00:00+00:00"
    add_observation(conn, "obs:a", "src:a", "club:arsenal", timestamp)
    add_observation(conn, "obs:b", "src:b", "club:liverpool", timestamp)

    belief = resolve_belief(
        conn,
        "player",
        "player:1",
        "club",
        as_of="2026-09-29T10:00:00+00:00",
    )

    assert belief.status == "CONFLICTED"
    assert belief.current_value is None
    assert belief.confidence == 0.0
    assert list_belief_observations(conn, belief.belief_id) == [
        ("obs:a", "COMPETING"),
        ("obs:b", "COMPETING"),
    ]


def test_resolver_is_idempotent_for_unchanged_resolution():
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")
    add_observation(
        conn,
        "obs:arsenal",
        "src:primary",
        "club:arsenal",
        "2026-09-28T09:00:00+00:00",
    )

    first = resolve_belief(
        conn,
        "player",
        "player:1",
        "club",
        as_of="2026-09-29T10:00:00+00:00",
    )
    second = resolve_belief(
        conn,
        "player",
        "player:1",
        "club",
        as_of="2026-09-29T10:00:00+00:00",
    )

    assert second.belief_id == first.belief_id
    assert len(list_belief_history(conn, "player", "player:1", "club")) == 1


def test_resolver_creates_version_when_belief_changes():
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")

    add_observation(
        conn,
        "obs:arsenal",
        "src:primary",
        "club:arsenal",
        "2026-09-28T09:00:00+00:00",
    )
    first = resolve_belief(
        conn,
        "player",
        "player:1",
        "club",
        as_of="2026-09-28T10:00:00+00:00",
    )

    add_observation(
        conn,
        "obs:liverpool",
        "src:primary",
        "club:liverpool",
        "2026-09-29T09:00:00+00:00",
    )
    second = resolve_belief(
        conn,
        "player",
        "player:1",
        "club",
        as_of="2026-09-29T10:00:00+00:00",
    )

    assert first.belief_id != second.belief_id
    assert second.current_value == {"entity_id": "club:liverpool"}
    history = list_belief_history(conn, "player", "player:1", "club")
    assert len(history) == 2
    assert history[0].is_current is False
    assert history[1].is_current is True


def test_resolver_marks_old_evidence_stale_when_requested():
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")
    add_observation(
        conn,
        "obs:arsenal",
        "src:primary",
        "club:arsenal",
        "2026-09-01T09:00:00+00:00",
    )

    belief = resolve_belief(
        conn,
        "player",
        "player:1",
        "club",
        as_of="2026-09-10T09:00:00+00:00",
        stale_after_days=7,
    )

    assert belief.status == "STALE"
    assert belief.current_value == {"entity_id": "club:arsenal"}
    assert belief.confidence == 1.0
