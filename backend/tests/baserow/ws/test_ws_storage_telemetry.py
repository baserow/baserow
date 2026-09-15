import os
from datetime import timedelta
from unittest.mock import MagicMock, call, patch

from django.db import OperationalError, connection, transaction
from django.utils import timezone

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from baserow.ws import history, realtime_events, telemetry
from baserow.ws.models import RealtimeEvent
from baserow.ws.realtime_events import RealtimeEventHandler
from baserow.ws.tasks import cleanup_old_realtime_events


@pytest.fixture
def storage_metrics(monkeypatch):
    metrics = {}
    for name in (
        "realtime_recording_events",
        "realtime_recording_batch_size",
        "realtime_recording_duration",
        "realtime_cleanup_deleted",
        "realtime_cleanup_batch_size",
        "realtime_cleanup_batch_duration",
        "realtime_cleanup_run_deleted",
        "realtime_cleanup_run_duration",
        "realtime_cleanup_skipped",
    ):
        metrics[name] = MagicMock()
        monkeypatch.setattr(telemetry, name, metrics[name])
    return metrics


def test_cleanup_overlap_is_observable_without_counting_a_database_run(storage_metrics):
    with (
        patch("django.core.cache.cache.lock") as make_lock,
        patch.object(RealtimeEventHandler, "cleanup_old_realtime_events") as cleanup,
    ):
        make_lock.return_value.acquire.return_value = False
        cleanup_old_realtime_events()

    cleanup.assert_not_called()
    make_lock.return_value.release.assert_not_called()
    storage_metrics["realtime_cleanup_skipped"].add.assert_called_once_with(
        1, {"process.pid": os.getpid(), "reason": "overlap"}
    )
    storage_metrics["realtime_cleanup_run_duration"].record.assert_not_called()


@pytest.mark.parametrize("failure_point", ["create", "acquire"])
def test_cleanup_lease_error_is_observable_and_still_fails_the_task(
    storage_metrics, failure_point
):
    with (
        patch("django.core.cache.cache.lock") as make_lock,
        patch.object(RealtimeEventHandler, "cleanup_old_realtime_events") as cleanup,
    ):
        fail = (
            make_lock if failure_point == "create" else make_lock.return_value.acquire
        )
        fail.side_effect = RedisConnectionError("cache unavailable")
        with pytest.raises(RedisConnectionError, match="cache unavailable"):
            cleanup_old_realtime_events()

    cleanup.assert_not_called()
    make_lock.return_value.release.assert_not_called()
    storage_metrics["realtime_cleanup_skipped"].add.assert_called_once_with(
        1, {"process.pid": os.getpid(), "reason": "lock_error"}
    )
    storage_metrics["realtime_cleanup_run_duration"].record.assert_not_called()


@pytest.mark.django_db
def test_recording_metrics_measure_real_insert_without_additional_queries(
    monkeypatch, storage_metrics, django_assert_num_queries
):
    now = [0.0]
    monkeypatch.setattr(telemetry, "monotonic", lambda: now[0])

    def timed_execute(execute, sql, params, many, context):
        result = execute(sql, params, many, context)
        now[0] += 0.025
        return result

    events = [
        ("users", {"payload": {"secret": "private event"}, "user_ids": [123]}),
        ("table-987", {"payload": {"row_id": 456}}),
        ("view-private-slug", {"payload": {"row_id": 789}}),
    ]
    with connection.execute_wrapper(timed_execute), django_assert_num_queries(1):
        ids = RealtimeEventHandler.record_events(events)

    assert (
        list(
            RealtimeEvent.objects.filter(id__in=ids)
            .order_by("id")
            .values_list("channel_group", "payload")
        )
        == events
    )
    attributes = {"process.pid": os.getpid(), "outcome": "success"}
    storage_metrics["realtime_recording_duration"].record.assert_called_once_with(
        pytest.approx(25.0), attributes
    )
    storage_metrics["realtime_recording_batch_size"].record.assert_called_once_with(
        3, attributes
    )
    assert storage_metrics["realtime_recording_events"].add.call_args_list == [
        call(1, {**attributes, "destination": "users"}),
        call(2, {**attributes, "destination": "page"}),
    ]


@pytest.mark.django_db
def test_recording_metrics_count_failed_attempts_without_claiming_success(
    storage_metrics,
):
    def fail_insert(execute, sql, params, many, context):
        if sql.lstrip().upper().startswith("INSERT"):
            raise OperationalError("database unavailable")
        return execute(sql, params, many, context)

    with pytest.raises(OperationalError, match="database unavailable"):
        with transaction.atomic(), connection.execute_wrapper(fail_insert):
            RealtimeEventHandler.record_events([("table-987", {"payload": {}})])

    assert RealtimeEvent.objects.count() == 0
    attributes = {"process.pid": os.getpid(), "outcome": "error"}
    storage_metrics["realtime_recording_events"].add.assert_called_once_with(
        1, {**attributes, "destination": "page"}
    )
    storage_metrics["realtime_recording_batch_size"].record.assert_called_once_with(
        1, attributes
    )
    duration = storage_metrics["realtime_recording_duration"].record.call_args
    assert duration.args[0] >= 0
    assert duration.args[1] == attributes


