from django.db import connection, migrations


RICH_TEXT_FILE_UNIQUES_FUNC = """
CREATE OR REPLACE FUNCTION _get_baserow_table_rich_text_file_uniques(table__id INT)
RETURNS TABLE(file_unique TEXT, field_id INT, table_id INT) AS $$
DECLARE
    field RECORD;
BEGIN
FOR field IN EXECUTE
    'SELECT df.id, df.table_id'
    ' FROM database_field df'
    ' JOIN database_longtextfield lt ON df.id = lt.field_ptr_id'
    ' WHERE df.trashed = false'
    ' AND lt.long_text_enable_rich_text = true'
    ' AND df.table_id = ' || table__id || ';'
LOOP
    BEGIN
        RETURN QUERY EXECUTE
            'SELECT SPLIT_PART((regexp_matches(field_' || field.id || ','
            ' ''!\[[^\[\]\\\\]*(?:\\\\.[^\[\]\\\\]*)*\]\[([a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\]\s]+)\]'', ''g''))[1], ''_'', 1),'
            ' ' || field.id || ', ' || field.table_id ||
            ' FROM database_table_' || field.table_id ||
            ' WHERE field_' || field.id || ' IS NOT NULL';
    EXCEPTION
        WHEN undefined_table THEN
            RAISE NOTICE 'Could not find database_table_%', field.table_id;
        WHEN undefined_column THEN
            RAISE NOTICE 'Could not find field_% in database_table_%', field.id, field.table_id;
    END;
END LOOP;
END;
$$
LANGUAGE plpgsql;
"""

UPDATED_DISTINCT_FILE_UNIQUES_FUNC = """
CREATE OR REPLACE FUNCTION get_distinct_baserow_table_file_uniques(table_id INT) RETURNS TEXT[] AS $$
DECLARE
    file_uniques TEXT[];
BEGIN
    BEGIN
        EXECUTE 'SELECT array_agg(distinct file_unique) FROM ('
            || 'SELECT file_unique FROM _get_baserow_table_file_uniques(' || table_id || ')'
            || ' UNION ALL'
            || ' SELECT file_unique FROM _get_baserow_table_rich_text_file_uniques(' || table_id || ')'
            || ') combined;'
        INTO file_uniques;
        RETURN file_uniques;
    EXCEPTION WHEN OTHERS THEN
        RETURN null;
    END;
END;
$$
LANGUAGE plpgsql;
"""

ORIGINAL_DISTINCT_FILE_UNIQUES_FUNC = """
CREATE OR REPLACE FUNCTION get_distinct_baserow_table_file_uniques(table_id INT) RETURNS TEXT[] AS $$
DECLARE
    file_uniques TEXT[];
BEGIN
    BEGIN
        EXECUTE 'SELECT array_agg(distinct file_unique) from _get_baserow_table_file_uniques(' || table_id || ');' into file_uniques;
        return file_uniques;
    EXCEPTION WHEN OTHERS THEN
        return null;
    END;
END;
$$
LANGUAGE plpgsql;
"""


def forward(apps, schema_editor):
    with connection.cursor() as cursor:
        cursor.execute(RICH_TEXT_FILE_UNIQUES_FUNC)
        cursor.execute(UPDATED_DISTINCT_FILE_UNIQUES_FUNC)


def reverse(apps, schema_editor):
    with connection.cursor() as cursor:
        cursor.execute("DROP FUNCTION IF EXISTS _get_baserow_table_rich_text_file_uniques(INT)")
        cursor.execute(ORIGINAL_DISTINCT_FILE_UNIQUES_FUNC)


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0216_databaseworkflowaction_createrowworkflowaction_and_more"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
