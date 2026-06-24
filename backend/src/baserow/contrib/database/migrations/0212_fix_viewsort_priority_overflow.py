from django.db import migrations

MAX_ORDER_VALUE = 32767


def renumber_priorities(schema_editor, table_name):
    """
    Renumbers `priority` densely (1..N) per view, only for views with a row stuck at
    the smallint ceiling, preserving the current order (`priority, id`).
    """

    table = schema_editor.connection.ops.quote_name(table_name)

    schema_editor.execute(
        f"""
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY view_id ORDER BY priority, id
                ) AS new_priority
            FROM {table}
            WHERE view_id IN (
                SELECT view_id FROM {table} WHERE priority >= {MAX_ORDER_VALUE}
            )
        )
        UPDATE {table} AS t
        SET priority = ranked.new_priority
        FROM ranked
        WHERE t.id = ranked.id AND t.priority <> ranked.new_priority;
        """
    )


def fix_priority_overflow(apps, schema_editor):
    renumber_priorities(schema_editor, "database_viewsort")
    renumber_priorities(schema_editor, "database_viewgroupby")


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0211_viewsort_viewgroupby_priority"),
    ]

    operations = [
        migrations.RunPython(
            fix_priority_overflow,
            migrations.RunPython.noop,
        ),
    ]
