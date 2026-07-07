_try_cast_function_body = """(
        p_in text,
        p_default int default null
    )
        returns %(type)s
    as
    $FUNCTION$
    begin
        begin
            %(alter_column_prepare_old_value)s
            %(alter_column_prepare_new_value)s
            return p_in::%(type)s;
        exception when others then
            return p_default;
        end;
    end;
    $FUNCTION$
    language plpgsql;
"""

sql_drop_pg_temp_try_cast = "DROP FUNCTION IF EXISTS pg_temp.try_cast(text, int)"
sql_create_pg_temp_try_cast = (
    "create or replace function pg_temp.try_cast" + _try_cast_function_body
)

sql_drop_field_try_cast = "DROP FUNCTION IF EXISTS %(function_name)s(text, int)"
sql_create_field_try_cast = (
    "create or replace function %(function_name)s" + _try_cast_function_body
)
