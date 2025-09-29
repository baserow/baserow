from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0199_field_rules"),
    ]

    operations = [
        migrations.RunSQL(
            (
                """
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
            ),
            # old function from
            # `src/baserow/contrib/database/migrations/0106_add_to_timestamptz_formula.py`
            (
                """
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
            ),
        )
    ]
