from itertools import chain
from typing import List

from baserow.contrib.database.data_sync.data_sync_types import (
    PostgreSQLDataSyncType as BaserowPostgreSQLDataSyncType,
)
from baserow.contrib.database.data_sync.exceptions import SyncError
from baserow.contrib.database.data_sync.models import DataSync
from baserow.core.psycopg import psycopg, sql

from .baserow_table_data_sync import LocalBaserowTableDataSyncType  # noqa: F401
from .github_issues_data_sync import GitHubIssuesDataSyncType  # noqa: F401
from .gitlab_issues_data_sync import GitLabIssuesDataSyncType  # noqa: F401
from .hubspot_contacts_data_sync import HubspotContactsDataSyncType  # noqa: F401
from .jira_issues_data_sync import JiraIssuesDataSyncType  # noqa: F401
from .two_way_sync_strategy_types import RealtimePushTwoWaySyncStrategy


class PostgreSQLDataSyncType(BaserowPostgreSQLDataSyncType):
    """
    This class extends the existing PostgreSQL data sync type and adds two-way sync
    functionality to it.
    """

    two_way_sync_strategy_type = RealtimePushTwoWaySyncStrategy.type
    """
    Chosen to go with the realtime_push sync strategy because we can only push data in
    realtime to a PostgreSQL database. Unfortunately, we can't receive changes in
    realtime, so that still depends on the manual or periodic sync.
    """

    def _get_unique_primaries(self, properties):
        primaries = [p for p in properties if p.unique_primary]
        if not primaries:
            raise SyncError("No unique primary defined. Cannot safely proceed.")
        return primaries

    def _get_pk_tuple(self, row, unique_primaries):
        return tuple(row[p.field.db_column] for p in unique_primaries)

    def _execute_query_and_commit(self, query, params, data_sync, fetch_all=False):
        returning = None

        with self._connection(data_sync) as cursor:
            try:
                cursor.execute(query, params)
                if fetch_all:
                    returning = cursor.fetchall()
                cursor.connection.commit()
            except psycopg.Error as e:
                raise SyncError(f"Database error: {str(e)}")

        return returning

    def _filter_rows_without_unique_primary(self, serialized_rows, unique_primaries):
        # Filters out the rows that have an empty unique primary value. If the value is
        # empty, then the update can't be done reliably. A row could and up in that
        # state if the creation has gone wrong.
        return [
            row
            for row in serialized_rows
            if all(bool(row.get(p.field.db_column)) for p in unique_primaries)
        ]

    def create_rows(self, serialized_rows, data_sync: "DataSync") -> List[dict]:
        properties = data_sync.synced_properties.all()
        schema_name = data_sync.postgresql_schema
        table_name = data_sync.postgresql_table

        insert_columns = [p.key for p in properties if not p.unique_primary]
        return_columns = [p.key for p in properties if p.unique_primary]

        values = [
            [row.get(p.field.db_column) for p in properties if not p.unique_primary]
            for row in serialized_rows
        ]
        if not values:
            return

        insert_query = sql.SQL("INSERT INTO {}.{} ({}) VALUES {} RETURNING {}").format(
            sql.Identifier(schema_name),
            sql.Identifier(table_name),
            sql.SQL(", ").join(map(sql.Identifier, insert_columns)),
            sql.SQL(", ").join(
                sql.SQL("({})").format(
                    sql.SQL(", ").join(sql.Placeholder() for _ in insert_columns)
                )
                for _ in values
            ),
            sql.SQL(", ").join(map(sql.Identifier, return_columns)),
        )

        params = list(chain.from_iterable(values))
        returned = self._execute_query_and_commit(
            insert_query, params, data_sync, fetch_all=True
        )

        # Because the unique primary values could be generated on INSERT by the
        # PostgreSQL database, they must be updated in the Baserow table as well to
        # make sure that the correct identifier is set for future updates to the row.
        # The two-way sync strategy is responsible for making the actual update.
        return [
            {
                **dict(
                    zip(
                        [p.field.db_column for p in properties if p.unique_primary],
                        returned_row,
                    )
                ),
                "id": serialized_row["id"],
            }
            for returned_row, serialized_row in zip(returned, serialized_rows)
        ]

    def update_rows(self, serialized_rows, data_sync: "DataSync", updated_field_ids):
        properties = data_sync.synced_properties.all()
        table_name = data_sync.postgresql_table
        schema_name = data_sync.postgresql_schema

        unique_primaries = self._get_unique_primaries(properties)
        field_id_to_property = {p.field_id: p for p in properties}

        serialized_rows = self._filter_rows_without_unique_primary(
            serialized_rows, unique_primaries
        )

        if len(serialized_rows) == 0:
            return

        set_clauses = []
        params = []

        for field_id in updated_field_ids:
            prop = field_id_to_property.get(field_id)
            if not prop:
                continue

            cases = []
            for row in serialized_rows:
                if f"field_{field_id}" not in row:
                    continue

                pk_vals = self._get_pk_tuple(row, unique_primaries)
                value = row[f"field_{field_id}"]

                conditions = sql.SQL(" AND ").join(
                    sql.SQL("{} = {}").format(sql.Identifier(p.key), sql.Placeholder())
                    for p in unique_primaries
                )
                when_clause = sql.SQL(" WHEN {} THEN {}").format(
                    conditions, sql.Placeholder()
                )
                cases.append((when_clause, list(pk_vals) + [value]))

            if not cases:
                continue

            case_expr = sql.SQL("CASE")
            for when_sql, values in cases:
                case_expr += when_sql
                params.extend(values)
            case_expr += sql.SQL(" ELSE {} END").format(sql.Identifier(prop.key))

            set_clause = sql.SQL("{} = ").format(sql.Identifier(prop.key)) + case_expr
            set_clauses.append(set_clause)

        if not set_clauses:
            return

        # Collect all unique PK values for the WHERE clause
        pk_tuples = {
            self._get_pk_tuple(row, unique_primaries) for row in serialized_rows
        }
        pk_placeholders = [
            sql.SQL("({})").format(sql.SQL(", ").join(sql.Placeholder() for _ in pk))
            for pk in pk_tuples
        ]
        for pk in pk_tuples:
            params.extend(pk)

        where_clause = sql.SQL("({}) IN ({})").format(
            sql.SQL(", ").join(sql.Identifier(p.key) for p in unique_primaries),
            sql.SQL(", ").join(pk_placeholders),
        )

        update_query = sql.SQL("UPDATE {}.{} SET {} WHERE {}").format(
            sql.Identifier(schema_name),
            sql.Identifier(table_name),
            sql.SQL(", ").join(set_clauses),
            where_clause,
        )

        self._execute_query_and_commit(update_query, params, data_sync)

    def delete_rows(self, serialized_rows, data_sync: "DataSync"):
        properties = data_sync.synced_properties.all()
        table_name = data_sync.postgresql_table
        schema_name = data_sync.postgresql_schema

        unique_primaries = self._get_unique_primaries(properties)

        serialized_rows = self._filter_rows_without_unique_primary(
            serialized_rows, unique_primaries
        )

        # If there are no rows to delete, then there is no point is doing executing
        # the delete query.
        if len(serialized_rows) == 0:
            return

        pk_tuples = {
            self._get_pk_tuple(row, unique_primaries) for row in serialized_rows
        }
        if not pk_tuples:
            return

        where_clause = sql.SQL("({}) IN ({})").format(
            sql.SQL(", ").join(sql.Identifier(p.key) for p in unique_primaries),
            sql.SQL(", ").join(
                sql.SQL("({})").format(
                    sql.SQL(", ").join(sql.Placeholder() for _ in pk)
                )
                for pk in pk_tuples
            ),
        )

        delete_query = sql.SQL("DELETE FROM {}.{} WHERE {}").format(
            sql.Identifier(schema_name),
            sql.Identifier(table_name),
            where_clause,
        )

        params = [val for pk in pk_tuples for val in pk]

        self._execute_query_and_commit(delete_query, params, data_sync)
