from django.db import migrations, models
from django.db.models import Q

TABLE = "database_view"
INDEX_NAME = "database_view_public_id_idx"


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


def forwards(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        # An interrupted build leaves an unusable index behind that `IF NOT EXISTS`
        # would silently skip on the next attempt, leaving the table paying to
        # maintain an index no query can use. Clear it first so a retried migration
        # rebuilds it instead of stepping over it.
        if is_unusable(cursor, INDEX_NAME):
            cursor.execute(f'DROP INDEX CONCURRENTLY "{INDEX_NAME}"')

        cursor.execute(
            f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{INDEX_NAME}" '
            f'ON "{TABLE}" ("id" DESC) INCLUDE ("table_id") '
            f'WHERE "public" AND NOT "trashed"'
        )


def backwards(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f'DROP INDEX CONCURRENTLY IF EXISTS "{INDEX_NAME}"')


class Migration(migrations.Migration):
    # `CREATE INDEX CONCURRENTLY` cannot run inside a transaction. There is a view for
    # roughly every table on an existing installation, and a view is written whenever
    # someone changes one, so a plain `CREATE INDEX` would block those writes.
    atomic = False

    dependencies = [
        ("database", "0214_buttonfield"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(forwards, backwards, atomic=False),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="view",
                    index=models.Index(
                        fields=["-id"],
                        include=["table_id"],
                        condition=Q(public=True, trashed=False),
                        name=INDEX_NAME,
                    ),
                ),
            ],
        ),
    ]
