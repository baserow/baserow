from contextlib import closing
from datetime import timedelta
from importlib import import_module
from time import monotonic

from django.db import DatabaseError, OperationalError, connection, transaction
from django.db.migrations.loader import MigrationLoader
from django.utils import timezone

import pytest

from baserow.ws import history
from baserow.ws.models import (
    RealtimeEvent,
    RealtimeEventHistoryState,
    RealtimeEventHistorySummary,
)
from baserow.ws.realtime_events import RealtimeEventHandler

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.websockets]


def record(channel="table-1", socket=None):
    return RealtimeEventHandler.record_events(
        [
            (
                channel,
                {
                    "type": "broadcast_to_group",
                    "ignore_web_socket_id": socket,
                    "payload": {"type": "rows_updated", "private_data": "discard"},
                },
            )
        ]
    )[0]


def compact():
    return history.compact_events_batch(
        timezone.now(),
        monotonic() + 10,
        batch_size=5000,
        statement_timeout_ms=3000,
        lock_timeout_ms=250,
    )


def test_history_catalog_keeps_new_tables_unlogged_and_sequence_logged():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relname, relpersistence FROM pg_class WHERE oid IN ("
            "'ws_realtime_event_history_summary'::regclass, "
            "'ws_realtime_event_history_state'::regclass, "
            "pg_get_serial_sequence('ws_realtime_events', 'id')::regclass)"
        )
        persistence = dict(cursor.fetchall())
        assert persistence.pop("ws_realtime_event_history_summary") == "u"
        assert persistence.pop("ws_realtime_event_history_state") == "u"
        assert list(persistence.values()) == ["p"]
        cursor.execute(
            "SELECT seqcache FROM pg_sequence WHERE seqrelid = "
            "pg_get_serial_sequence('ws_realtime_events', 'id')::regclass"
        )
        assert cursor.fetchone() == (1,)
        cursor.execute(
            "SELECT indisvalid, pg_get_expr(indpred, indrelid) FROM pg_index "
            "WHERE indexrelid = 'ws_realtime_created_id_idx'::regclass"
        )
        assert cursor.fetchone() == (True, None)
        cursor.execute(
            "SELECT count(*) FROM pg_trigger "
            "WHERE tgrelid = 'ws_realtime_events'::regclass "
            "AND NOT tgisinternal AND (tgtype & 8) <> 0"
        )
        assert cursor.fetchone() == (0,)


def test_history_migration_roundtrip_preserves_event_data_and_age_index():
    loader = MigrationLoader(None)
    schema_migration = loader.get_migration("ws", "0003_realtime_event_history")
    previous_state = loader.project_state([("ws", "0002_realtime_event_indexes")])

    def filenodes():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_relation_filenode('ws_realtime_events'), "
                "pg_relation_filenode('ws_realtime_created_id_idx')"
            )
            return cursor.fetchone()

    at_current_schema = True
    try:
        # Exercise all CreateModel/RunPython operations in both directions,
        # without reapplying ws.0002's deliberate replay-buffer reset.
        with connection.schema_editor() as editor:
            schema_migration.unapply(previous_state.clone(), editor)
        at_current_schema = False
        old_id, recent_id = record(), record()
        RealtimeEvent.objects.filter(pk=old_id).update(
            created_at=timezone.now() - timedelta(days=2)
        )
        originals = list(RealtimeEvent.objects.order_by("id").values())
        original_filenodes = filenodes()

        with connection.schema_editor() as editor:
            schema_migration.apply(previous_state.clone(), editor)
        at_current_schema = True
        assert list(RealtimeEvent.objects.order_by("id").values()) == originals
        assert filenodes() == original_filenodes
        assert not RealtimeEventHistorySummary.objects.exists()
        state = RealtimeEventHistoryState.objects.get(pk=1)
        assert state.floor == state.compacted_event_id == recent_id

        with connection.schema_editor() as editor:
            schema_migration.unapply(previous_state.clone(), editor)
        at_current_schema = False
        assert list(RealtimeEvent.objects.order_by("id").values()) == originals
        assert filenodes() == original_filenodes
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_regclass('ws_realtime_event_history_summary'), "
                "to_regclass('ws_realtime_event_history_state'), "
                "to_regprocedure('ws_initialize_realtime_history()')"
            )
            assert cursor.fetchone() == (None, None, None)
        # Older writers still use the unchanged table and durable sequence.
        assert record() > recent_id
    finally:
        if not at_current_schema:
            with connection.schema_editor() as editor:
                schema_migration.apply(previous_state.clone(), editor)


def test_history_initialization_is_idempotent_with_existing_summary_and_floor():
    expired_id = record()
    assert compact() == 1
    retained_id = record()
    original_summary = RealtimeEventHistorySummary.objects.values().get()
    original_state = RealtimeEventHistoryState.objects.values().get()
    migration = import_module("baserow.ws.migrations.0003_realtime_event_history")

    for _ in range(2):
        with connection.schema_editor() as editor:
            migration.forwards(None, editor)
        assert RealtimeEventHistorySummary.objects.values().get() == original_summary
        assert RealtimeEventHistoryState.objects.values().get() == original_state
        assert list(RealtimeEvent.objects.values_list("id", flat=True)) == [retained_id]
    assert original_state["floor"] == 0
    assert original_state["compacted_event_id"] == expired_id


