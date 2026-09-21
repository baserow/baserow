from django.db import migrations, models

INDEX_NAME = "ent_ts_team_created_idx"
TABLE_NAME = "baserow_enterprise_teamsubject"


def is_unusable(cursor):
    """Return whether an interrupted concurrent build left an invalid index."""

    cursor.execute(
        """
        SELECT 1
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        JOIN pg_class t ON t.oid = i.indrelid
        WHERE c.relname = %s AND t.relname = %s
          AND NOT (i.indisvalid AND i.indisready)
        """,
        [INDEX_NAME, TABLE_NAME],
    )
    return cursor.fetchone() is not None


def add_index(apps, schema_editor):
    """Build a retry-safe index for each team's newest subject memberships."""

    with schema_editor.connection.cursor() as cursor:
        if is_unusable(cursor):
            cursor.execute(f'DROP INDEX CONCURRENTLY "{INDEX_NAME}"')
        cursor.execute(
            f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{INDEX_NAME}" '
            f'ON "{TABLE_NAME}" ("team_id", "created_on" DESC)'
        )


def remove_index(apps, schema_editor):
    """Remove the team subject sample index without blocking table writes."""

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f'DROP INDEX CONCURRENTLY IF EXISTS "{INDEX_NAME}"')


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("baserow_enterprise", "0065_remove_text_format_fields"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_index, remove_index, atomic=False),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="teamsubject",
                    index=models.Index(fields=["team", "-created_on"], name=INDEX_NAME),
                ),
            ],
        ),
    ]
