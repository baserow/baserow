import secrets

_try_cast_function_body = """(
        p_in text,
        p_default int default null
    )
        returns %(type)s
    as
    %(fence)s
    begin
        begin
            %(alter_column_prepare_old_value)s
            %(alter_column_prepare_new_value)s
            return p_in::%(type)s;
        exception when others then
            return p_default;
        end;
    end;
    %(fence)s
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


def generate_try_cast_dollar_tag(values=()):
    """
    Returns a random dollar-quote tag (e.g. `$baserow_ab12...$`) used to delimit the
    body of the generated `try_cast` function.

    The function body embeds user-controlled values, such as select option values. A
    fixed tag would let such a value contain the closing tag itself and break out of
    the dollar-quoted body, turning the remainder of the value into executable SQL.
    Single-quote escaping by the database driver does not help because single quotes
    have no special meaning inside a dollar-quoted body. The tag is therefore random
    and unguessable, and is additionally verified not to occur in any of the provided
    values so it can never be reproduced by the stored data. This mirrors how pg_dump
    chooses a dollar-quote tag when it quotes data.

    :param values: The values that will be embedded in the dollar-quoted body. The
        returned tag is guaranteed not to appear in any of them.
    :return: A dollar-quote tag that is safe to use as the body delimiter.
    """

    while True:
        tag = f"$baserow_{secrets.token_hex(16)}$"
        if all(tag not in str(value) for value in values):
            return tag
