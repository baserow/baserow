import json
from importlib import import_module
from unittest.mock import patch

from django.db import IntegrityError, connection

import pytest

from baserow.ws.models import RealtimeEvent, RealtimeEventHistoryState
from baserow.ws.realtime_events import RealtimeEventHandler


def _migration():
    return import_module("baserow.ws.migrations.0002_realtime_event_indexes")


def _indexes():
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.relname, i.indisvalid AND i.indisready,
                pg_get_expr(i.indpred, i.indrelid), pg_get_indexdef(i.indexrelid)
            FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid
            WHERE i.indrelid = 'ws_realtime_events'::regclass
            """
        )
        return {
            name: (valid, predicate, definition)
            for name, valid, predicate, definition in cursor
        }


def _apply(direction):
    with connection.schema_editor(atomic=False) as editor:
        getattr(_migration(), direction)(None, editor)


def _table_storage():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relfilenode, reloptions FROM pg_class "
            "WHERE oid = 'ws_realtime_events'::regclass"
        )
        filenode, options = cursor.fetchone()
        return filenode, dict(option.split("=", 1) for option in options or [])


def _legacy_insert(channel_group="users", payload=None):
    # Old workers know nothing about the new fields and omit them from INSERT.
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO ws_realtime_events (channel_group, payload, created_at) "
            "VALUES (%s, %s::jsonb, now()) RETURNING id",
            [
                channel_group,
                json.dumps(
                    payload
                    if payload is not None
                    else {
                        "type": "broadcast_to_users",
                        "user_ids": [42],
                        "send_to_all_users": False,
                        "ignore_web_socket_id": None,
                        "payload": {"type": "test"},
                    }
                ),
            ],
        )
        return cursor.fetchone()[0]


def _columns():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT attname FROM pg_attribute "
            "WHERE attrelid = 'ws_realtime_events'::regclass "
            "AND attnum > 0 AND NOT attisdropped"
        )
        return {row[0] for row in cursor}


@pytest.mark.django_db(transaction=True)
def test_replay_reset_upgrade_and_rollback_keep_ids_and_old_writer_compatibility():
    migration = _migration()
    _apply("backwards")
    try:
        old_cursor = _legacy_insert()
        lost_id = _legacy_insert()
        old_filenode = _table_storage()[0]
        _apply("forwards")
        assert RealtimeEvent.objects.count() == 0
        assert _table_storage()[0] != old_filenode
        assert {"target_user_ids", "all_users"} <= _columns()

        # Activate history after the reset, as ws.0003 does in deployment. The
        # sequence records the missed event even though its payload is now gone.
        RealtimeEventHistoryState.objects.all().delete()
        RealtimeEventHandler._initialize_realtime_history()
        assert RealtimeEventHistoryState.objects.get(pk=1).floor == lost_id
        new_id = _legacy_insert()
        assert new_id > lost_id > old_cursor
        event = RealtimeEvent.objects.get(id=new_id)
        assert event.target_user_ids == [42]
        assert event.all_users is False
        result = RealtimeEventHandler.get_replay_events_result(
            42, [], old_cursor, "socket"
        )
        assert result.force_refresh is True
        assert result.refresh_reason == "unknown_history"
        indexes = _indexes()
        assert migration.OLD_INDEX not in indexes
        assert migration.USERS_INDEX not in indexes
        assert indexes["ws_realtime_channel_group_idx"][0]
        valid, predicate, definition = indexes[migration.TARGETS_INDEX]
        assert valid and "'users'" in predicate
        assert "USING gin (target_user_ids)" in definition
        valid, predicate, definition = indexes[migration.ALL_USERS_INDEX]
        assert valid and "'users'" in predicate and "all_users" in predicate
        assert "USING btree (id)" in definition
        valid, predicate, definition = indexes[migration.CREATED_INDEX]
        assert valid and predicate is None
        assert "USING btree (created_at, id)" in definition
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relpersistence FROM pg_class WHERE oid IN "
                "('ws_realtime_events'::regclass, "
                "pg_get_serial_sequence('ws_realtime_events', 'id')::regclass) "
                "ORDER BY relkind"
            )
            assert cursor.fetchall() == [("p",), ("u",)]

        _apply("backwards")
        assert not {"target_user_ids", "all_users"} & _columns()
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM ws_realtime_events")
            assert cursor.fetchone() == (0,)
            cursor.execute(
                "SELECT relpersistence FROM pg_class WHERE oid = "
                "pg_get_serial_sequence('ws_realtime_events', 'id')::regclass"
            )
            assert cursor.fetchone() == ("p",)
        assert _legacy_insert() > new_id
        indexes = _indexes()
        assert indexes[migration.OLD_INDEX][0]
        assert indexes[migration.OLD_INDEX][1] is None
        assert migration.TARGETS_INDEX not in indexes
        assert migration.ALL_USERS_INDEX not in indexes
        assert migration.CREATED_INDEX not in indexes
    finally:
        _apply("forwards")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload, expected_ids, expected_all",
    [
        (
            {
                "type": "broadcast_to_users",
                "user_ids": [42, 7, 42.0, -2147483648, 2147483647, 0],
                "send_to_all_users": True,
            },
            [-2147483648, 0, 7, 42, 2147483647],
            True,
        ),
        (
            {
                "type": "broadcast_to_users",
                "user_ids": ["42", None, True, 42.5, 2147483648, -(10**100)],
                "send_to_all_users": "true",
            },
            [],
            False,
        ),
        (
            {
                "type": "broadcast_to_users_individual_payloads",
                "payload_map": {
                    key: {"sensitive": "body"}
                    for key in [
                        "42",
                        "7",
                        "-2147483648",
                        "2147483647",
                        "0",
                        "-0",
                        "0042",
                        "+42",
                        "42.0",
                        "1e2",
                        "2147483648",
                        "9" * 100,
                    ]
                },
                "send_to_all_users": True,
            },
            [-2147483648, 0, 7, 42, 2147483647],
            False,
        ),
        ({"type": "broadcast_to_users", "user_ids": {"42": True}}, [], False),
        (
            {"type": "broadcast_to_users_individual_payloads", "payload_map": [42]},
            [],
            False,
        ),
        ({"type": "unknown", "user_ids": [42], "send_to_all_users": True}, [], False),
    ],
)
def test_replay_target_trigger_handles_legacy_routing(
    payload, expected_ids, expected_all
):
    event = RealtimeEvent.objects.get(id=_legacy_insert(payload=payload))
    assert event.target_user_ids == expected_ids
    assert event.all_users is expected_all
    assert event.payload == payload


@pytest.mark.django_db
def test_replay_target_trigger_recomputes_legacy_updates_and_group_changes():
    event_id = _legacy_insert()
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE ws_realtime_events SET payload = %s::jsonb WHERE id = %s",
            [
                json.dumps(
                    {
                        "type": "broadcast_to_users_individual_payloads",
                        "payload_map": {"7": {"private": "data"}},
                    }
                ),
                event_id,
            ],
        )
    assert RealtimeEvent.objects.get(id=event_id).target_user_ids == [7]
    RealtimeEvent.objects.filter(id=event_id).update(channel_group="table-1")
    event = RealtimeEvent.objects.get(id=event_id)
    assert event.target_user_ids == [] and event.all_users is False
    RealtimeEvent.objects.filter(id=event_id).update(channel_group="users")
    assert RealtimeEvent.objects.get(id=event_id).target_user_ids == [7]
    # Explicit caller metadata cannot override the envelope on INSERT.
    event = RealtimeEvent.objects.create(
        channel_group="table-1",
        payload={"type": "broadcast_to_users", "send_to_all_users": True},
        target_user_ids=[42],
        all_users=True,
    )
    event.refresh_from_db()
    assert event.target_user_ids == [] and event.all_users is False


@pytest.mark.django_db(transaction=True)
def test_replay_autovacuum_settings_are_reversible_and_retry_safe():
    expected = {
        "autovacuum_analyze_threshold": "2000",
        "autovacuum_analyze_scale_factor": "0.002",
        "autovacuum_vacuum_threshold": "5000",
        "autovacuum_vacuum_scale_factor": "0.01",
        "autovacuum_vacuum_insert_threshold": "5000",
        "autovacuum_vacuum_insert_scale_factor": "0.01",
    }
    _, original_options = _table_storage()
    unrelated = {
        name: value for name, value in original_options.items() if name not in expected
    }
    unrelated["fillfactor"] = "80"
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE ws_realtime_events SET (fillfactor = 80)")
    try:
        for direction in [
            "backwards",
            "forwards",
            "forwards",
            "backwards",
            "backwards",
        ]:
            _apply(direction)
            assert _table_storage()[1] == (
                {**unrelated, **expected} if direction == "forwards" else unrelated
            )
    finally:
        _apply("forwards")
        with connection.cursor() as cursor:
            if "fillfactor" in original_options:
                cursor.execute(
                    "ALTER TABLE ws_realtime_events SET "
                    f"(fillfactor = {int(original_options['fillfactor'])})"
                )
            else:
                cursor.execute("ALTER TABLE ws_realtime_events RESET (fillfactor)")


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "index_name",
    [
        "ws_realtime_users_payload_idx",
        "ws_realtime_targets_idx",
        "ws_realtime_created_id_idx",
    ],
)
def test_replay_reset_replaces_invalid_indexes_from_interrupted_draft(index_name):
    _apply("backwards")
    try:
        _legacy_insert()
        _legacy_insert()
        with connection.cursor() as cursor, pytest.raises(IntegrityError):
            cursor.execute(
                f'CREATE UNIQUE INDEX CONCURRENTLY "{index_name}" '
                "ON ws_realtime_events (channel_group)"
            )
        assert _indexes()[index_name][0] is False
        _apply("forwards")
        indexes = _indexes()
        if index_name == _migration().USERS_INDEX:
            assert index_name not in indexes
        else:
            assert indexes[index_name][0]
        assert _migration().OLD_INDEX not in indexes
    finally:
        _apply("forwards")


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("direction", ["forwards", "backwards"])
def test_replay_reset_failure_rolls_back_rows_schema_and_indexes(direction):
    if direction == "forwards":
        _apply("backwards")
    event_id = _legacy_insert()
    before_storage = _table_storage()
    before_indexes = _indexes()
    before_columns = _columns()

    def fail_after_index_creation(execute, sql, params, many, context):
        result = execute(sql, params, many, context)
        if sql.startswith("CREATE INDEX"):
            raise RuntimeError("Interrupted after index creation")
        return result

    try:
        with connection.execute_wrapper(fail_after_index_creation):
            with pytest.raises(RuntimeError, match="Interrupted"):
                _apply(direction)
        assert _table_storage() == before_storage
        assert _indexes() == before_indexes
        assert _columns() == before_columns
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM ws_realtime_events")
            assert cursor.fetchall() == [(event_id,)]
        assert _legacy_insert() > event_id
        if direction == "backwards":
            assert RealtimeEvent.objects.get(id=event_id).target_user_ids == [42]
    finally:
        _apply("forwards")


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "configured, expected",
    [("0", ("1s", "3s")), ("500ms", ("500ms", "500ms")), ("20s", ("1s", "3s"))],
)
def test_replay_reset_preserves_stricter_timeouts_without_leaking(configured, expected):
    migration = _migration()
    observed = []
    drop_indexes = migration._drop_indexes

    def inspect_timeouts(cursor):
        cursor.execute(
            "SELECT current_setting('lock_timeout'), current_setting('statement_timeout')"
        )
        observed.append(cursor.fetchone())
        drop_indexes(cursor)

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_setting('lock_timeout'), current_setting('statement_timeout')"
        )
        original = cursor.fetchone()
        cursor.execute(
            "SELECT set_config('lock_timeout', %s, false), "
            "set_config('statement_timeout', %s, false)",
            [configured, configured],
        )
    try:
        with patch.object(migration, "_drop_indexes", side_effect=inspect_timeouts):
            _apply("forwards")
        assert observed == [expected]
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_setting('lock_timeout'), current_setting('statement_timeout')"
            )
            assert cursor.fetchone() == (configured, configured)
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('lock_timeout', %s, false), "
                "set_config('statement_timeout', %s, false)",
                list(original),
            )
