import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from time import monotonic

from django.db import connection, connections
from django.utils import timezone

import pytest

from baserow.ws import realtime_events
from baserow.ws.models import (
    RealtimeEvent,
    RealtimeEventHistoryState,
    RealtimeEventHistorySummary,
)
from baserow.ws.realtime_events import FIRST_CONNECT_CURSOR, RealtimeEventHandler

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.websockets]


@pytest.fixture(autouse=True)
def replay_settings(settings):
    settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS = 100
    settings.REALTIME_REPLAY_RETENTION_HOURS = 24


def group_event(*, event_type="rows_updated", socket=None, excluded=None, **data):
    event = {
        "type": "broadcast_to_group",
        "payload": {"type": event_type, **data},
        "ignore_web_socket_id": socket,
    }
    if excluded is not None:
        event["exclude_user_ids"] = excluded
    return event


def users_event(*, recipients=None, everyone=False, socket=None):
    return {
        "type": "broadcast_to_users",
        "payload": {"type": "workspace_updated", "private_data": "omit-me"},
        "user_ids": [42] if recipients is None else recipients,
        "send_to_all_users": everyone,
        "ignore_web_socket_id": socket,
    }


def individual_event(*, recipients=None, socket=None):
    return {
        "type": "broadcast_to_users_individual_payloads",
        "payload_map": {
            str(user_id): {"type": event_type, "private_data": "omit-me"}
            for user_id, event_type in (
                {42: "workspace_updated"} if recipients is None else recipients
            ).items()
        },
        "ignore_web_socket_id": socket,
    }


def record(group="table-1", payload=None, *, age=timedelta()):
    event_id = RealtimeEventHandler.record_events(
        [(group, group_event() if payload is None else payload)]
    )[0]
    RealtimeEvent.objects.filter(pk=event_id).update(created_at=timezone.now() - age)
    return event_id


def replay(cursor, *, user=42, groups=None, socket="own"):
    return RealtimeEventHandler.get_replay_events_result(
        user, ["table-1"] if groups is None else groups, cursor, socket
    )


def cleanup():
    return RealtimeEventHandler.cleanup_old_realtime_events(timedelta(days=1))


@pytest.mark.parametrize("missed_old", [False, True])
@pytest.mark.parametrize("recent", [False, True])
def test_missing_baseline_preserves_no_change_replay_and_refresh(missed_old, recent):
    baseline = record("other-page", age=timedelta(days=3))
    record("other-page", age=timedelta(days=2))
    if missed_old:
        record(age=timedelta(days=2))
    fresh_id = record(age=timedelta(hours=1)) if recent else None

    # An expired relevant gap requires refresh even while its payload still
    # exists, and a newer full event must not hide that gap after compaction.
    assert replay(baseline).force_refresh is missed_old
    assert cleanup() == 2 + missed_old
    assert not RealtimeEvent.objects.filter(pk=baseline).exists()

    result = replay(baseline)
    assert result.force_refresh is missed_old
    assert result.refresh_reason == ("expired_payload" if missed_old else None)
    assert [event.id for event in result.replay_events] == (
        [fresh_id] if recent and not missed_old else []
    )
    if not missed_old:
        assert result.latest_event_id == (fresh_id if recent else baseline)
    state = RealtimeEventHistoryState.objects.get(pk=1)
    assert state.floor == 0
    assert state.compacted_event_id > baseline


@pytest.mark.parametrize(
    "group,payload,socket,relevant",
    [
        ("table-1", group_event(), "own", True),
        ("other-page", group_event(), "own", False),
        ("table-1", group_event(socket="own"), "own", False),
        ("table-1", group_event(socket="other"), "own", True),
        ("table-1", group_event(socket="own"), None, True),
        ("table-1", group_event(excluded=[42]), "own", False),
        ("table-1", group_event(excluded=[7]), "own", True),
        ("users", users_event(), "own", True),
        ("users", users_event(recipients=[7]), "own", False),
        ("users", users_event(recipients=[], everyone=True), "own", True),
        ("users", users_event(socket="own"), "own", False),
        ("users", users_event(socket="own"), None, True),
        ("users", individual_event(), "own", True),
        (
            "users",
            individual_event(recipients={7: "workspace_updated"}),
            "own",
            False,
        ),
        ("users", individual_event(socket="own"), "own", False),
        ("users", individual_event(socket="own"), None, True),
    ],
    ids=[
        "page",
        "other-page",
        "own-page",
        "other-socket-page",
        "page-without-client-socket",
        "excluded-page",
        "other-excluded-page",
        "target-user",
        "other-user",
        "everyone",
        "own-user",
        "user-without-client-socket",
        "individual",
        "other-individual",
        "own-individual",
        "individual-without-client-socket",
    ],
)
def test_summary_and_expired_payload_have_identical_relevance(
    group, payload, socket, relevant
):
    baseline = record("baseline", age=timedelta(days=3))
    expired = record(group, payload, age=timedelta(days=2))

    assert replay(baseline, socket=socket).force_refresh is relevant
    assert cleanup() == 2
    assert not RealtimeEvent.objects.filter(pk=expired).exists()
    result = replay(baseline, socket=socket)
    assert result.force_refresh is relevant
    assert result.replay_events == []


