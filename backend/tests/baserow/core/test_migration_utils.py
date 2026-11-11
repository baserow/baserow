from unittest.mock import MagicMock, patch

from django.db import OperationalError, connection, migrations

import pytest

from baserow.core.migration_utils import LockTimeoutMigration, set_lock_timeout
from baserow.core.psycopg import errors


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
