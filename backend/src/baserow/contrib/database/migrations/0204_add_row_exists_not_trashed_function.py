from django.db import migrations

forward_sql = """
CREATE OR REPLACE FUNCTION row_exists_not_trashed(p_table_id integer, p_row_id integer)
RETURNS boolean AS $$
DECLARE
    table_name text;
    result boolean;
BEGIN
    table_name := 'database_table_' || p_table_id;

    IF NOT EXISTS (
        SELECT 1 FROM pg_class WHERE relname = table_name AND relkind = 'r'
    ) THEN
        RETURN false;
    END IF;

    EXECUTE format(
        'SELECT EXISTS(SELECT 1 FROM %I WHERE id = $1 AND trashed = false)',
        table_name
    ) INTO result USING p_row_id;

    RETURN COALESCE(result, false);
END;
$$ LANGUAGE plpgsql;
"""

reverse_sql = """
DROP FUNCTION IF EXISTS row_exists_not_trashed(integer, integer);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0203_alter_field_field_dependencies"),
    ]

    operations = [
        migrations.RunSQL(forward_sql, reverse_sql),
    ]
