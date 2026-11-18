from unittest.mock import MagicMock, patch

from django.db import (
    NotSupportedError,
    OperationalError,
    connection,
    migrations,
    models,
)
from django.db.migrations.state import ModelState, ProjectState
from django.db.migrations.writer import MigrationWriter

import pytest

from baserow.core.migration_utils import (
    LockTimeoutMigration,
    RetryableAddIndexConcurrently,
    set_lock_timeout,
)
from baserow.core.psycopg import errors


@pytest.fixture
def concurrent_index_state():
    before = ProjectState()
    before.add_model(
        ModelState(
            "core",
            "IndexRecovery",
            fields=[
                ("id", models.AutoField(primary_key=True)),
                ("active", models.BooleanField(default=False)),
            ],
            options={"db_table": "migration_index_recovery"},
        )
    )
    operation = RetryableAddIndexConcurrently(
        model_name="indexrecovery",
        index=models.Index(
            fields=["-id"],
            condition=models.Q(active=True),
            include=["active"],
            name="migration_recovery_idx",
        ),
    )
    after = before.clone()
    operation.state_forwards("core", after)
    return operation, before, after


@pytest.fixture
def concurrent_index_table(concurrent_index_state):
    _, before, _ = concurrent_index_state
    model = before.apps.get_model("core", "IndexRecovery")
    with connection.schema_editor(atomic=False) as editor:
        editor.create_model(model)
    try:
        yield concurrent_index_state
    finally:
        with connection.schema_editor(atomic=False) as editor:
            editor.delete_model(model)


def recovery_index_state(schema="public"):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.oid, i.indisvalid AND i.indisready, pg_get_indexdef(c.oid) "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "JOIN pg_index i ON i.indexrelid = c.oid "
            "WHERE c.relname = 'migration_recovery_idx' AND n.nspname = %s",
            [schema],
        )
        return cursor.fetchone()


@pytest.mark.django_db(transaction=True)
def test_concurrent_index_forward_and_reverse_can_be_repeated(concurrent_index_table):
    operation, before, after = concurrent_index_table
    with connection.schema_editor(atomic=False) as editor:
        operation.database_forwards("core", editor, before, after)
        initial = recovery_index_state()
        assert initial[1] is True
        assert "(id DESC) INCLUDE (active) WHERE active" in initial[2]

        operation.database_forwards("core", editor, before, after)
        assert recovery_index_state() == initial  # No needless index rebuild.
        operation.database_backwards("core", editor, after, before)
        assert recovery_index_state() is None
        operation.database_backwards("core", editor, after, before)
        assert recovery_index_state() is None


@pytest.mark.django_db(transaction=True)
def test_concurrent_index_recovery_uses_the_tables_schema(concurrent_index_table):
    operation, before, after = concurrent_index_table
    with connection.cursor() as cursor:
        cursor.execute("SHOW search_path")
        original_path = cursor.fetchone()[0]
        cursor.execute("CREATE SCHEMA migration_index_shadow")
        cursor.execute("CREATE TABLE migration_index_shadow.other (id integer)")
        cursor.execute(
            "CREATE INDEX migration_recovery_idx ON migration_index_shadow.other (id)"
        )
        cursor.execute("SET search_path = migration_index_shadow, public")
    try:
        shadow = recovery_index_state("migration_index_shadow")
        with connection.schema_editor(atomic=False) as editor:
            operation.database_forwards("core", editor, before, after)
            assert recovery_index_state()[1] is True
            operation.database_backwards("core", editor, after, before)
        assert recovery_index_state() is None
        assert recovery_index_state("migration_index_shadow") == shadow
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('search_path', %s, false)", [original_path]
            )
            cursor.execute("DROP SCHEMA migration_index_shadow CASCADE")


@pytest.mark.django_db(transaction=True)
def test_concurrent_index_recovery_refuses_an_index_on_another_table(
    concurrent_index_table,
):
    operation, before, after = concurrent_index_table
    with connection.cursor() as cursor:
        cursor.execute("CREATE TABLE migration_index_other (id integer)")
        cursor.execute(
            "CREATE INDEX migration_recovery_idx ON migration_index_other (id)"
        )
    try:
        initial = recovery_index_state()
        with connection.schema_editor(atomic=False) as editor:
            with pytest.raises(ValueError, match="not an index on"):
                operation.database_forwards("core", editor, before, after)
            with pytest.raises(ValueError, match="not an index on"):
                operation.database_backwards("core", editor, after, before)
        assert recovery_index_state() == initial
    finally:
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE migration_index_other")


