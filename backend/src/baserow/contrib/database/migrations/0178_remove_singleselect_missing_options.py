from django.db import ProgrammingError, connection, migrations, transaction

from psycopg2 import sql


def forward(apps, schema_editor):
    SelectOption = apps.get_model("database", "SelectOption")
    SingleSelectField = apps.get_model("database", "SingleSelectField")

    option_table_name = SelectOption.objects.model._meta.db_table

    for field in SingleSelectField.objects.all().order_by("id").iterator(chunk_size=50):
        table_name = f"database_table_{field.table_id}"
        try:
            with transaction.atomic():  # Start a new transaction for each query
                with connection.cursor() as cursor:
                    query = sql.SQL(
                        "UPDATE {table} SET {select_column} = NULL "
                        "WHERE {select_column} NOT IN "
                        "(SELECT id FROM {option_table})"
                    ).format(
                        table=sql.Identifier(table_name),
                        select_column=sql.Identifier(f"field_{field.id}"),
                        option_table=sql.Identifier(option_table_name)
                    )
                    cursor.execute(query)
        except ProgrammingError as e:
            error_string = str(e)
            if f'relation "{table_name}" does not exist' in error_string:
                print(f"Ignoring because table {table_name} does not exist in "
                      f"PostgreSQL.")
                continue
            raise e


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0177_airtableimportjob_skip_files"),
    ]

    operations = [
        # We disable transaction here to be able to manage it.
        migrations.RunPython(forward, migrations.RunPython.noop, atomic=False),
    ]
