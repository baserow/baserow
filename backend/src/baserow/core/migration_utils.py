import time

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import OperationalError, migrations, transaction

from baserow.core.psycopg import errors, sql


class RetryableAddIndexConcurrently(AddIndexConcurrently):
    """
    Add an index concurrently, recovering when a migration is rerun after failure.

    PostgreSQL can leave an invalid index after an interrupted concurrent build.
    Drop that index concurrently before rebuilding; retain a valid, ready index
    when the build succeeded but the migration was not recorded. Reversing is also
    safe to repeat. Like Django migrations, this assumes one migration runner and
    an immutable index definition/name. Errors propagate for the next deploy to retry.

    Requires a non-atomic migration. SQL collection emits ordinary concurrent DDL;
    recovery requires live catalog inspection and only runs during migration execution.
    """

    def _existing_index(self, schema_editor, model):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT ns.nspname, idx.relname,
                       info.indisvalid AND info.indisready,
                       info.indrelid = tbl.oid
                FROM pg_class tbl
                JOIN pg_class idx ON idx.relnamespace = tbl.relnamespace
                    AND idx.relname = %s
                JOIN pg_namespace ns ON ns.oid = idx.relnamespace
                LEFT JOIN pg_index info ON info.indexrelid = idx.oid
                WHERE tbl.oid = to_regclass(%s)
                """,
                [self.index.name, schema_editor.quote_name(model._meta.db_table)],
            )
            existing = cursor.fetchone()
        if existing is None:
            return None
        schema, name, valid, belongs_to_table = existing
        if not belongs_to_table:
            raise ValueError(
                f"Cannot recover index {schema}.{name}: the existing relation is "
                f"not an index on {model._meta.db_table}."
            )
        qualified_name = sql.Identifier(schema, name).as_string(
            schema_editor.connection.connection
        )
        return qualified_name, valid

    def _drop_index(self, schema_editor, qualified_name):
        schema_editor.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {qualified_name}")

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.collect_sql:
            return super().database_forwards(
                app_label, schema_editor, from_state, to_state
            )
        self._ensure_not_in_transaction(schema_editor)
        model = to_state.apps.get_model(app_label, self.model_name)
        if not self.allow_migrate_model(schema_editor.connection.alias, model):
            return
        existing = self._existing_index(schema_editor, model)
        if existing is not None:
            name, valid = existing
            if valid:
                return
            self._drop_index(schema_editor, name)
        schema_editor.add_index(model, self.index, concurrently=True)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.collect_sql:
            return super().database_backwards(
                app_label, schema_editor, from_state, to_state
            )
        self._ensure_not_in_transaction(schema_editor)
        model = from_state.apps.get_model(app_label, self.model_name)
        if not self.allow_migrate_model(schema_editor.connection.alias, model):
            return
        existing = self._existing_index(schema_editor, model)
        if existing is not None:
            self._drop_index(schema_editor, existing[0])


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