@pytest.mark.parametrize("kind", ["group", "users", "individual"])
def test_missing_and_null_socket_share_one_summary_without_losing_changes(kind):
    group = "table-1" if kind == "group" else "users"
    make_payload = {
        "group": group_event,
        "users": users_event,
        "individual": individual_event,
    }[kind]
    payload = make_payload()
    del payload["ignore_web_socket_id"]
    missing = record(group, payload, age=timedelta(days=2))
    null = record(group, make_payload(), age=timedelta(days=2))
    own = record(group, make_payload(socket="own"), age=timedelta(days=2))

    assert cleanup() == 3
    summary = RealtimeEventHistorySummary.objects.get()
    assert (summary.latest_event_id, summary.latest_socket_id) == (own, "own")
    assert (summary.previous_event_id, summary.previous_socket_id) == (null, None)
    assert replay(missing).force_refresh is True
    assert replay(null).force_refresh is False
    assert replay(null, socket=None).force_refresh is True


@pytest.mark.parametrize(
    "ignored_socket,client_socket",
    [(42, "42"), (True, "true"), (["own"], "own"), ({"id": "own"}, "own")],
    ids=["number", "boolean", "array", "object"],
)
def test_non_string_socket_values_do_not_exclude_a_client(
    ignored_socket, client_socket
):
    baseline = record("baseline", age=timedelta(days=3))
    record(payload=group_event(socket=ignored_socket), age=timedelta(days=2))
    assert replay(baseline, socket=client_socket).force_refresh is True

    assert cleanup() == 2
    summary = RealtimeEventHistorySummary.objects.get(channel_group="table-1")
    assert summary.latest_socket_id is None
    assert replay(baseline, socket=client_socket).force_refresh is True


def test_many_originating_sockets_keep_only_two_distinct_socket_watermarks():
    ids = [
        record(payload=group_event(socket=f"socket-{index}"), age=timedelta(days=2))
        for index in range(20)
    ]
    newest = record(payload=group_event(socket="socket-19"), age=timedelta(days=2))

    assert cleanup() == 21
    assert not RealtimeEvent.objects.exists()
    summary = RealtimeEventHistorySummary.objects.get()
    assert (summary.latest_event_id, summary.latest_socket_id) == (newest, "socket-19")
    assert (summary.previous_event_id, summary.previous_socket_id) == (
        ids[-2],
        "socket-18",
    )
    assert replay(ids[-3], socket="socket-19").force_refresh is True
    assert replay(ids[-2], socket="socket-19").force_refresh is False
    assert replay(ids[-2], socket="socket-18").force_refresh is True
    assert replay(ids[-2], socket=None).force_refresh is True


def test_summary_merges_batches_in_id_order_despite_different_timestamp_order(
    monkeypatch,
):
    monkeypatch.setattr(realtime_events, "REALTIME_EVENTS_CLEANUP_BATCH_SIZE", 2)
    ids = [
        record(payload=group_event(socket=socket), age=timedelta(days=days))
        for socket, days in [("a", 2), ("b", 5), ("a", 4), ("c", 3)]
    ]

    assert cleanup() == 4
    summary = RealtimeEventHistorySummary.objects.get()
    assert (summary.latest_event_id, summary.latest_socket_id) == (ids[-1], "c")
    assert (summary.previous_event_id, summary.previous_socket_id) == (ids[-2], "a")
    assert RealtimeEventHistoryState.objects.get(pk=1).compacted_event_id == ids[-1]
    assert replay(ids[-2], socket="c").force_refresh is False
    assert replay(ids[1], socket="c").force_refresh is True


