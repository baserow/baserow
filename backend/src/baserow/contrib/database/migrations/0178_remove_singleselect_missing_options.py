from django.db import ProgrammingError, connection, migrations, transaction
from django.db.models.expressions import F

from baserow.core.psycopg import sql


def forward(apps, schema_editor):
    SelectOption = apps.get_model("database", "SelectOption")
    SingleSelectField = apps.get_model("database", "SingleSelectField")

    option_table_name = SelectOption.objects.model._meta.db_table

    for field in SingleSelectField.objects.filter(
        updated_on__gt=F("created_on")
    ).order_by("id").iterator(chunk_size=50):
        table_name = f"database_table_{field.table_id}"
        select_column = f"field_{field.id}"
        try:
            with transaction.atomic():  # Start a new transaction for each query
                with connection.cursor() as cursor:
                    # First, check if there are records to update, so that we don't
                    # have to start and update query if not really needed.
                    pre_check_query = sql.SQL("""
                        SELECT EXISTS (
                            SELECT 1 FROM {table}
                            WHERE {select_column} IS NOT NULL
                            AND NOT EXISTS (
                                SELECT 1 FROM {option_table} opt
                                WHERE opt.id = {table}.{select_column}
                            )
                            LIMIT 1
                        )
                    """).format(
                        table=sql.Identifier(table_name),
                        select_column=sql.Identifier(select_column),
                        option_table=sql.Identifier(option_table_name)
                    )

                    cursor.execute(pre_check_query)
                    should_update = cursor.fetchone()[0]

                    if not should_update:
                        print(
                            f"Skipping update for {table_name}.{select_column} because "
                            f"no changes are needed."
                        )
                        continue

                    query = sql.SQL("""
                        UPDATE {table}
                        SET {select_column} = NULL
                        WHERE {select_column} IS NOT NULL
                        AND NOT EXISTS (
                            SELECT 1 FROM {option_table} opt
                            WHERE opt.id = {table}.{select_column}
                        )
                    """).format(
                        table=sql.Identifier(table_name),
                        select_column=sql.Identifier(select_column),
                        option_table=sql.Identifier(option_table_name)
                    )
                    cursor.execute(query)

                    print(f"Updated {table_name}.{select_column}")
        except ProgrammingError as e:
            error_string = str(e)
            if f'relation "{table_name}" does not exist' in error_string:
                print(f"Ignoring because table {table_name} does not exist in "
                      f"PostgreSQL.")
                continue
            raise e


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("database", "0177_airtableimportjob_skip_files"),
    ]

    operations = [
        # We disable transaction here to be able to manage it.
        migrations.RunPython(forward, migrations.RunPython.noop, atomic=False),
    ]
