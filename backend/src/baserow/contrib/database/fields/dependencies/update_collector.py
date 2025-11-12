import dataclasses
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, cast

from django.db.models import Expression, Q, Value

from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.models import Field, LinkRowField
from baserow.contrib.database.fields.signals import field_updated, fields_type_changed
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.table.constants import (
    ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME,
)
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.signals import table_updated

StartingRowIdsType = Optional[List[int]]


@dataclasses.dataclass
class DependencyContext:
    """
    DependencyContext is used to pass additional dependency-related information
    to callbacks.
    """

    # The depth of the dependency chain from the starting
    # field to the field parameter. 0 means the field is a direct dependency of
    # the updated row's field. 1 means the field depends on a field which depends
    # on the updated row's field, etc.
    depth: int = 0


class PathBasedUpdateStatementCollector:
    def __init__(
        self,
        table: Table,
        connection_here: Optional[LinkRowField],
        connection_is_broken: bool,
        update_changes_only: bool = False,
    ):
        """
        Collects updates statements for a particular table and then can execute them
        all at once. Can be connected to other collectors for other tables via a link
        row field.

        :param table: The table this collector is holding updates for.
        :param connection_here: The link row field that was used to connect this
            collector to its parent collector, if it has one.
        :param connection_is_broken: If True then this collector is for a table which
            has had its connection to the starting table broken, so all fields in the
            table need to be updated.
        :param update_changes_only: If True then only rows which have had their
            values changed will be updated, otherwise all rows will be updated.
        """

        self.update_statements: Dict[str, Expression] = {}
        self.table = table
        self.sub_paths: Dict[str, PathBasedUpdateStatementCollector] = {}
        self.connection_here: Optional[LinkRowField] = connection_here
        self.connection_is_broken = connection_is_broken
        self.update_changes_only = update_changes_only

    def add_update_statement(
        self,
        field: Field,
        update_statement: Expression,
        path_from_starting_table: Optional[List[LinkRowField]] = None,
    ):
        self._add_update_statement_or_mark_as_changed_for_field(
            field, update_statement, path_from_starting_table
        )

    def mark_field_as_changed(
        self,
        field: Field,
        path_from_starting_table: Optional[List[LinkRowField]] = None,
    ):
        self._add_update_statement_or_mark_as_changed_for_field(
            field, None, path_from_starting_table
        )

    def _add_update_statement_or_mark_as_changed_for_field(
        self,
        field: Field,
        update_statement: Optional[Expression],
        path_from_starting_table: Optional[List[LinkRowField]] = None,
    ):
        if not path_from_starting_table:
            if self.table != field.table:
                collector = self._get_collector_for_broken_connection(field)
                collector._add_update_statement_or_mark_as_changed_for_field(
                    field, update_statement, path_from_starting_table
                )
            else:
                if update_statement is not None:
                    # Value(None) is a valid update statement, but it doesn't work
                    # with the exclude method, so we need to convert it to None.
                    self.update_statements[field.db_column] = (
                        update_statement if update_statement != Value(None) else None
                    )
        else:
            next_via_field_link = path_from_starting_table[0]
            if next_via_field_link.link_row_table != self.table:
                # A link row field has been edited and this has been triggered by the
                # related link field that is being deleted, nothing to do as a separate
                # update will fix this column.
                return
            next_link_db_column = next_via_field_link.db_column
            if next_link_db_column not in self.sub_paths:
                self.sub_paths[next_link_db_column] = PathBasedUpdateStatementCollector(
                    next_via_field_link.table,
                    next_via_field_link,
                    connection_is_broken=self.connection_is_broken,
                )
            self.sub_paths[
                next_link_db_column
            ]._add_update_statement_or_mark_as_changed_for_field(
                field, update_statement, path_from_starting_table[1:]
            )

    def _get_collector_for_broken_connection(self, field):
        # We have been given an update statement for a different table, but
        # we don't have a path back to the starting table. This only occurs
        # when a link row field has been converted to another type, which will
        # have deleted the m2m connection entirely. In this situation we just
        # want to update all the cells of the dependant fields because they will
        # have all been affected by the deleted connection.
        broken_name = f"broken_connection_to_table_{field.table_id}"
        if broken_name not in self.sub_paths:
            collector = PathBasedUpdateStatementCollector(
                field.table, None, connection_is_broken=True
            )
            self.sub_paths[broken_name] = collector
        else:
            collector = self.sub_paths[broken_name]
        return collector

    def execute_all(
        self,
        field_cache: FieldCache,
        starting_row_ids: StartingRowIdsType = None,
        path_to_starting_table: StartingRowIdsType = None,
        deleted_m2m_rels_per_link_field: Optional[Dict[int, Set[int]]] = None,
        result: Optional[Dict[int, Set[int]]] = None,
    ) -> Dict[int, Set[int]]:
        """
        Executes all the pending update statements in the correct order and returns
        a dictionary containing a list of updated row ids per table id.

        :param field_cache: The field cache to use to get the models and fields.
        :param starting_row_ids: If the update starts from specific rows in the starting
            table set this and all update statements executed by this collector will
            only update rows which join back to these starting rows.
        :param path_to_starting_table: A list of link row fields which lead from the
            self.table to the table containing the starting row ids. Used to properly
            order the update statements so the graph is updated in sequence and also
            used if self.starting_row_ids is set so only rows which join back to the
            starting rows via this path are updated.
        :param deleted_m2m_rels_per_link_field: A dictionary per link field of rows in
            the table it links to which have had their connections removed. This is used
            to ensure that rows which have had their connections removed are still
            updated when the starting row ids are set.
        :param result: If the result dict containing the table and the updated rows
            already exists, then it can be provided here. If provided, it will be
            updated.
        :return: A dictionary containing a set of updated row ids per table id.
        """

        if result is None:
            result = defaultdict(set)

        path_to_starting_table = path_to_starting_table or []
        if self.connection_here is not None:
            path_to_starting_table = [self.connection_here] + path_to_starting_table
        updated_row_ids = self._execute_pending_update_statements(
            field_cache,
            path_to_starting_table,
            starting_row_ids,
            deleted_m2m_rels_per_link_field,
        )
        result[self.table.id].update(updated_row_ids)

        for sub_path in self.sub_paths.values():
            result = sub_path.execute_all(
                starting_row_ids=starting_row_ids,
                path_to_starting_table=path_to_starting_table,
                field_cache=field_cache,
                deleted_m2m_rels_per_link_field=deleted_m2m_rels_per_link_field,
                result=result,
            )
        return result

    def _execute_pending_update_statements(
        self,
        field_cache: FieldCache,
        path_to_starting_table: List[LinkRowField],
        starting_row_ids: StartingRowIdsType,
        deleted_m2m_rels_per_link_field: Optional[Dict[int, Set[int]]],
    ) -> list[int]:
        model = field_cache.get_model(self.table)
        qs = model.objects_and_trash
        # If the connection is broken back to the starting table then there is no
        # way to join back to these starting rows. So we just update all cells.
        if starting_row_ids is not None and not self.connection_is_broken:
            if len(path_to_starting_table) == 0:
                path_to_starting_table_id_column = "id"
            # If the path back to the starting table is a relationship pointing to the
            # same table, then the `starting_row_ids` are directly related to the same
            # table. We then can't go through the through table because the reversed
            # lookup would use the `to` starting row and not `from`. This causes rows
            # with a relation to another row to not be updated.
            elif (
                len(path_to_starting_table) == 1
                and path_to_starting_table[0].link_row_table_id == self.table.id
            ):
                path_to_starting_table_id_column = "id"
            else:
                path_to_starting_table_id_column = (
                    "__".join([p.db_column for p in path_to_starting_table]) + "__id"
                )
            path_to_starting_table_id_column += "__in"

            filter_for_rows_connected_to_starting_row = Q(
                **{path_to_starting_table_id_column: starting_row_ids}
            ) | self._include_rows_connected_to_deleted_m2m_relationships(
                deleted_m2m_rels_per_link_field,
                path_to_starting_table,
            )

            qs = qs.filter(filter_for_rows_connected_to_starting_row)
        if starting_row_ids is None:
            # We aren't updating individual rows but instead entire columns, so don't
            # set this per row attribute.
            self.update_statements.pop(ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME, None)

        updated_row_ids = []
        if self.update_statements:
            annotations, filters = {}, Q()

            # If we are only updating changes, we need to filter out rows that don't
            # need to be updated. Because of how postgres works, this could save a lot
            # of disk space and IO, at the cost of a more complex query and a longer
            # execution time, but if we're updating an entire field or only certain
            # rows, it's better to skip this optimization.
            if self.update_changes_only:
                for field, expr in self.update_statements.items():
                    if expr is None or not field.startswith("field_"):
                        continue

                    annotated_field = f"{field}_expr"
                    annotations[annotated_field] = expr
                    # Because the expression can evaluate to null and because of how the
                    # comparison with null should be handle in SQL
                    # (https://www.postgresql.org/docs/15/functions-comparison.html), we
                    # need to properly filter rows to correctly update only the ones
                    # that need to be updated.
                    filters |= Q(
                        **{
                            f"{field}__isnull": False,
                            f"{annotated_field}__isnull": True,
                        }
                    ) | ~Q(**{field: expr})

            updated_row_ids = (
                qs.annotate(**annotations)
                .filter(filters)
                .update_returning_ids(**self.update_statements)
            )
        return updated_row_ids

    def _include_rows_connected_to_deleted_m2m_relationships(
        self,
        deleted_m2m_rels_per_link_field: Dict[int, Set[int]],
        path_to_starting_table: List[LinkRowField],
    ):
        """
        If a row or batch of rows have been updated breaking their link row connections
        with other rows, we need to ensure that those other rows are still updated.
        We can't just join back to the starting row id as that m2m relation has been
        deleted by now. Instead the provided dict contains per link field which rows
        have had their connections deleted. This method then constructs a Q filter that
        ensures this UPDATE statement will also update those rows as they need to
        change their values because a connection has been removed for them.

        :return: A filter including any rows which previously were connected to the
            starting row.
        """

        if deleted_m2m_rels_per_link_field is None or not path_to_starting_table:
            return Q()

        # The first link row field in the path will be a link row field not in the
        # starting table, but which leads to the starting table. However the
        # deleted_m2m_rels_per_link_field is a dictionary per link field of rows in
        # the table it links to which have had their connections removed. Hence we
        # need to use the link row field in the starting table to lookup the deleted
        # row ids in the table after the starting table.
        link_row_field_in_starting_table: int = cast(
            int, path_to_starting_table[-1].link_row_related_field_id
        )
        filters = Q()
        if link_row_field_in_starting_table in deleted_m2m_rels_per_link_field:
            path_to_table_after_starting_table = "".join(
                [p.db_column + "__" for p in path_to_starting_table[:-1]]
            )

            row_ids = deleted_m2m_rels_per_link_field[link_row_field_in_starting_table]
            filter_kwargs_forcing_update_for_row_with_deleted_rels = {
                f"{path_to_table_after_starting_table}id__in": row_ids
            }
            filters |= Q(**filter_kwargs_forcing_update_for_row_with_deleted_rels)
        return filters