def test_later_cleanup_of_lower_ids_does_not_regress_summary_or_high_water():
    lower = record(payload=group_event(socket="a"), age=timedelta(hours=1))
    other = record(payload=group_event(socket="b"), age=timedelta(days=2))
    latest = record(payload=group_event(socket="a"), age=timedelta(days=2))
    assert cleanup() == 2
    original = RealtimeEventHistorySummary.objects.values().get()

    RealtimeEvent.objects.filter(pk=lower).update(
        created_at=timezone.now() - timedelta(days=3)
    )
    assert cleanup() == 1
    assert RealtimeEventHistorySummary.objects.values().get() == original
    assert RealtimeEventHandler.get_latest_event_id() == latest

    repeated = record(payload=group_event(socket="a"), age=timedelta(days=2))
    assert cleanup() == 1
    summary = RealtimeEventHistorySummary.objects.get()
    assert (summary.latest_event_id, summary.latest_socket_id) == (repeated, "a")
    assert (summary.previous_event_id, summary.previous_socket_id) == (other, "b")

    newest = record(payload=group_event(socket="c"), age=timedelta(days=2))
    assert cleanup() == 1
    summary.refresh_from_db()
    assert (summary.latest_event_id, summary.latest_socket_id) == (newest, "c")
    assert (summary.previous_event_id, summary.previous_socket_id) == (repeated, "a")


@pytest.mark.parametrize("individual", [False, True], ids=["group", "individual"])
def test_summary_retains_recovery_types_without_business_payload(individual):
    for event_type in ("rows_updated", "rows_deleted"):
        payload = (
            individual_event(recipients={42: event_type, 7: "workspace_updated"})
            if individual
            else group_event(event_type=event_type, secret="omit-me", rows=[1, 2, 3])
        )
        payload["request_debug_data"] = "omit-me"
        record("users" if individual else "table-1", payload, age=timedelta(days=2))

    assert cleanup() == 2
    summaries = list(RealtimeEventHistorySummary.objects.order_by("latest_event_id"))
    assert len(summaries) == 2
    for summary, event_type in zip(summaries, ("rows_updated", "rows_deleted")):
        assert "ignore_web_socket_id" not in summary.payload
        assert "request_debug_data" not in summary.payload
        assert "omit-me" not in json.dumps(summary.payload)
        if individual:
            assert summary.payload["payload_map"] == {
                "7": {"type": "workspace_updated"},
                "42": {"type": event_type},
            }
            assert summary.target_user_ids == [7, 42]
            assert summary.all_users is False
        else:
            assert summary.payload["payload"] == {"type": event_type}


@pytest.mark.parametrize("kind", ["recipients", "exclusions"])
def test_reordered_and_duplicate_audience_ids_share_one_summary(kind):
    for audience in ([42, 7, 42], [7, 42]):
        payload = (
            users_event(recipients=audience)
            if kind == "recipients"
            else group_event(excluded=audience)
        )
        latest = record(
            "users" if kind == "recipients" else "table-1",
            payload,
            age=timedelta(days=2),
        )

    assert cleanup() == 2
    summary = RealtimeEventHistorySummary.objects.get()
    key = "user_ids" if kind == "recipients" else "exclude_user_ids"
    assert summary.payload[key] == [7, 42]
    assert summary.latest_event_id == latest


def test_retention_increase_cannot_make_summarized_payload_replayable(settings):
    baseline = record("baseline", age=timedelta(days=3))
    expired = record(age=timedelta(days=2))
    assert cleanup() == 2

    settings.REALTIME_REPLAY_RETENTION_HOURS = 240
    result = replay(baseline)
    assert result.force_refresh is True
    assert result.replay_events == []
    recent = record(age=timedelta(hours=1))
    result = replay(expired)
    assert result.force_refresh is False
    assert [event.id for event in result.replay_events] == [recent]


def test_empty_full_buffer_keeps_summarized_high_water_without_raising_loss_floor():
    record(age=timedelta(days=3))
    latest = record(age=timedelta(days=2))

    assert cleanup() == 2
    assert not RealtimeEvent.objects.exists()
    assert RealtimeEventHandler.get_latest_event_id() == latest
    state = RealtimeEventHistoryState.objects.get(pk=1)
    assert (state.floor, state.compacted_event_id) == (0, latest)
    baseline = replay(FIRST_CONNECT_CURSOR)
    assert baseline.force_refresh is False
    assert baseline.latest_event_id == latest
    assert baseline.replay_events == []

    fresh = record()
    assert fresh > latest
    result = replay(latest)
    assert result.force_refresh is False
    assert [event.id for event in result.replay_events] == [fresh]


