from django.db import migrations, models

TABLE = "baserow_enterprise_auditlogentry"
ACTOR_INDEX_NAME = "baserow_ent_actor_ts_idx"


def create_actor_index(apps, schema_editor):
    """Create the actor index, rebuilding an interrupted concurrent index."""

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indexrelid
            JOIN pg_class t ON t.oid = i.indrelid
            WHERE c.relname = %s AND t.relname = %s
              AND NOT (i.indisvalid AND i.indisready)
            """,
            [ACTOR_INDEX_NAME, TABLE],
        )
        if cursor.fetchone() is not None:
            cursor.execute(f'DROP INDEX CONCURRENTLY "{ACTOR_INDEX_NAME}"')

        cursor.execute(
            f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{ACTOR_INDEX_NAME}" '
            f'ON "{TABLE}" ("actor_type", "user_id", "action_timestamp" DESC)'
        )


def drop_actor_index(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f'DROP INDEX CONCURRENTLY IF EXISTS "{ACTOR_INDEX_NAME}"')


class Migration(migrations.Migration):
    # The actor index is created concurrently, so this migration cannot be wrapped
    # in one transaction. actor_id and actor_name only rename Django's model state;
    # their existing database columns are reused and require no data backfill.
    atomic = False

    dependencies = [
        ("baserow_enterprise", "0063_auditlogentry_filter_indexes"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveIndex(
                    model_name="auditlogentry",
                    name="auditlogentry_user_ts_idx",
                ),
                migrations.RenameField(
                    model_name="auditlogentry",
                    old_name="user_id",
                    new_name="actor_id",
                ),
                migrations.AlterField(
                    model_name="auditlogentry",
                    name="actor_id",
                    field=models.PositiveIntegerField(db_column="user_id", null=True),
                ),
                migrations.RenameField(
                    model_name="auditlogentry",
                    old_name="user_email",
                    new_name="actor_name",
                ),
                migrations.AlterField(
                    model_name="auditlogentry",
                    name="actor_name",
                    field=models.CharField(
                        blank=True,
                        db_column="user_email",
                        max_length=254,
                        null=True,
                    ),
                ),
                migrations.AddIndex(
                    model_name="auditlogentry",
                    index=models.Index(
                        fields=["actor_id", "-action_timestamp"],
                        name="auditlogentry_user_ts_idx",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="auditlogentry",
            name="actor_type",
            field=models.CharField(
                db_default="auth.User",
                max_length=255,
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameField(
                    model_name="auditlogexportjob",
                    old_name="filter_user_id",
                    new_name="filter_actor_id",
                ),
                migrations.AlterField(
                    model_name="auditlogexportjob",
                    name="filter_actor_id",
                    field=models.PositiveIntegerField(
                        db_column="filter_user_id",
                        help_text="Optional: The actor to filter the audit log by.",
                        null=True,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="auditlogexportjob",
            name="filter_actor_type",
            field=models.CharField(
                db_default="auth.User",
                help_text="Optional: The actor type to filter the audit log by.",
                max_length=255,
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    create_actor_index,
                    drop_actor_index,
                    atomic=False,
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="auditlogentry",
                    index=models.Index(
                        fields=["actor_type", "actor_id", "-action_timestamp"],
                        name="baserow_ent_actor_ts_idx",
                    ),
                )
            ],
        ),
    ]