def test_history_reset_uses_allocated_sequence_ids_as_conservative_floor(settings):
    settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS = 100
    committed_id = record()
    assert compact() == 1
    with pytest.raises(RuntimeError, match="rollback"):
        with transaction.atomic():
            allocated_id = record()
            raise RuntimeError("rollback")
    assert allocated_id > committed_id

    # Simulate loss of every UNLOGGED history relation while retaining the
    # logged sequence, including IDs allocated by a rolled-back transaction.
    with connection.cursor() as cursor:
        cursor.execute(
            "TRUNCATE ws_realtime_events, ws_realtime_event_history_summary, "
            "ws_realtime_event_history_state"
        )
    assert RealtimeEventHandler.get_latest_event_id() >= allocated_id
    state = RealtimeEventHistoryState.objects.get(pk=1)
    assert state.floor == state.compacted_event_id >= allocated_id
    assert not RealtimeEventHistorySummary.objects.exists()
    result = RealtimeEventHandler.get_replay_events_result(
        42, ["table-1"], committed_id, None
    )
    assert result.force_refresh
    assert result.refresh_reason == "unknown_history"
    assert record() > state.floor


def test_history_initialization_waits_for_inflight_inserts():
    RealtimeEventHistoryState.objects.all().delete()
    with closing(
        connection.Database.connect(**connection.get_connection_params())
    ) as writer:
        with writer.cursor() as cursor:
            cursor.execute(
                "INSERT INTO ws_realtime_events (channel_group, payload, created_at) "
                "VALUES ('other', '{}', now()) RETURNING id"
            )
            inserted_id = cursor.fetchone()[0]

        # Initialization must wait for the invisible writer's RowExclusive lock
        # before treating its allocated ID as covered by the loss floor.
        with pytest.raises(OperationalError) as error:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '25ms'")
                cursor.execute("SELECT ws_initialize_realtime_history()")
        cause = error.value.__cause__
        assert (
            getattr(cause, "pgcode", None) or getattr(cause, "sqlstate", None)
        ) == "55P03"
        assert not RealtimeEventHistoryState.objects.exists()
        writer.commit()

    with connection.cursor() as cursor:
        cursor.execute("SELECT ws_initialize_realtime_history()")
    assert RealtimeEventHistoryState.objects.get(pk=1).floor >= inserted_id


def test_missing_history_with_cached_sequence_ids_fails_closed():
    RealtimeEventHistoryState.objects.all().delete()
    with connection.cursor() as cursor:
        cursor.execute(
            "DO $block$ BEGIN EXECUTE format('ALTER SEQUENCE %s CACHE 100', "
            "pg_get_serial_sequence('ws_realtime_events', 'id')); END $block$"
        )
    try:
        with (
            connection.cursor() as cursor,
            pytest.raises(DatabaseError, match="CACHE 1"),
        ):
            cursor.execute("SELECT ws_initialize_realtime_history()")
        assert not RealtimeEventHistoryState.objects.exists()
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "DO $block$ BEGIN EXECUTE format('ALTER SEQUENCE %s CACHE 1', "
                "pg_get_serial_sequence('ws_realtime_events', 'id')); END $block$"
            )
            cursor.execute("SELECT ws_initialize_realtime_history()")


@pytest.mark.parametrize("existing_summary", [False, True])
def test_route_hash_collision_rolls_back_summary_and_keeps_originals(
    monkeypatch, existing_summary
):
    record("first-audience", socket="first")
    if existing_summary:
        assert compact() == 1
        collision_key = bytes(RealtimeEventHistorySummary.objects.get().route_key)
    else:
        collision_key = b"x" * 32
    record("second-audience", socket="second")
    original_events = list(RealtimeEvent.objects.order_by("id").values())
    original_summaries = list(RealtimeEventHistorySummary.objects.values())
    original_state = RealtimeEventHistoryState.objects.values().get()
    summarize = history._summarize_candidates

    def force_hash_collision(candidates):
        # Inject a digest collision after real SQL routing extraction. The
        # existing-summary case still executes the actual ON CONFLICT update.
        return summarize(
            [(event_id, collision_key, *route) for event_id, _, *route in candidates]
        )

    monkeypatch.setattr(history, "_summarize_candidates", force_hash_collision)
    with pytest.raises(RuntimeError, match="route hash collision"):
        compact()
    assert list(RealtimeEvent.objects.order_by("id").values()) == original_events
    assert list(RealtimeEventHistorySummary.objects.values()) == original_summaries
    assert RealtimeEventHistoryState.objects.values().get() == original_state
