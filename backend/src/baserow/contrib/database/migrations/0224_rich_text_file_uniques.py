from django.db import connection, migrations


# Not a raw string on purpose: tests install these functions by reading the file
# as text and collapsing `\\` to `\` (see test_utils/setup_formulas.py), which
# mirrors Python's escape handling below. Keep every backslash doubled.
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
            ' ''!\\[[^\\[\\]\\\\]*(?:\\\\.[^\\[\\]\\\\]*)*\\]\\[([a-zA-Z0-9]+_[a-zA-Z0-9]+\\.[^\\]\\s/\\\\]+)\\]'', ''g''))[1], ''_'', 1),'
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
    EXCEPTION
        -- A table can legitimately be missing or lack a column while it is being
        -- created, trashed or snapshotted, so tolerate those quietly. Anything
        -- else is a bug: still return null so one bad table cannot abort the bulk
        -- usage job, but make it audible instead of reporting the table as using
        -- no files at all.
        WHEN undefined_table OR undefined_column THEN
            RAISE NOTICE 'Skipping file uniques for table %', table_id;
            RETURN null;
        WHEN OTHERS THEN
            RAISE WARNING
                'get_distinct_baserow_table_file_uniques failed for table %: % (%)',
                table_id, SQLERRM, SQLSTATE;
            RETURN null;
    END;
END;
$$
LANGUAGE plpgsql;
"""

# The function-creation header below is deliberately split across two adjacent
# string literals. test_utils/setup_formulas.py scrapes every function definition
# out of the migration files by regex and installs them in filename order, last
# wins. Written as one contiguous literal, this rollback body is scraped after
# UPDATED_DISTINCT_FILE_UNIQUES_FUNC and silently replaces the UNION version in
# every test database. Do not join these literals back together, and do not spell
# the full header out in a comment here either -- the scraper would match that too.
ORIGINAL_DISTINCT_FILE_UNIQUES_FUNC = (
    """
CREATE OR REPLACE """
    """FUNCTION get_distinct_baserow_table_file_uniques(table_id INT) RETURNS TEXT[] AS $$
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
)


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
        ("database", "0223_gridview_group_by_layout"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
