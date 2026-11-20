from django.db import migrations

from baserow.core.psycopg import sql

VECTOR_TABLE_PATTERN = "^database_semantic_search_workspace_[0-9]+_data$"


def add_chunk_text_columns(schema_editor):
    """
    The vector tables are created per workspace when first needed, so Django
    doesn't know them. The columns are nullable, so adding them doesn't rewrite a
    table and the previous version can still write to it.
    """

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_name ~ %s
            """,
            [VECTOR_TABLE_PATTERN],
        )
        for (table_name,) in cursor.fetchall():
            cursor.execute(
                sql.SQL(
                    """
                    ALTER TABLE {table}
                    ADD COLUMN IF NOT EXISTS content text,
                    ADD COLUMN IF NOT EXISTS source text
                    """
                ).format(table=sql.Identifier(table_name))
            )


def queue_indexing_of_every_field(apps):
    """
    Existing chunks have no text. Every cell is indexed again, which the periodic
    check of pending search data starts.
    """

    SemanticSearchField = apps.get_model("baserow_enterprise", "SemanticSearchField")
    SemanticSearchPendingUpdate = apps.get_model(
        "baserow_enterprise", "SemanticSearchPendingUpdate"
    )
    semantic_search_fields = SemanticSearchField.objects.exclude(status="incompatible")
    field_ids = list(semantic_search_fields.values_list("field_id", flat=True))
    queued = SemanticSearchPendingUpdate.objects.filter(
        field_id__in=field_ids, row_id=None
    )
    queued_field_ids = set(queued.values_list("field_id", flat=True))
    queued.update(processed_until_row_id=None)
    SemanticSearchPendingUpdate.objects.bulk_create(
        [
            SemanticSearchPendingUpdate(field_id=field_id)
            for field_id in field_ids
            if field_id not in queued_field_ids
        ],
        batch_size=1000,
    )
    semantic_search_fields.update(status="indexing")


def forward(apps, schema_editor):
    add_chunk_text_columns(schema_editor)
    queue_indexing_of_every_field(apps)


class Migration(migrations.Migration):
    # Not atomic: each table is altered on its own, so no lock waits on the others.
    atomic = False

    dependencies = [
        ("baserow_enterprise", "0071_semantic_search_action"),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
