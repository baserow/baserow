import typing

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
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

    # we can exit early if the rule is somehow invalid

    table = TableHandler().get_table(table_id)
    fh = FieldRuleHandler(table, None)
    rule = fh.get_rule(rule_id)

    if not (rule.is_active and rule.is_valid):
        return

    rule: "DateDependency" = rule.specific
    model = table.get_model()
    try:
        row_count = table.usage.row_count
    except ObjectDoesNotExist:
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

    if above_row_count_limit:
        q = sql.SQL(
            """
            with src as
                     (select id, {duration_col_name} as before_duration_val
                      from {table_name}
                      where
                          {start_col_name} is not null
                        and {end_col_name} is not null
                        and ({duration_col_name} is null
                         or {duration_col_name} != make_interval(days =>{end_col_name} - {start_col_name})))
            update {table_name} t
            set {duration_col_name} = make_interval(days =>t.{end_col_name} - t.{start_col_name})
                from src
                where t.id = src.id
            """
        ).format(**params)

        with connection.cursor() as cursor:
            cursor.execute(q)
        table_updated.send(fh, table=table, user=fh.user, force_table_refresh=True)

    else:
        # this allows us to get old and new state in the same query
        q = sql.SQL(
            """
            with src as
                     (select id, {duration_col_name} as before_duration_val
                      from {table_name}
                      where
                          {start_col_name} is not null
                        and {end_col_name} is not null
                        and ({duration_col_name} is null
                         or {duration_col_name} != make_interval(days =>{end_col_name} - {start_col_name})))
            update {table_name} t
            set {duration_col_name} = make_interval(days =>t.{end_col_name} - t.{start_col_name})
                from src
                where t.id = src.id
                returning t.id
                , t.order
                , t.updated_on
                , src.before_duration_val
                , t.{duration_col_name}
            """
        ).format(**params)

        with connection.cursor() as cursor:
            cursor.execute(q)
            for r in cursor.fetchall():
                row_id, order, updated_on, before_duration_val, after_duration_val = r
                old_state = {duration_col_name: before_duration_val}
                new_state = {duration_col_name: after_duration_val}
                old_row = model(
                    id=row_id, order=order, updated_on=updated_on, **old_state
                )
                new_row = model(
                    id=row_id, order=order, updated_on=updated_on, **new_state
                )

                before_values.append(old_row)
                after_values.append(new_row)

        from baserow.contrib.database.ws.public.rows.signals import (
            public_before_rows_update,
        )
        from baserow.contrib.database.ws.rows.signals import serialize_rows_values

        before_return_values = {
            serialize_rows_values: serialize_rows_values(
                None,
                before_values,
                None,
                table,
                model,
                [rule.duration_field.id],
                use_fields_subset=True,
            ),
            public_before_rows_update: public_before_rows_update(
                None,
                before_values,
                None,
                table,
                model,
                [rule.duration_field.id],
            ),
        }

        rows_updated.send(
            rule_type,
            rows=after_values,
            user=None,
            table=table,
            model=model,
            #  sender, rows, user, table, model, updated_field_ids, **kwargs
            before_return=before_return_values,
            updated_field_ids=[rule.duration_field.id],
            m2m_change_tracker=None,
            send_realtime_update=True,
            send_webhook_events=True,
            fields=[rule.duration_field],
            dependant_fields=[],
            use_fields_subset=True,
        )
    SearchHandler.schedule_update_search_data(table, [rule.duration_field])
