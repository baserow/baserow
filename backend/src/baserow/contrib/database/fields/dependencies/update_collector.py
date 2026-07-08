import dataclasses
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, cast

from django.conf import settings
from django.db.models import Expression, Q, Value

from baserow.contrib.database.fields.dependencies.statement_builder import (
    execute_update_statements_returning_ids,
)
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.models import Field, LinkRowField
from baserow.contrib.database.fields.signals import field_updated, fields_type_changed
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.table.constants import (
    ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME,
)
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.signals import table_updated
from baserow.contrib.database.ws.realtime_listeners import (
    table_group_has_ws_subscribers,
)

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


@dataclasses.dataclass
class DependantRowsUpdate:
    """
    Rows of a table whose cell values changed as a consequence of a change in
    another (or the same) table, so that realtime updates can be sent for them.
    """

    table: Table
    # Empty when requires_refresh is True.
    row_ids: List[int]
    # The ids of the fields in this table whose values changed.
    field_ids: List[int]
    # True when the rows are unknown or over the limit: refresh the whole table.
    requires_refresh: bool
    # Serialized pre-cascade state for realtime updates. Empty if requires_refresh=True.
    before_rows: Dict[int, Dict[str, Any]] = dataclasses.field(default_factory=dict)


def merge_dependant_rows_updates(
    *updates_lists: List[DependantRowsUpdate],
) -> List[DependantRowsUpdate]:
    """
    Merges lists of DependantRowsUpdate into one entry per table, unioning
    row/field ids, respecting the limit and dropping empty entries.

    :param updates_lists: The lists of dependant rows updates to merge.
    :return: One update per table with sorted, deduplicated row and field ids.
    """

    limit = settings.DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT
    if limit <= 0:
        return []

    tables: Dict[int, Table] = {}
    row_ids_per_table: Dict[int, Set[int]] = defaultdict(set)
    field_ids_per_table: Dict[int, Set[int]] = defaultdict(set)
    before_rows_per_table: Dict[int, Dict[int, Dict[str, Any]]] = defaultdict(dict)
    tables_requiring_refresh: Set[int] = set()

    for updates in updates_lists:
        for update in updates:
            table_id = update.table.id
            tables[table_id] = update.table
            field_ids_per_table[table_id].update(update.field_ids)
            if table_id in tables_requiring_refresh:
                continue
            row_ids = row_ids_per_table[table_id]
            row_ids.update(update.row_ids)
            # Earliest snapshot wins.
            before_rows = before_rows_per_table[table_id]
            for row_id, serialized in update.before_rows.items():
                before_rows.setdefault(row_id, serialized)
            if update.requires_refresh or len(row_ids) > limit:
                # Past the limit only the refresh flag matters; free the ids.
                tables_requiring_refresh.add(table_id)
                row_ids.clear()
                before_rows.clear()

    return [
        DependantRowsUpdate(
            table=table,
            row_ids=sorted(row_ids_per_table[table_id]),
            field_ids=sorted(field_ids_per_table[table_id]),
            requires_refresh=table_id in tables_requiring_refresh,
            before_rows={
                row_id: before_rows_per_table[table_id][row_id]
                for row_id in row_ids_per_table[table_id]
                if row_id in before_rows_per_table[table_id]
            },
        )
        for table_id, table in tables.items()
        if row_ids_per_table[table_id] or table_id in tables_requiring_refresh
    ]


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
        self.changed_only_fields: List[Field] = []
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
                    self.changed_only_fields.append(field)
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
                    update_changes_only=self.update_changes_only,
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
                field.table,
                None,
                connection_is_broken=True,
                update_changes_only=self.update_changes_only,
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
        overflowed_table_ids: Optional[Set[int]] = None,
        collect_dependant_rows: bool = True,
        before_rows_result: Optional[Dict[int, Dict[int, Dict[str, Any]]]] = None,
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
        :param overflowed_table_ids: If provided, table ids whose changed rows could
            not be determined or exceeded the realtime update limit are added to it.
        :param collect_dependant_rows: Set to False when no realtime events will be
            sent for this update, to skip the extra queries needed to find the rows
            changed by fields marked as changed without an update statement.
        :return: A dictionary containing a set of updated row ids per table id.
        """

        if result is None:
            result = defaultdict(set)
        if overflowed_table_ids is None:
            overflowed_table_ids = set()
        if before_rows_result is None:
            before_rows_result = defaultdict(dict)

        path_to_starting_table = path_to_starting_table or []
        if self.connection_here is not None:
            path_to_starting_table = [self.connection_here] + path_to_starting_table

        if collect_dependant_rows:
            # Old cell values are gone once the update statements run.
            self._snapshot_before_rows(
                field_cache,
                path_to_starting_table,
                starting_row_ids,
                deleted_m2m_rels_per_link_field,
                before_rows_result,
            )

        updated_row_ids = self._execute_pending_update_statements(
            field_cache,
            path_to_starting_table,
            starting_row_ids,
            deleted_m2m_rels_per_link_field,
        )
        result[self.table.id].update(updated_row_ids)

        if collect_dependant_rows:
            self._collect_changed_only_row_ids(
                field_cache,
                path_to_starting_table,
                starting_row_ids,
                deleted_m2m_rels_per_link_field,
                result,
                overflowed_table_ids,
            )

        for sub_path in self.sub_paths.values():
            result = sub_path.execute_all(
                starting_row_ids=starting_row_ids,
                path_to_starting_table=path_to_starting_table,
                field_cache=field_cache,
                deleted_m2m_rels_per_link_field=deleted_m2m_rels_per_link_field,
                result=result,
                overflowed_table_ids=overflowed_table_ids,
                collect_dependant_rows=collect_dependant_rows,
                before_rows_result=before_rows_result,
            )
        return result

    def _snapshot_before_rows(
        self,
        field_cache: FieldCache,
        path_to_starting_table: List[LinkRowField],
        starting_row_ids: StartingRowIdsType,
        deleted_m2m_rels_per_link_field: Optional[Dict[int, Set[int]]],
        before_rows_result: Dict[int, Dict[int, Dict[str, Any]]],
    ) -> None:
        """
        Serializes the pre-update state of the rows this collector is about to
        update, so realtime listeners get a truthful `rows_before_update`.

        Only rows updated via a SQL statement are captured; a link row field
        display resolves at serialization time and its upstream value has already
        changed, so it keeps the skeleton and the client uses its buffered state.

        :param field_cache: The field cache to use to get the table model.
        :param path_to_starting_table: A list of link row fields which lead from
            self.table to the table containing the starting row ids.
        :param starting_row_ids: The ids of the rows in the starting table the
            update originated from.
        :param deleted_m2m_rels_per_link_field: A dictionary per link field of
            rows in the table it links to which have had their connections
            removed.
        :param before_rows_result: Output dict of serialized before rows per row
            id per table id, added to with the earliest snapshot winning.
        :return: None, the outcome is recorded in `before_rows_result`.
        """

        from baserow.contrib.database.api.rows.native_serializer import (
            get_light_fetchable_link_row_field_ids,
            native_serialize_rows,
        )

        limit = settings.DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT
        if limit <= 0 or not self.update_statements or self.connection_is_broken:
            # No SQL update, whole-column or broken connection: not an exact snapshot.
            return
        if starting_row_ids is None or not path_to_starting_table:
            # Starting rows and whole-column updates are broadcast elsewhere.
            return
        if not table_group_has_ws_subscribers(self.table.id):
            # The snapshot only feeds the websocket broadcast of this table's
            # dependant rows; without subscribers the broadcast falls back to
            # the already supported id-only skeletons.
            return

        model = field_cache.get_model(self.table)
        before = before_rows_result[self.table.id]
        light_link_field_ids = get_light_fetchable_link_row_field_ids(model)
        for row_filter in self._filters_for_rows_connected_to_starting_rows(
            path_to_starting_table,
            starting_row_ids,
            deleted_m2m_rels_per_link_field,
            include_starting_rows=False,
        ):
            # One past the limit is enough to detect the overflow that drops it.
            cap = limit + 1 - len(before)
            if cap <= 0:
                break
            queryset = model.objects.filter(row_filter)
            if before:
                # Rows snapshotted by an earlier statement are excluded in the
                # query, so their (potentially large) prefetches aren't
                # fetched again just to be thrown away.
                queryset = queryset.exclude(id__in=list(before.keys()))
            rows = list(
                queryset.enhance_by_fields(skip_field_ids=light_link_field_ids)
                .order_by()
                .distinct()[:cap]
            )
            for row, serialized in zip(rows, native_serialize_rows(model, rows)):
                before[row.id] = serialized

    def _collect_changed_only_row_ids(
        self,
        field_cache: FieldCache,
        path_to_starting_table: List[LinkRowField],
        starting_row_ids: StartingRowIdsType,
        deleted_m2m_rels_per_link_field: Optional[Dict[int, Set[int]]],
        result: Dict[int, Set[int]],
        overflowed_table_ids: Set[int],
    ) -> None:
        """
        Fields marked as changed without an update statement (e.g. link row
        fields resolve their values at serialization time) never appear in
        `update_returning_ids`, so their affected rows are found with a bounded
        SELECT joining back to the starting rows instead.

        :param field_cache: The field cache to use to get the table model.
        :param path_to_starting_table: A list of link row fields which lead from
            self.table to the table containing the starting row ids.
        :param starting_row_ids: The ids of the rows in the starting table the
            update originated from.
        :param deleted_m2m_rels_per_link_field: A dictionary per link field of
            rows in the table it links to which have had their connections
            removed.
        :param result: Output dictionary of updated row ids per table id, to
            which the found row ids are added.
        :param overflowed_table_ids: Output set to which the table id is added
            when the changed rows could not be determined or exceed the
            realtime update limit.
        :return: None, the outcome is recorded in `result` and
            `overflowed_table_ids`.
        """

        limit = settings.DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT
        if limit <= 0 or self.update_statements or not self.changed_only_fields:
            # The UPDATE already returned the ids of every row joining back.
            return
        if starting_row_ids is None or not path_to_starting_table:
            # Starting rows and whole-column updates are broadcast elsewhere.
            return
        if self.connection_is_broken:
            overflowed_table_ids.add(self.table.id)
            return

        model = field_cache.get_model(self.table)
        # The starting rows themselves are excluded from realtime updates, so
        # their filter half is skipped here entirely.
        filters = self._filters_for_rows_connected_to_starting_rows(
            path_to_starting_table,
            starting_row_ids,
            deleted_m2m_rels_per_link_field,
            include_starting_rows=False,
        )
        # The m2m join emits one row per relation, so distinct ids are requested
        # to keep duplicated relations from inflating the count. Fetching one id
        # past the limit is enough to detect an overflow, which falls back to a
        # table refresh.
        row_ids: Set[int] = set()
        for row_filter in filters:
            # Trashed rows need value updates but never realtime events.
            row_ids |= set(
                model.objects.filter(row_filter)
                .order_by()
                .distinct()
                .values_list("id", flat=True)[: limit + 1]
            )
            if len(row_ids) > limit:
                break
        if len(row_ids) > limit:
            overflowed_table_ids.add(self.table.id)
        else:
            result[self.table.id].update(row_ids)

    def _filters_for_rows_connected_to_starting_rows(
        self,
        path_to_starting_table: List[LinkRowField],
        starting_row_ids: List[int],
        deleted_m2m_rels_per_link_field: Optional[Dict[int, Set[int]]],
        include_starting_rows: bool = True,
    ) -> List[Q]:
        """
        Returns the filters matching every row affected by a change to the
        starting rows, one per statement. OR-ing a joined column with a base
        column defeats every index (full table + through-table scans), so each
        filter stays driveable by a single index instead.

        :param path_to_starting_table: A list of link row fields which lead from
            self.table to the table containing the starting row ids.
        :param starting_row_ids: The ids of the rows in the starting table the
            update originated from.
        :param deleted_m2m_rels_per_link_field: A dictionary per link field of
            rows in the table it links to which have had their connections
            removed, so rows which lost a connection still match.
        :param include_starting_rows: Whether the starting rows themselves must
            be matched by the returned filters.
        :return: A list of Q filters, each one to be used in its own statement.
        """

        if len(path_to_starting_table) == 0:
            return [Q(id__in=starting_row_ids)] if include_starting_rows else []

        m2m_column = (
            "__".join([p.db_column for p in path_to_starting_table]) + "__id__in"
        )
        filters = [Q(**{m2m_column: starting_row_ids})]
        if include_starting_rows and (
            len(path_to_starting_table) == 1
            and path_to_starting_table[0].link_row_table_id == self.table.id
        ):
            # A change via a self-link affects both the rows linking to the
            # starting rows and the starting rows themselves (their own cells
            # read through the link).
            filters.append(Q(id__in=starting_row_ids))
        deleted_q = self._include_rows_connected_to_deleted_m2m_relationships(
            deleted_m2m_rels_per_link_field,
            path_to_starting_table,
        )
        if deleted_q:
            filters.append(deleted_q)
        return filters

    def _execute_pending_update_statements(
        self,
        field_cache: FieldCache,
        path_to_starting_table: List[LinkRowField],
        starting_row_ids: StartingRowIdsType,
        deleted_m2m_rels_per_link_field: Optional[Dict[int, Set[int]]],
    ) -> list[int]:
        model = field_cache.get_model(self.table)
        base_queryset = model.objects_and_trash
        # If the connection is broken back to the starting table then there is no
        # way to join back to these starting rows. So we just update all cells.
        if starting_row_ids is not None and not self.connection_is_broken:
            querysets = [
                base_queryset.filter(row_filter)
                for row_filter in self._filters_for_rows_connected_to_starting_rows(
                    path_to_starting_table,
                    starting_row_ids,
                    deleted_m2m_rels_per_link_field,
                )
            ]
        else:
            # A None queryset updates the whole table.
            querysets = [None]
        if starting_row_ids is None:
            # We aren't updating individual rows but instead entire columns, so don't
            # set this per row attribute.
            self.update_statements.pop(ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME, None)

        # Recalculating a row twice is idempotent, so overlapping filters
        # (e.g. a starting row linking to another starting row) are fine.
        return execute_update_statements_returning_ids(
            model,
            self.update_statements,
            querysets,
            update_changes_only=self.update_changes_only,
        )

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
        row_ids = deleted_m2m_rels_per_link_field.get(link_row_field_in_starting_table)
        if row_ids:
            path_to_table_after_starting_table = "".join(
                [p.db_column + "__" for p in path_to_starting_table[:-1]]
            )

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
        collect_dependant_rows: bool = True,
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
        :param collect_dependant_rows: Set to False when no realtime events will
            be sent for this update, to skip the work of tracking the affected
            rows per table.
        """

        # Track the fields which have been updated since last call to apply_updates
        self._pending_field_updates = FieldUpdatesTracker()
        # Track all fields which have been updated in this collector
        self._all_field_updates = FieldUpdatesTracker()

        # Updated row ids per table across all apply_updates calls, bounded by
        # the realtime update limit; overflowing tables move to the other set.
        self._updated_rows_per_table: Dict[int, Set[int]] = defaultdict(set)
        self._overflowed_table_ids: Set[int] = set()

        # Serialized pre-cascade state per row id per table, captured before each
        # update statement runs and accumulated across apply_updates calls.
        self._before_rows_per_table: Dict[int, Dict[int, Dict[str, Any]]] = defaultdict(
            dict
        )

        self._starting_row_ids = starting_row_ids
        self._starting_table = starting_table
        self._deleted_m2m_rels_per_link_field = deleted_m2m_rels_per_link_field
        self.update_changes_only = update_changes_only
        self.collect_dependant_rows = collect_dependant_rows

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

    def apply_updates(self, field_cache: FieldCache) -> Dict[int, Set[int]]:
        """
        Triggers all update statements to be executed in the correct order in as few
        update queries as possible and return a dictionary containing a set of
        updated row ids per table id.
        """

        updated_rows_per_table = self._update_statement_collector.execute_all(
            field_cache,
            self._starting_row_ids,
            deleted_m2m_rels_per_link_field=self._deleted_m2m_rels_per_link_field,
            overflowed_table_ids=self._overflowed_table_ids,
            collect_dependant_rows=self.collect_dependant_rows,
            before_rows_result=self._before_rows_per_table,
        )
        self._accumulate_updated_rows(updated_rows_per_table)
        return updated_rows_per_table

    def _accumulate_updated_rows(
        self, updated_rows_per_table: Dict[int, Set[int]]
    ) -> None:
        """
        Accumulates the updated row ids per table across apply_updates calls,
        marking tables exceeding the realtime update limit as overflowed.

        :param updated_rows_per_table: The updated row ids per table id of the
            last apply_updates call.
        """

        limit = settings.DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT
        if limit <= 0 or not self.collect_dependant_rows:
            return
        for table_id, row_ids in updated_rows_per_table.items():
            if table_id in self._overflowed_table_ids:
                continue
            accumulated = self._updated_rows_per_table[table_id]
            accumulated.update(row_ids)
            if len(accumulated) > limit:
                # Past the limit only the refresh flag matters; free the ids.
                self._overflowed_table_ids.add(table_id)
                del self._updated_rows_per_table[table_id]

    def get_dependant_rows_updates(self) -> List[DependantRowsUpdate]:
        """
        Returns, per affected table, the rows whose values changed as a
        consequence of the applied updates, excluding the starting rows
        (already broadcast by the row signals). Empty when the limit is <= 0.

        :return: A list with one DependantRowsUpdate per affected table.
        """

        limit = settings.DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT
        if limit <= 0 or not self.collect_dependant_rows:
            return []

        starting_row_ids = set(self._starting_row_ids or [])
        updates = []
        for table in self._all_field_updates.tables():
            row_ids = self._updated_rows_per_table.get(table.id, set())
            if table.id == self._starting_table.id:
                row_ids = row_ids - starting_row_ids
            requires_refresh = table.id in self._overflowed_table_ids
            if not row_ids and not requires_refresh:
                continue
            table_before_rows = self._before_rows_per_table.get(table.id, {})
            updates.append(
                DependantRowsUpdate(
                    table=table,
                    row_ids=[] if requires_refresh else sorted(row_ids),
                    field_ids=[
                        field.id for field in self._all_field_updates.fields(table)
                    ],
                    requires_refresh=requires_refresh,
                    before_rows={}
                    if requires_refresh
                    else {
                        row_id: table_before_rows[row_id]
                        for row_id in row_ids
                        if row_id in table_before_rows
                    },
                )
            )
        return updates

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
                if len(row_ids) > settings.SEARCH_UPDATE_ROW_IDS_LIMIT:
                    # Serializing huge id lists into the task queue is worse
                    # than rebuilding the whole fields.
                    SearchHandler.schedule_update_search_data(table, fields=fields)
                else:
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