@pytest.mark.django_db
def test_concurrent_index_refuses_transactions(concurrent_index_state):
    operation, before, after = concurrent_index_state
    with connection.schema_editor(atomic=False) as editor:
        with pytest.raises(NotSupportedError, match="set atomic = False"):
            operation.database_forwards("core", editor, before, after)
        with pytest.raises(NotSupportedError, match="set atomic = False"):
            operation.database_backwards("core", editor, after, before)


@pytest.mark.django_db(transaction=True)
def test_concurrent_index_respects_database_router(
    concurrent_index_table, django_assert_num_queries
):
    operation, before, after = concurrent_index_table
    with (
        patch("django.db.router.allow_migrate", return_value=False),
        connection.schema_editor(atomic=False) as editor,
        django_assert_num_queries(0),
    ):
        operation.database_forwards("core", editor, before, after)
        operation.database_backwards("core", editor, after, before)
    assert recovery_index_state() is None


@pytest.mark.django_db(transaction=True)
def test_concurrent_index_sql_collection_does_not_need_the_table(
    concurrent_index_state, django_assert_num_queries
):
    operation, before, after = concurrent_index_state
    with (
        connection.schema_editor(atomic=False, collect_sql=True) as editor,
        django_assert_num_queries(0),
    ):
        operation.database_forwards("core", editor, before, after)
        operation.database_backwards("core", editor, after, before)
    assert len(editor.collected_sql) == 2
    assert editor.collected_sql[0].startswith("CREATE INDEX CONCURRENTLY")
    assert editor.collected_sql[1].startswith("DROP INDEX CONCURRENTLY")


def test_concurrent_index_serialization_preserves_operation_and_state(
    concurrent_index_state,
):
    operation, before, after = concurrent_index_state
    migration = migrations.Migration("test_index", "core")
    migration.operations = [operation]
    namespace = {}
    # Round-trip only the migration source generated from this test's operation.
    exec(MigrationWriter(migration).as_string(), namespace)  # noqa: S102
    restored = namespace["Migration"].operations[0]
    assert isinstance(restored, RetryableAddIndexConcurrently)
    assert restored.deconstruct() == operation.deconstruct()
    restored.state_forwards("core", before)
    assert before.models == after.models


def get_lock_timeout(cursor) -> str:
    cursor.execute("SHOW lock_timeout")
    return cursor.fetchone()[0]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "current, expected",
    [("0", "2s"), ("10s", "2s"), ("500ms", "500ms")],
)
def test_set_lock_timeout_keeps_a_stricter_timeout(current, expected):
    with connection.cursor() as cursor:
        cursor.execute(f"SET LOCAL lock_timeout = '{current}'")
        set_lock_timeout(cursor, "2s")
        assert get_lock_timeout(cursor) == expected


class FakeLockTimeoutMigration(LockTimeoutMigration):
    lock_attempts = 3
    operations = []


def lock_not_available() -> OperationalError:
    error = OperationalError("canceling statement due to lock timeout")
    error.__cause__ = errors.LockNotAvailable()
    return error


def apply_fake_migration(apply_side_effect):
    migration = FakeLockTimeoutMigration("0001_fake", "core")
    with (
        patch.object(
            migrations.Migration, "apply", side_effect=apply_side_effect
        ) as apply,
        patch("baserow.core.migration_utils.time.sleep") as sleep,
        connection.schema_editor(atomic=False) as schema_editor,
    ):
        try:
            result = migration.apply(MagicMock(), schema_editor)
        except OperationalError as error:
            result = error
    return result, apply, sleep


@pytest.mark.django_db
def test_lock_timeout_migration_retries_when_a_lock_is_not_available():
    result, apply, sleep = apply_fake_migration([lock_not_available(), "state"])

    assert result == "state"
    assert apply.call_count == 2
    sleep.assert_called_once_with(1)


@pytest.mark.django_db
def test_lock_timeout_migration_gives_up_after_the_last_attempt():
    result, apply, sleep = apply_fake_migration(
        [lock_not_available() for _ in range(3)]
    )

    assert isinstance(result, OperationalError)
    assert apply.call_count == 3
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2]


@pytest.mark.django_db
def test_lock_timeout_migration_does_not_retry_other_errors():
    result, apply, sleep = apply_fake_migration(
        [OperationalError("server closed the connection"), "state"]
    )

    assert isinstance(result, OperationalError)
    assert apply.call_count == 1
    sleep.assert_not_called()


@pytest.mark.django_db
def test_lock_timeout_migration_sets_the_lock_timeout_in_its_transaction():
    seen = []

    def apply(*args, **kwargs):
        with connection.cursor() as cursor:
            seen.append(get_lock_timeout(cursor))
        return "state"

    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL lock_timeout = 0")
    result, _, _ = apply_fake_migration(apply)

    assert result == "state"
    assert seen == ["2s"]