class FieldUpdatesTracker(defaultdict):
    """
    Utility class to track which fields have been updated and whether a field_updated
    signal should be sent for them.
    """

    def __init__(self):
        super().__init__(dict)

    def add_field(self, field: Field, send_field_updated_signal: bool = True):
        self[field.table][field] = send_field_updated_signal

    def tables(self):
        return self.keys()

    def fields(self, table):
        return self[table].keys()


class FieldUpdateCollector:
    """
    From a starting table this class collects updated fields and an update
    statements to re-calculate their cell values. Then can execute the cell update
    statements in the correct
    order and send field_updated signals informing the user about the updated fields.
    """

    def __init__(
        self,
        starting_table: Table,
        starting_row_ids: StartingRowIdsType = None,
        deleted_m2m_rels_per_link_field: Optional[Dict[int, Set[int]]] = None,
        update_changes_only: bool = False,
    ):
        """
        :param starting_table: The table where the triggering field update begins.
        :param starting_row_ids: If the update starts from specific rows in the starting
            table set this and all update statements executed by this collector will
            only update rows which join back to these starting rows.
        :param deleted_m2m_rels_per_link_field: A dictionary per link field of rows in
            the table it links to which have had their connections removed. This is used
            to ensure that rows which have had their connections removed are still
            updated when the starting row ids are set.
        :param update_changes_only: If True then only rows which have had their values
            changed will be updated, otherwise the update statement will update all the
            rows in the table. Because of how Postgres works, this could save a lot of
            disk space and IO, at the cost of a more complex query and a longer
            execution time.
        """

        # Track the fields which have been updated since last call to apply_updates
        self._pending_field_updates = FieldUpdatesTracker()
        # Track all fields which have been updated in this collector
        self._all_field_updates = FieldUpdatesTracker()

        self._starting_row_ids = starting_row_ids
        self._starting_table = starting_table
        self._deleted_m2m_rels_per_link_field = deleted_m2m_rels_per_link_field
        self.update_changes_only = update_changes_only

        self._update_statement_collector = self._init_update_statement_collector()

        # Keep a set of all the fields that have changed, and for which it's expected
        # the `ViewHandler::fields_type_changed` is called. That way, they can be
        # called combined, instead of one by one to save queries when many updated have
        # been made.
        self._fields_type_changed = set()

        # Keep a set of all the fields where the dependencies must be rebuild for. That
        # way, we can efficiently call the rebuild_dependencies method in bulk to reduce
        # the number of queries.
        self._rebuild_field_dependencies = set()

    def _init_update_statement_collector(self):
        return PathBasedUpdateStatementCollector(
            self._starting_table,
            connection_here=None,
            connection_is_broken=False,
            update_changes_only=self.update_changes_only,
        )

    def add_field_with_pending_update_statement(
        self,
        field: Field,
        update_statement: Expression,
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
    ):
        """
        Stores the provided field as an updated one to send in field updated signals
        when triggered to do so. Also stores the provided update statement to execute
        later when apply_updates is called.

        :param field: The field which has been updated.
        :param update_statement: The update statement to run over the fields row values
            to update them.
        :param via_path_to_starting_table: A list of link row fields which lead from
            the self.starting_table to the table containing field. Used to properly
            order the update statements so the graph is updated in sequence and also
            used if self.starting_row_ids is set so only rows which join back to the
            starting rows via this path are updated.
        """

        self._all_field_updates.add_field(field)
        self._pending_field_updates.add_field(field)

        self._update_statement_collector.add_update_statement(
            field, update_statement, via_path_to_starting_table
        )

    def add_field_which_has_changed(
        self,
        field: Field,
        via_path_to_starting_table: Optional[List[LinkRowField]] = None,
        send_field_updated_signal: bool = True,
    ):
        """
        Stores the provided field as an updated one to send in field updated signals
        when triggered to do so. Call this when you have no update statement to run
        for the field's cells, but they have still changed and so other cascading
        updates or background row tasks still need to be run for them

        :param field: The field which has had cell values changed.
        :param via_path_to_starting_table: A list of link row fields which lead from
            the self.starting_table to the table containing field. Used to properly
            order the update statements so the graph is updated in sequence and also
            used if self.starting_row_ids is set so only rows which join back to the
            starting rows via this path are updated.
        :param send_field_updated_signal: Whether to send a field_updated signal
            for this field at the end.
        """

        self._all_field_updates.add_field(field, send_field_updated_signal)

        self._update_statement_collector.mark_field_as_changed(
            field, via_path_to_starting_table
        )

    def apply_updates(self, field_cache: FieldCache) -> dict[int, list[int]]:
        """
        Triggers all update statements to be executed in the correct order in as few
        update queries as possible and return a dictionary containing a list of
        updated row ids per table id.
        """

        return self._update_statement_collector.execute_all(
            field_cache,
            self._starting_row_ids,
            deleted_m2m_rels_per_link_field=self._deleted_m2m_rels_per_link_field,
        )

    def apply_fields_type_changed(self, field_cache: FieldCache):
        if len(self._fields_type_changed) > 0:
            fields_type_changed.send(self, fields=list(self._fields_type_changed))
            self._fields_type_changed = set()

    def apply_rebuild_field_dependencies(self, field_cache: FieldCache):
        if len(self._rebuild_field_dependencies) > 0:
            from baserow.contrib.database.fields.dependencies.handler import (
                FieldDependencyHandler,
            )

            FieldDependencyHandler.rebuild_dependencies(
                list(self._rebuild_field_dependencies), field_cache
            )
            self._rebuild_field_dependencies = set()

    def apply_updates_and_get_updated_fields(
        self,
        field_cache: FieldCache,
        skip_search_updates=False,
        skip_fields_type_changed=False,
        skip_rebuild_field_dependencies=False,
    ) -> List[Field]:
        """
        Triggers all update statements to be executed in the correct order in as few
        update queries as possible.
        :return: The list of all fields which have been updated in the starting table.
        """

        updated_rows_per_table = self.apply_updates(field_cache)
        any_table_updated = any(
            len(updated_row_ids) > 0
            for updated_row_ids in updated_rows_per_table.values()
        )
        if any_table_updated and not skip_search_updates:
            for table in self._pending_field_updates.tables():
                row_ids = updated_rows_per_table.get(table.id)
                if not row_ids:
                    continue

                fields = self._get_updated_fields_in_table(table)
                SearchHandler.schedule_update_search_data(
                    table, fields=fields, row_ids=list(row_ids)
                )

        updated_fields = self._get_updated_fields_in_table(self._starting_table)

        # Reset the pending field updates so next time apply_updates is called it
        # will only send signals for the newly updated fields.
        self._pending_field_updates = FieldUpdatesTracker()
        self._update_statement_collector = self._init_update_statement_collector()

        if not skip_fields_type_changed:
            self.apply_fields_type_changed(field_cache)

        if not skip_rebuild_field_dependencies:
            self.apply_rebuild_field_dependencies(field_cache)

        return updated_fields

    def send_additional_field_updated_signals(self):
        """
        Sends field_updated signals for all fields which have been updated in tables
        which were not the self._starting_table. Will group together fields per table
        so only one signal is sent per table where the field_updated.field will be the
        first updated field encountered for that table and field_updated.related_fields
        will be all the other updated fields in that table.
        """

        for (
            field,
            related_fields,
        ) in self._get_updated_fields_to_send_signals_for_per_table():
            if field.table != self._starting_table:
                field_updated.send(
                    self,
                    field=field,
                    related_fields=related_fields,
                    user=None,
                )

    def send_force_refresh_signals_for_all_updated_tables(self):
        for table in self._all_field_updates.tables():
            table_updated.send(self, table=table, user=None, force_table_refresh=True)

    def _get_updated_fields_to_send_signals_for_per_table(
        self,
    ) -> List[Tuple[Field, List[Field]]]:
        result = []

        for table in self._all_field_updates.tables():
            fields = [
                field
                for field in self._all_field_updates.fields(table)
                if self._all_field_updates[table][field]
            ]
            if fields:
                result.append((fields[0], fields[1:]))
        return result

    def _get_updated_fields_in_table(self, table) -> List[Field]:
        return [field for field in self._pending_field_updates.fields(table)]

    def add_to_fields_type_changed(self, field: Field):
        self._fields_type_changed.add(field)

    def add_to_rebuild_field_dependencies(self, field: Field):
        self._rebuild_field_dependencies.add(field)