def is_event_delete(sql):
    return re.search(r'\bDELETE\s+FROM\s+"?ws_realtime_events\b', sql, re.IGNORECASE)


def test_failure_after_deletion_rolls_back_payloads_summary_and_high_water():
    record(payload=group_event(value="first"), age=timedelta(days=2))
    record(payload=group_event(value="second"), age=timedelta(days=2))
    record(age=timedelta(hours=1))
    originals = list(RealtimeEvent.objects.order_by("id").values())
    state = RealtimeEventHistoryState.objects.values().get()

    def fail_after_delete(execute, sql, params, many, context):
        result = execute(sql, params, many, context)
        if is_event_delete(sql):
            raise RuntimeError("failed after deleting expired payloads")
        return result

    with (
        connection.execute_wrapper(fail_after_delete),
        pytest.raises(RuntimeError, match="failed after deleting expired payloads"),
    ):
        cleanup()

    assert list(RealtimeEvent.objects.order_by("id").values()) == originals
    assert not RealtimeEventHistorySummary.objects.exists()
    assert RealtimeEventHistoryState.objects.values().get() == state


def test_replay_on_another_connection_remains_correct_during_compaction_delete():
    baseline = record("baseline", age=timedelta(days=3))
    record(age=timedelta(days=2))
    fresh = record(age=timedelta(hours=1))
    reads = []

    def read_history():
        try:
            result = replay(baseline)
            return RealtimeEventHandler.get_latest_event_id(), result
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=1) as executor:

        def read_while_delete_is_uncommitted(execute, sql, params, many, context):
            result = execute(sql, params, many, context)
            if is_event_delete(sql):
                assert connection.in_atomic_block
                # The reader has its own connection and must finish before the
                # deleting transaction commits, with the expired gap still visible.
                reads.append(executor.submit(read_history).result(timeout=5))
            return result

        with connection.execute_wrapper(read_while_delete_is_uncommitted):
            assert cleanup() == 2

    assert len(reads) == 1
    latest, result = reads[0]
    assert latest == fresh
    assert result.force_refresh is True
    assert result.replay_events == []
    assert replay(baseline).force_refresh is True
    assert list(RealtimeEvent.objects.values_list("id", flat=True)) == [fresh]


@pytest.mark.parametrize(
    "latest_socket", ["b", None], ids=["two-sockets", "null-socket"]
)
def test_concurrent_batches_merge_the_same_route_without_losing_either_socket(
    monkeypatch, latest_socket
):
    monkeypatch.setattr(realtime_events, "REALTIME_EVENTS_CLEANUP_BATCH_SIZE", 1)
    baseline = record("baseline")
    first = record(payload=group_event(socket="a"), age=timedelta(days=2))
    latest = record(payload=group_event(socket=latest_socket), age=timedelta(days=2))
    candidates_locked = Barrier(2)

    def compact_one():
        db = connections["default"]

        def synchronize_candidates(execute, sql, params, many, context):
            result = execute(sql, params, many, context)
            if "FOR UPDATE SKIP LOCKED" in sql:
                # Both transactions lock separate full rows before either inserts
                # the shared route. The upsert must merge their evidence safely.
                candidates_locked.wait(timeout=5)
            return result

        try:
            with db.execute_wrapper(synchronize_candidates):
                return RealtimeEventHandler._delete_realtime_events_batch(
                    timezone.now() - timedelta(days=1), monotonic() + 10
                )
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(compact_one) for _ in range(2)]
        try:
            assert [future.result(timeout=10) for future in futures] == [1, 1]
        finally:
            candidates_locked.abort()

    summary = RealtimeEventHistorySummary.objects.get()
    assert (summary.latest_event_id, summary.latest_socket_id) == (
        latest,
        latest_socket,
    )
    assert (summary.previous_event_id, summary.previous_socket_id) == (first, "a")
    assert list(RealtimeEvent.objects.values_list("id", flat=True)) == [baseline]
    state = RealtimeEventHistoryState.objects.get(pk=1)
    assert (state.floor, state.compacted_event_id) == (0, latest)
    assert replay(baseline, socket="b").force_refresh is True
    assert replay(first, socket="b").force_refresh is (latest_socket is None)
    assert replay(first, socket="a").force_refresh is True
