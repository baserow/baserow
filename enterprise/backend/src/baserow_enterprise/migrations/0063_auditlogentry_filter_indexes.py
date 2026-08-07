from django.db import migrations, models

TABLE = "baserow_enterprise_auditlogentry"

# In Postgres this index is always called `baserow_ent_action__8db5d6_idx`, the name
# migration 0011 created it with, while Django's migration state calls it
# `baserow_ent_action__ca13aa_idx`: migration 0016 renamed `group_id` to
# `workspace_id` in the state only and never renamed the index in the database, as
# its own comment records. The `RunSQL` below therefore drops a different name than
# the `RemoveIndex` it carries as its state operation.
OLD_INDEX_DB_NAME = "baserow_ent_action__8db5d6_idx"
OLD_INDEX_STATE_NAME = "baserow_ent_action__ca13aa_idx"


def is_unusable(cursor, name):
    """
    Whether an index exists but was left half-built, which is what an interrupted
    `CREATE INDEX CONCURRENTLY` produces.
    """

    cursor.execute(
        """
        SELECT 1
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        JOIN pg_class t ON t.oid = i.indrelid
        WHERE c.relname = %s AND t.relname = %s
          AND NOT (i.indisvalid AND i.indisready)
        """,
        [name, TABLE],
    )
    return cursor.fetchone() is not None


def add_index(name, fields, columns):
    def forwards(apps, schema_editor):
        with schema_editor.connection.cursor() as cursor:
            # An interrupted build leaves an unusable index behind that
            # `IF NOT EXISTS` would silently skip on the next attempt, leaving the
            # table paying to maintain an index no query can use. Clear it first so
            # a retried migration rebuilds it instead of stepping over it.
            if is_unusable(cursor, name):
                cursor.execute(f'DROP INDEX CONCURRENTLY "{name}"')

            cursor.execute(
                f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{name}" '
                f'ON "{TABLE}" ({columns})'
            )

    def backwards(apps, schema_editor):
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(f'DROP INDEX CONCURRENTLY IF EXISTS "{name}"')

    return migrations.SeparateDatabaseAndState(
        database_operations=[
            migrations.RunPython(forwards, backwards, atomic=False),
        ],
        state_operations=[
            migrations.AddIndex(
                model_name="auditlogentry",
                index=models.Index(fields=fields, name=name),
            )
        ],
    )


class Migration(migrations.Migration):
    # `CREATE INDEX CONCURRENTLY` cannot run inside a transaction. The audit log is
    # large enough on existing installations that a plain `CREATE INDEX` would block
    # inserts, and entries are written synchronously while users perform actions.
    atomic = False

    dependencies = [
        ("baserow_enterprise", "0062_core_xls_file_reader"),
    ]

    operations = [
        add_index(
            "auditlogentry_ts_idx",
            ["-action_timestamp"],
            '"action_timestamp" DESC',
        ),
        add_index(
            "auditlogentry_user_ts_idx",
            ["user_id", "-action_timestamp"],
            '"user_id", "action_timestamp" DESC',
        ),
        add_index(
            "auditlogentry_ws_ts_idx",
            ["workspace_id", "-action_timestamp"],
            '"workspace_id", "action_timestamp" DESC',
        ),
        add_index(
            "auditlogentry_type_ts_idx",
            ["action_type", "-action_timestamp"],
            '"action_type", "action_timestamp" DESC',
        ),
        # Dropped last so the listing is never left without an index to order by.
        # `IF EXISTS` also removes a half-dropped index, so this is safe to retry.
        migrations.RunSQL(
            sql=f'DROP INDEX CONCURRENTLY IF EXISTS "{OLD_INDEX_DB_NAME}"',
            reverse_sql=(
                f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{OLD_INDEX_DB_NAME}" '
                f'ON "{TABLE}" ("action_timestamp" DESC, "user_id", '
                f'"workspace_id", "action_type")'
            ),
            state_operations=[
                migrations.RemoveIndex(
                    model_name="auditlogentry",
                    name=OLD_INDEX_STATE_NAME,
                ),
            ],
        ),
    ]
