import time

from django.db import OperationalError, migrations, transaction

from baserow.core.psycopg import errors


def set_lock_timeout(cursor, lock_timeout: str):
    """
    Sets the lock timeout of the current transaction, unless the deployment set a
    stricter one.
    """

    cursor.execute(
        "SELECT set_config('lock_timeout', %s, true) WHERE "
        "current_setting('lock_timeout')::interval = interval '0' OR "
        "current_setting('lock_timeout')::interval > %s::interval",
        [lock_timeout, lock_timeout],
    )


class LockTimeoutMigration(migrations.Migration):
    """
    Applies its operations in one transaction with a short lock timeout, retried a
    few times, so that a long running transaction on a table it changes can't make
    every request touching that table wait behind the migration. The deferred
    foreign keys and indexes run in the same transaction, so they also respect the
    timeout.
    """

    atomic = False
    lock_timeout = "2s"
    lock_attempts = 10

    def apply(self, project_state, schema_editor, collect_sql=False):
        if collect_sql:
            return super().apply(project_state, schema_editor, collect_sql)

        connection = schema_editor.connection
        for attempt in range(1, self.lock_attempts + 1):
            try:
                with transaction.atomic(using=connection.alias):
                    with connection.cursor() as cursor:
                        set_lock_timeout(cursor, self.lock_timeout)
                    state = super().apply(project_state.clone(), schema_editor)
                    for sql in schema_editor.deferred_sql:
                        schema_editor.execute(sql)
                    schema_editor.deferred_sql = []
                    return state
            except OperationalError as exc:
                schema_editor.deferred_sql = []
                if (
                    not isinstance(exc.__cause__, errors.LockNotAvailable)
                    or attempt == self.lock_attempts
                ):
                    raise
                time.sleep(attempt)
