import typing

from django.conf import settings
from django.db import connection

from baserow.config.celery import app
from baserow.contrib.database.field_rules.handlers import FieldRuleHandler
from baserow.contrib.database.rows.signals import rows_updated
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.signals import table_updated
from baserow.core.psycopg import sql

if typing.TYPE_CHECKING:
    from .models import DateDependency


@app.task(queue="export")
def date_dependency_recalculate_rows(rule_id, table_id):
    """
    Runs table recalculation in the background for date dependency.
    """

    table = TableHandler().get_table(table_id)
    field_rules_handler = FieldRuleHandler(table)
    rule = field_rules_handler.get_rule(rule_id)

    if not (rule.is_active and rule.is_valid):
        return

    rule: "DateDependency" = rule.specific
    model = table.get_model()
    row_count = model.objects.all().count()

    # determine if it's a small or big table.
    above_row_count_limit = row_count > settings.FIELD_RULE_ROWS_LIMIT

    table_name = model._meta.db_table
    rule_type = rule.get_type()

    duration_col_name = rule.duration_field.db_column
    start_col_name = rule.start_date_field.db_column
    end_col_name = rule.end_date_field.db_column
    params = {
        "duration_col_name": sql.Identifier(duration_col_name),
        "start_col_name": sql.Identifier(start_col_name),
        "end_col_name": sql.Identifier(end_col_name),
        "table_name": sql.Identifier(table_name),
    }
    before_values = []
    after_values = []

    # This query will update duration for rows where duration can be calculated and
    # will be correct. Note, that there may be rows that can calculate duration, but
    # the value will be invalid (i.e. negative). This is covered by validation_query.
    #
    # Note: the formula to calculate duration is
    #
    #  duration = start_date + end_date + 1 day.
    #
    # see: .field_rule_types.DateCalculator.adjust_duration_after()
    # for details
    recalculation_query = sql.SQL(
        """WITH src AS
                     (SELECT id
                          , {duration_col_name} AS before_duration_val
                          , MAKE_INTERVAL(days =>({end_col_name} - {start_col_name} +1)) AS calculated
                      FROM {table_name}
                      WHERE
                          {start_col_name} IS NOT NULL
                        AND {end_col_name} IS NOT NULL
                        -- limit to rows that actually will change
                        AND ({duration_col_name} IS NULL
                        OR
                             {duration_col_name} != MAKE_INTERVAL(days =>{end_col_name} - {start_col_name} + 1))
                     )
            UPDATE {table_name} t
            SET {duration_col_name} = src.calculated
                FROM src
                WHERE t.id = src.id
                    AND src.calculated IS NOT NULL
                    AND src.calculated > make_interval(days=>0)
                {returning}"""
    )

    # After the update we need to validate rows for date dependency. The problem here
    # is that update set is different from valid/invalid set: some rows may not be
    # updated because they're missing start/end date columns, but they should be
    # considered invalid for this rule.
    validation_query = sql.SQL(
        """
    UPDATE {table_name}
        SET field_rules_are_valid = FALSE
    WHERE
        MAKE_INTERVAL(days =>{end_col_name} - {start_col_name} + 1) IS NULL
        OR MAKE_INTERVAL(days =>{end_col_name} - {start_col_name} + 1) < make_interval(days=>1)
    """
    ).format(**params)

    # in this case the table is apparently quite large, so the result may be
    # significant as well. We don't want to send millions of row updates, but we can
    # notify all sessions that the table changed as a whole.
    if above_row_count_limit:
        # no RETURNING clause
        params["returning"] = sql.SQL("")
        recalculation_query = recalculation_query.format(**params)

        with connection.cursor() as cursor:
            cursor.execute(recalculation_query)
            cursor.execute(validation_query)
        table_updated.send(
            field_rules_handler,
            table=table,
            user=field_rules_handler.user,
            force_table_refresh=True,
        )

    # the table is below the limit, so we want to return all affected rows.
    else:
        params["returning"] = sql.SQL(
            """RETURNING t.id
                , t.order
                , t.updated_on
                , src.before_duration_val
                , t.{duration_col_name}"""
        ).format(**params)

        recalculation_query = recalculation_query.format(**params)

        with connection.cursor() as cursor:
            cursor.execute(recalculation_query)
            # we iterate once over the result calculating before/after values
            for r in cursor.fetchall():
                row_id, order, updated_on, before_duration_val, after_duration_val = r
                old_state = {duration_col_name: before_duration_val}
                new_state = {duration_col_name: after_duration_val}

                # we can create some in-memory model instances, because we will send
                # updates limited to values in update query.
                old_row = model(
                    id=row_id, order=order, updated_on=updated_on, **old_state
                )
                new_row = model(
                    id=row_id, order=order, updated_on=updated_on, **new_state
                )

                before_values.append(old_row)
                after_values.append(new_row)
            cursor.execute(validation_query)
        from baserow.contrib.database.ws.rows.signals import serialize_rows_values
        from baserow.contrib.database.ws.views.rows.signals import (
            views_before_rows_update,
        )

        before_return_values = {
            serialize_rows_values: serialize_rows_values(
                None,
                before_values,
                None,
                table,
                model,
                [rule.duration_field.id],
                serialize_only_updated_fields=True,
            ),
            views_before_rows_update: views_before_rows_update(
                None,
                before_values,
                None,
                table,
                model,
                [rule.duration_field.id],
            ),
        }

        if after_values:
            rows_updated.send(
                rule_type,
                rows=after_values,
                user=None,
                table=table,
                model=model,
                before_return=before_return_values,
                updated_field_ids=[rule.duration_field.id],
                m2m_change_tracker=None,
                send_realtime_update=True,
                send_webhook_events=True,
                fields=[rule.duration_field],
                dependant_fields=[],
                serialize_only_updated_fields=True,
            )
    SearchHandler.schedule_update_search_data(table, [rule.duration_field])
