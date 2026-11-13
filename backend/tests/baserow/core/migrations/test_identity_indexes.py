from importlib import import_module

from django.db import OperationalError, connection
from django.db.migrations.loader import MigrationLoader

import pytest

from baserow.core.models import UserProfile
from baserow.core.psycopg import errors, psycopg


@pytest.mark.django_db(transaction=True)
def test_0136_can_retry_after_interrupted_concurrent_build(data_fixture):
    user = data_fixture.create_user()
    migration = import_module("baserow.core.migrations.0139_userprofile_trashed_idx")
    operation = migration.Migration.operations[0]
    before = MigrationLoader(connection).project_state(
        [("core", "0138_user_identities")]
    )
    after = before.clone()
    operation.state_forwards("core", after)
    blocker = psycopg.connect(**connection.get_connection_params())
    with connection.cursor() as cursor:
        cursor.execute("SHOW lock_timeout")
        original_timeout = cursor.fetchone()[0]
    try:
        with connection.cursor() as cursor:
            cursor.execute("DROP INDEX IF EXISTS core_profile_trashed_idx")
        with blocker.cursor() as cursor:
            cursor.execute(
                "UPDATE core_userprofile SET last_active = last_active "
                "WHERE user_id = %s",
                [user.id],
            )
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '250ms'")
        with pytest.raises(OperationalError) as interrupted:
            with connection.schema_editor(atomic=False) as editor:
                operation.database_forwards("core", editor, before, after)
        assert isinstance(interrupted.value.__cause__, errors.LockNotAvailable)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indisvalid, indisready FROM pg_index "
                "WHERE indexrelid = 'core_profile_trashed_idx'::regclass"
            )
            assert cursor.fetchone() == (False, False)
        blocker.rollback()
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = 0")

        with connection.schema_editor(atomic=False) as editor:
            operation.database_forwards("core", editor, before, after)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indisvalid, indisready, pg_get_expr(indpred, indrelid) "
                "FROM pg_index "
                "WHERE indexrelid = 'core_profile_trashed_idx'::regclass"
            )
            assert cursor.fetchone() == (True, True, "trashed")
    finally:
        blocker.rollback()
        blocker.close()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('lock_timeout', %s, false)", [original_timeout]
            )
            cursor.execute("DROP INDEX IF EXISTS core_profile_trashed_idx")
        with connection.schema_editor(atomic=False) as editor:
            editor.add_index(UserProfile, operation.index, concurrently=True)
