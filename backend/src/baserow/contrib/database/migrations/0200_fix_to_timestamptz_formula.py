from django.db import migrations

# The old function must be listed added first in the file because the
# `iter_formula_pgsql_functions` method extracts that one first. Added the new first
# second, makes sure that that version is executed last.
old_function = """
create or replace function try_cast_to_date_tz(
    p_in text,
    p_format text,
    p_timezone text
)
    returns timestamptz
as
$$
declare
        original_timezone text;
        tstamp timestamptz := null;
begin
    original_timezone := current_setting('TIMEZONE');
    begin
        PERFORM set_config('timezone', p_timezone, true /* local */) ;
        tstamp := to_timestamp(p_in, p_format);
    exception when others then
        null;
    end;
   PERFORM set_config('timezone', original_timezone, true /* local */);
   return tstamp;
end;
$$
    language plpgsql;
"""

new_function = """
create or replace function try_cast_to_date_tz(
    p_in text,
    p_format text,
    p_timezone text
)
returns timestamptz
as
$$
declare
    tstamp timestamp := null;
begin
    begin
        tstamp := to_timestamp(p_in, p_format);
        return (tstamp AT TIME ZONE p_timezone);
    exception when others then
        return null;
    end;
end;
$$
language plpgsql;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0199_field_rules"),
    ]

    operations = [
        migrations.RunSQL(
            new_function,
            # old function from
            # `src/baserow/contrib/database/migrations/0106_add_to_timestamptz_formula.py`
            old_function,
        )
    ]
