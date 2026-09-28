import sqlite3

from apps.asset_library.belief import get_current_belief
from apps.asset_library.change_detection import (
    ChangeEvent,
    detect_changes,
)
from apps.asset_library.observation import (
    Observation,
    ensure_observation_schema,
    upsert_observation,
)
from apps.asset_library.resolution_orchestrator import (
    ensure_resolution_schema,
    get_resolution_status,
    process_pending_change_events,
    resolve_change_event,
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
    ensure_resolution_schema(conn)
    return conn


def add_source(conn, source_id, provider, trust_tier):
    upsert_source(
        conn,
        Source(
            source_id=source_id,
            provider=provider,
            source_type="official_club",
            scope="football/test",
            locator=f"https://example.test/{source_id}",
            default_trust_tier=trust_tier,
        ),
    )


def add_observation(
    conn,
    observation_id,
    source_id,
    value,
    observed_at,
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
        ),
    )


def make_event(conn, observation_id, source_id="src:primary"):
    add_observation(
        conn,
        observation_id,
        source_id,
        "club:arsenal",
        "2026-09-28T09:00:00+00:00",
    )
    events = detect_changes(conn, "player", "player:1", "club")
    assert len(events) == 1
    return events[0]


def test_processes_initial_change_event_into_current_belief():
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")

    event = make_event(conn, "obs:1")

    results = process_pending_change_events(
        conn,
        as_of="2026-09-28T10:00:00+00:00",
    )

    assert len(results) == 1
    assert results[0].status == "RESOLVED"
    assert results[0].belief_id is not None

    belief = get_current_belief(
        conn,
        "player",
        "player:1",
        "club",
    )
    assert belief is not None
    assert belief.current_value == {"entity_id": "club:arsenal"}

    resolution = get_resolution_status(
        conn,
        event.change_event_id,
    )
    assert resolution.status == "RESOLVED"
    assert resolution.attempts == 1
    assert resolution.result_belief_id == belief.belief_id


def test_resolved_event_is_idempotently_skipped():
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")

    event = make_event(conn, "obs:1")
    first = process_pending_change_events(
        conn,
        as_of="2026-09-28T10:00:00+00:00",
    )
    second = process_pending_change_events(
        conn,
        as_of="2026-09-28T11:00:00+00:00",
    )

    assert first[0].status == "RESOLVED"
    assert second == []

    direct = resolve_change_event(
        conn,
        event,
        as_of="2026-09-28T11:00:00+00:00",
    )
    assert direct.status == "SKIPPED"
    assert direct.attempts == 1


def test_new_value_event_re_resolves_belief():
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")

    make_event(conn, "obs:1")
    process_pending_change_events(
        conn,
        as_of="2026-09-28T10:00:00+00:00",
    )

    add_observation(
        conn,
        "obs:2",
        "src:primary",
        "club:liverpool",
        "2026-09-29T09:00:00+00:00",
    )
    events = detect_changes(conn, "player", "player:1", "club")
    assert len(events) == 1

    results = process_pending_change_events(
        conn,
        as_of="2026-09-29T10:00:00+00:00",
    )
    assert results[0].status == "RESOLVED"

    belief = get_current_belief(
        conn,
        "player",
        "player:1",
        "club",
    )
    assert belief.current_value == {"entity_id": "club:liverpool"}


def test_failed_resolution_is_persistent_and_retryable(monkeypatch):
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")

    event = make_event(conn, "obs:1")

    def fail(*args, **kwargs):
        raise RuntimeError("resolver unavailable")

    monkeypatch.setattr(
        "apps.asset_library.resolution_orchestrator.resolve_belief",
        fail,
    )

    first = process_pending_change_events(conn)
    assert first[0].status == "FAILED"
    status = get_resolution_status(conn, event.change_event_id)
    assert status.status == "FAILED"
    assert status.attempts == 1
    assert status.error_type == "RuntimeError"
    assert status.error_message == "resolver unavailable"

    monkeypatch.setattr(
        "apps.asset_library.resolution_orchestrator.resolve_belief",
        __import__(
            "apps.asset_library.belief",
            fromlist=["resolve_belief"],
        ).resolve_belief,
    )

    second = process_pending_change_events(
        conn,
        as_of="2026-09-28T10:00:00+00:00",
    )
    assert second[0].status == "RESOLVED"

    status = get_resolution_status(conn, event.change_event_id)
    assert status.status == "RESOLVED"
    assert status.attempts == 2
    assert status.error_type is None
    assert status.error_message is None


def test_failed_event_does_not_block_later_event(monkeypatch):
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")

    event_one = make_event(conn, "obs:1")
    add_observation(
        conn,
        "obs:2",
        "src:primary",
        "club:liverpool",
        "2026-09-29T09:00:00+00:00",
    )
    events = detect_changes(conn, "player", "player:1", "club")
    assert [event.observation_id for event in events] == ["obs:2"]

    original = __import__(
        "apps.asset_library.belief",
        fromlist=["resolve_belief"],
    ).resolve_belief
    calls = {"count": 0}

    def fail_once(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(
        "apps.asset_library.resolution_orchestrator.resolve_belief",
        fail_once,
    )

    results = process_pending_change_events(
        conn,
        as_of="2026-09-29T10:00:00+00:00",
    )

    assert [result.status for result in results] == [
        "FAILED",
        "RESOLVED",
    ]
    assert get_resolution_status(
        conn,
        event_one.change_event_id,
    ).status == "FAILED"


def test_limit_bounds_one_batch():
    conn = setup_db()
    add_source(conn, "src:primary", "Official", "primary")

    make_event(conn, "obs:1")
    add_observation(
        conn,
        "obs:2",
        "src:primary",
        "club:liverpool",
        "2026-09-29T09:00:00+00:00",
    )
    detect_changes(conn, "player", "player:1", "club")

    first = process_pending_change_events(
        conn,
        limit=1,
        as_of="2026-09-29T10:00:00+00:00",
    )
    second = process_pending_change_events(
        conn,
        limit=1,
        as_of="2026-09-29T10:00:00+00:00",
    )

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].change_event_id != second[0].change_event_id


def test_no_pending_events_returns_empty_without_side_effects():
    conn = setup_db()

    assert process_pending_change_events(conn) == []


def test_negative_limits_are_rejected():
    conn = setup_db()

    try:
        process_pending_change_events(conn, limit=0)
    except ValueError as error:
        assert "limit" in str(error)
    else:
        raise AssertionError("expected ValueError")