@pytest.mark.django_db
def test_recording_metrics_include_serialization_errors(storage_metrics):
    with pytest.raises(TypeError):
        with transaction.atomic():
            RealtimeEventHandler.record_events([("users", {"invalid": object()})])

    assert RealtimeEvent.objects.count() == 0
    attributes = {"process.pid": os.getpid(), "outcome": "error"}
    storage_metrics["realtime_recording_events"].add.assert_called_once_with(
        1, {**attributes, "destination": "users"}
    )
    storage_metrics["realtime_recording_batch_size"].record.assert_called_once_with(
        1, attributes
    )


def _create_expired_events():
    ids = RealtimeEventHandler.record_events(
        [("table-987", {"payload": {"i": i}}) for i in range(4)]
    )
    RealtimeEvent.objects.filter(id__in=ids[:3]).update(
        created_at=timezone.now() - timedelta(days=2)
    )
    return ids


@pytest.mark.django_db(transaction=True)
def test_cleanup_metrics_count_only_committed_rows(monkeypatch, storage_metrics):
    ids = _create_expired_events()
    monkeypatch.setattr(realtime_events, "REALTIME_EVENTS_CLEANUP_BATCH_SIZE", 2)
    committed_counts = []

    def record_committed_count(count, attributes):
        # The metric must not claim rows that can still roll back with the batch.
        assert not connection.in_atomic_block
        committed_counts.append(count)

    storage_metrics["realtime_cleanup_deleted"].add.side_effect = record_committed_count

    deleted = RealtimeEventHandler.cleanup_old_realtime_events(timedelta(hours=24))

    assert deleted == 3
    assert list(RealtimeEvent.objects.values_list("id", flat=True)) == ids[3:]
    assert committed_counts == [2, 1]
    attributes = {"process.pid": os.getpid(), "outcome": "success"}
    successful_batches = [
        entry
        for entry in storage_metrics[
            "realtime_cleanup_batch_size"
        ].record.call_args_list
        if entry.args[0] > 0
    ]
    assert successful_batches == [call(2, attributes), call(1, attributes)]
    storage_metrics["realtime_cleanup_run_deleted"].record.assert_called_once_with(
        3, attributes
    )
    duration = storage_metrics["realtime_cleanup_run_duration"].record.call_args
    assert duration.args[0] > 0
    assert duration.args[1] == attributes


@pytest.mark.django_db(transaction=True)
def test_cleanup_error_keeps_earlier_committed_progress_visible(
    monkeypatch, storage_metrics
):
    ids = _create_expired_events()
    monkeypatch.setattr(realtime_events, "REALTIME_EVENTS_CLEANUP_BATCH_SIZE", 2)
    delete_attempts = 0

    def fail_second_delete(execute, sql, params, many, context):
        nonlocal delete_attempts
        if "DELETE FROM" in sql.upper() and "ws_realtime_events" in sql:
            delete_attempts += 1
            if delete_attempts == 2:
                raise OperationalError("database unavailable")
        return execute(sql, params, many, context)

    with connection.execute_wrapper(fail_second_delete):
        with pytest.raises(OperationalError, match="database unavailable"):
            RealtimeEventHandler.cleanup_old_realtime_events(timedelta(hours=24))

    assert (
        list(RealtimeEvent.objects.order_by("id").values_list("id", flat=True))
        == (ids[2:])
    )
    attributes = {"process.pid": os.getpid()}
    storage_metrics["realtime_cleanup_deleted"].add.assert_called_once_with(
        2, attributes
    )
    storage_metrics["realtime_cleanup_run_deleted"].record.assert_called_once_with(
        2, {**attributes, "outcome": "error"}
    )
    batch_durations = storage_metrics[
        "realtime_cleanup_batch_duration"
    ].record.call_args_list
    assert [entry.args[1]["outcome"] for entry in batch_durations] == [
        "success",
        "error",
    ]


@pytest.mark.django_db(transaction=True)
def test_cleanup_budget_reports_progress_without_claiming_completion(
    monkeypatch, storage_metrics
):
    ids = _create_expired_events()
    monkeypatch.setattr(realtime_events, "REALTIME_EVENTS_CLEANUP_BATCH_SIZE", 2)
    now = [0.0]
    monkeypatch.setattr(realtime_events, "monotonic", lambda: now[0])
    monkeypatch.setattr(history, "monotonic", lambda: now[0])
    delete_batch = RealtimeEventHandler._delete_realtime_events_batch

    def slow_batch(cutoff, deadline):
        deleted = delete_batch(cutoff, deadline)
        now[0] += realtime_events.REALTIME_EVENTS_CLEANUP_BUDGET_SECONDS + 1
        return deleted

    monkeypatch.setattr(
        RealtimeEventHandler, "_delete_realtime_events_batch", staticmethod(slow_batch)
    )

    assert RealtimeEventHandler.cleanup_old_realtime_events(timedelta(hours=24)) == 2
    assert (
        list(RealtimeEvent.objects.order_by("id").values_list("id", flat=True))
        == (ids[2:])
    )
    attributes = {"process.pid": os.getpid()}
    storage_metrics["realtime_cleanup_deleted"].add.assert_called_once_with(
        2, attributes
    )
    storage_metrics["realtime_cleanup_run_deleted"].record.assert_called_once_with(
        2, {**attributes, "outcome": "budget"}
    )
    duration = storage_metrics["realtime_cleanup_run_duration"].record.call_args
    assert duration.args[1] == {**attributes, "outcome": "budget"}
