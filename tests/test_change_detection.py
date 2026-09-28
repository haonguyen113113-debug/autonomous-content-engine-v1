import sqlite3

from apps.asset_library.belief import resolve_belief
from apps.asset_library.change_detection import (
    count_change_events,
    detect_changes,
    list_change_events,
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
    recorded_at=None,
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
            recorded_at=recorded_at,
        ),
    )


def test_initial_observation_creates_reassessment_event_and_is_idempotent():
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")

    add_observation(
        conn,
        "obs:1",
        "src:primary",
        "club:arsenal",
        "2026-09-01T09:00:00+00:00",
        recorded_at="2026-09-01T09:01:00+00:00",
    )

    first = detect_changes(conn, "player", "player:1", "club")
    second = detect_changes(conn, "player", "player:1", "club")

    assert len(first) == 1
    assert first[0].reason_codes == ("INITIAL_OBSERVATION",)
    assert first[0].event_type == "REASSESSMENT_REQUIRED"
    assert second == []
    assert count_change_events(conn) == 1


def test_same_value_from_same_trust_does_not_trigger_new_event():
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")

    add_observation(
        conn,
        "obs:1",
        "src:primary",
        "club:arsenal",
        "2026-09-01T09:00:00+00:00",
        recorded_at="2026-09-01T09:01:00+00:00",
    )
    detect_changes(conn, "player", "player:1", "club")

    resolve_belief(
        conn,
        "player",
        "player:1",
        "club",
        as_of="2026-09-02T09:00:00+00:00",
    )

    add_observation(
        conn,
        "obs:2",
        "src:primary",
        "club:arsenal",
        "2026-09-02T09:00:00+00:00",
        recorded_at="2026-09-02T09:01:00+00:00",
    )

    assert detect_changes(conn, "player", "player:1", "club") == []
    assert count_change_events(conn) == 1


def test_value_change_creates_value_and_belief_mismatch_reasons():
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")

    add_observation(
        conn,
        "obs:1",
        "src:primary",
        "club:arsenal",
        "2026-09-01T09:00:00+00:00",
        recorded_at="2026-09-01T09:01:00+00:00",
    )
    detect_changes(conn, "player", "player:1", "club")
    resolve_belief(
        conn,
        "player",
        "player:1",
        "club",
        as_of="2026-09-02T09:00:00+00:00",
    )

    add_observation(
        conn,
        "obs:2",
        "src:primary",
        "club:liverpool",
        "2026-09-03T09:00:00+00:00",
        recorded_at="2026-09-03T09:01:00+00:00",
    )

    events = detect_changes(conn, "player", "player:1", "club")

    assert len(events) == 1
    assert events[0].reason_codes == (
        "BELIEF_MISMATCH",
        "VALUE_CHANGE",
    )
    assert events[0].previous_observation_id == "obs:1"


def test_higher_trust_same_value_creates_evidence_update():
    conn = setup_db()
    add_source(conn, "src:secondary", "Secondary", "secondary")
    add_source(conn, "src:primary", "Official", "primary")

    add_observation(
        conn,
        "obs:secondary",
        "src:secondary",
        "club:arsenal",
        "2026-09-01T09:00:00+00:00",
        recorded_at="2026-09-01T09:01:00+00:00",
    )
    detect_changes(conn, "player", "player:1", "club")
    resolve_belief(
        conn,
        "player",
        "player:1",
        "club",
        as_of="2026-09-02T09:00:00+00:00",
    )

    add_observation(
        conn,
        "obs:primary",
        "src:primary",
        "club:arsenal",
        "2026-09-03T09:00:00+00:00",
        recorded_at="2026-09-03T09:01:00+00:00",
    )

    events = detect_changes(conn, "player", "player:1", "club")

    assert len(events) == 1
    assert events[0].reason_codes == ("EVIDENCE_UPDATE",)


def test_stale_belief_triggers_reassessment_even_when_value_is_same():
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")

    add_observation(
        conn,
        "obs:1",
        "src:primary",
        "club:arsenal",
        "2026-09-01T09:00:00+00:00",
        recorded_at="2026-09-01T09:01:00+00:00",
    )
    detect_changes(conn, "player", "player:1", "club")

    resolve_belief(
        conn,
        "player",
        "player:1",
        "club",
        as_of="2026-09-10T09:00:00+00:00",
        stale_after_days=7,
    )

    add_observation(
        conn,
        "obs:2",
        "src:primary",
        "club:arsenal",
        "2026-09-10T09:00:00+00:00",
        recorded_at="2026-09-10T09:01:00+00:00",
    )

    events = detect_changes(conn, "player", "player:1", "club")

    assert len(events) == 1
    assert events[0].reason_codes == (
        "BELIEF_STATUS_REQUIRES_REASSESSMENT",
    )


def test_late_recorded_observation_is_detected_by_recorded_at_cursor():
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")

    add_observation(
        conn,
        "obs:1",
        "src:primary",
        "club:arsenal",
        "2026-09-03T09:00:00+00:00",
        recorded_at="2026-09-03T09:01:00+00:00",
    )
    detect_changes(conn, "player", "player:1", "club")
    resolve_belief(
        conn,
        "player",
        "player:1",
        "club",
        as_of="2026-09-03T09:02:00+00:00",
    )

    add_observation(
        conn,
        "obs:late",
        "src:primary",
        "club:liverpool",
        "2026-09-02T09:00:00+00:00",
        recorded_at="2026-09-04T09:01:00+00:00",
    )

    events = detect_changes(conn, "player", "player:1", "club")

    assert len(events) == 1
    assert events[0].observation_id == "obs:late"
    assert events[0].reason_codes == (
        "BELIEF_MISMATCH",
        "VALUE_CHANGE",
    )


def test_multiple_new_observations_are_processed_once_in_recorded_order():
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")

    add_observation(
        conn,
        "obs:1",
        "src:primary",
        "club:arsenal",
        "2026-09-01T09:00:00+00:00",
        recorded_at="2026-09-01T09:01:00+00:00",
    )
    detect_changes(conn, "player", "player:1", "club")
    resolve_belief(
        conn,
        "player",
        "player:1",
        "club",
        as_of="2026-09-02T09:00:00+00:00",
    )

    add_observation(
        conn,
        "obs:2",
        "src:primary",
        "club:liverpool",
        "2026-09-03T09:00:00+00:00",
        recorded_at="2026-09-03T09:01:00+00:00",
    )
    add_observation(
        conn,
        "obs:3",
        "src:primary",
        "club:chelsea",
        "2026-09-04T09:00:00+00:00",
        recorded_at="2026-09-04T09:01:00+00:00",
    )

    events = detect_changes(conn, "player", "player:1", "club")
    assert [event.observation_id for event in events] == ["obs:2", "obs:3"]
    assert len(list_change_events(conn, "player", "player:1", "club")) == 3

    assert detect_changes(conn, "player", "player:1", "club") == []
