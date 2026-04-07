from django.db import ProgrammingError, connection, migrations, transaction

from baserow.core.psycopg import sql


def forward(apps, schema_editor):
    AutonumberField = apps.get_model("database", "AutonumberField")
    Field = apps.get_model("database", "Field")

    autonumber_field_ids = AutonumberField.objects.values_list(
        "field_ptr_id", flat=True
    )
    fields = (
        Field.objects.filter(id__in=autonumber_field_ids, trashed=False)
        .order_by("id")
        .iterator(chunk_size=100)
    )

    for field in fields:
        db_column = f"field_{field.id}"
        db_table = f"database_table_{field.table_id}"
        seq_name = f"{db_column}_seq"

        query = sql.SQL(
            "WITH seq_val AS (SELECT MAX({column}) AS max_val FROM {table}) "
            "SELECT setval({seq}, GREATEST(COALESCE(max_val, 0), 1), "
            "max_val IS NOT NULL) FROM seq_val"
        ).format(
            column=sql.Identifier(db_column),
            table=sql.Identifier(db_table),
            seq=sql.Literal(seq_name),
        )

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(query)
        except ProgrammingError as e:
            error_msg = str(e)
            if (
                f'relation "{db_table}" does not exist' in error_msg
                or "does not exist" in error_msg
            ):
                continue
            raise e


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("database", "0207_fix_data_sync_missing_primary_field"),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop, atomic=False),
    ]
