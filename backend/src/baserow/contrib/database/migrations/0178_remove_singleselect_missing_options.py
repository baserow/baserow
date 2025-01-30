from django.db import connection, migrations, transaction

from psycopg2 import sql


def forward(apps, schema_editor):
    batch_size = 50
    SelectOption = apps.get_model("database", "SelectOption")
    SingleSelectField = apps.get_model("database", "SingleSelectField")

    option_table_name = SelectOption.objects.model._meta.db_table
    total = SingleSelectField.objects.count()

    for start in range(0, total, batch_size):
        with transaction.atomic():
            for field in SingleSelectField.objects.all()[start : start + batch_size]:
                with connection.cursor() as cursor:
                    query = sql.SQL(
                        "UPDATE {table} SET {select_column} = NULL "
                        "WHERE {select_column} NOT IN "
                        "(SELECT id FROM {option_table})"
                    ).format(
                        table=sql.Identifier(f"database_table_{field.table.id}"),
                        select_column=sql.Identifier(f"field_{field.id}"),
                        option_table=sql.Identifier(option_table_name)
                    )
                    cursor.execute(query)


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0177_airtableimportjob_skip_files"),
    ]

    operations = [
        # We disable transaction here to be able to manage it.
        migrations.RunPython(forward, migrations.RunPython.noop, atomic=False),
    ]
