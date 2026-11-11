from functools import partial
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Set, Type

from django.db.models import (
    BooleanField,
    Case,
    Exists,
    Expression,
    OuterRef,
    Q,
    QuerySet,
    Value,
    When,
)

from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
)
from baserow.contrib.database.fields.dependencies.update_collector import (
    DependantRowsUpdate,
)
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.contrib.database.views.models import View, ViewFilter
from baserow.contrib.database.views.registries import view_type_registry
from baserow.contrib.database.views.row_checker import (
    FilteredViewRowChecker,
    FilteredViewRows,
    ViewHandler,
)
from baserow.contrib.database.ws.rows.messages import RealtimeRowMessages

from .registries import view_realtime_rows_registry


class ViewsRowsChanges(NamedTuple):
    """Per view, the rows an update made leave, enter or stay in the view."""

    deleted: List[FilteredViewRows]
    created: List[FilteredViewRows]
    updated: List[FilteredViewRows]


class DependantRowsViewChange(NamedTuple):
    """The rows a cascade made leave or enter a view, and the message telling it."""

    view: View
    rows: List[Dict[str, Any]]
    to_message: Callable[[List[Dict[str, Any]]], Dict[str, Any]]


def split_views_rows_changes(
    old_views_rows: List[FilteredViewRows],
    new_views_rows: List[FilteredViewRows],
) -> ViewsRowsChanges:
    """
    A client only holds the rows its view showed, so a row that left must be
    deleted, one that entered created, and only the rest updated.

    :param old_views_rows: Per view, the ids of the rows visible before.
    :param new_views_rows: Per view, the ids of the rows visible after.
    :return: Per view, the deleted, created and updated row ids, if any.
    """

    changes = ViewsRowsChanges(deleted=[], created=[], updated=[])

    def add_change(
        changed: List[FilteredViewRows], view: View, row_ids: Optional[Set[int]]
    ) -> None:
        if row_ids is FilteredViewRows.ALL_ROWS_ALLOWED or row_ids:
            changed.append(FilteredViewRows(view, row_ids))

    new_views_rows_by_view_id = {
        view_rows.view.id: view_rows for view_rows in new_views_rows
    }
    for view, old_row_ids in old_views_rows:
        new_view_rows = new_views_rows_by_view_id.pop(view.id, None)
        if new_view_rows is None:
            add_change(changes.deleted, view, old_row_ids)
            continue

        new_row_ids = new_view_rows.allowed_row_ids
        if (
            old_row_ids is FilteredViewRows.ALL_ROWS_ALLOWED
            and new_row_ids is FilteredViewRows.ALL_ROWS_ALLOWED
        ):
            add_change(changes.updated, view, FilteredViewRows.ALL_ROWS_ALLOWED)
            continue
        if old_row_ids is FilteredViewRows.ALL_ROWS_ALLOWED:
            old_row_ids = new_row_ids
        if new_row_ids is FilteredViewRows.ALL_ROWS_ALLOWED:
            new_row_ids = old_row_ids

        add_change(changes.deleted, view, old_row_ids - new_row_ids)
        add_change(changes.created, view, new_row_ids - old_row_ids)
        add_change(changes.updated, view, new_row_ids & old_row_ids)

    for view, new_row_ids in new_views_rows_by_view_id.values():
        add_change(changes.created, view, new_row_ids)
    return changes


class ViewRealtimeRowsHandler:
    def _is_name(self, name):
        return f"_is_{name}"

    def _get_views_filter(self) -> Q:
        """
        :return: The views any realtime rows type broadcasts to.
        """

        combined_q = Q()
        for t in view_realtime_rows_registry.get_all():
            combined_q |= t.get_views_filter()
        return combined_q

    def _get_views_annotated_with_types(self, table: Table) -> QuerySet:
        """
        Annotated with the types they match, which `broadcast_to_types` reads.

        :param table: The table of the views.
        :return: The views queryset.
        """

        return table.view_set.filter(self._get_views_filter()).annotate(
            **{
                self._is_name(t.type): Case(
                    When(t.get_views_filter(), then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                )
                for t in view_realtime_rows_registry.get_all()
            }
        )

    def _get_views_queryset(self, table: Table) -> QuerySet:
        """
        Prefetched to check rows against the views' filters.

        :param table: The table of the views.
        :return: The views queryset.
        """

        return (
            self._get_views_annotated_with_types(table)
            .select_related("table")
            .prefetch_related("viewfilter_set", "filter_groups", "table__field_set")
        )

    def get_views_row_checker(
        self,
        table: Table,
        model: GeneratedTableModel,
        only_include_views_which_want_realtime_events: bool,
        updated_field_ids: Optional[List[int]] = None,
    ) -> FilteredViewRowChecker:
        """
        Returns a FilteredViewRowChecker object which will have precalculated
        information about the public views in the provided table to aid with quickly
        checking which views a row in that table is visible in. If you will be updating
        the row and reusing the checker you must provide an iterable of the field ids
        that you will be updating in the row, otherwise the checker will cache the
        first check per view/row.

        :param table: The table the row is in.
        :param model: The model of the table including all fields.
        :param only_include_views_which_want_realtime_events: If True will only look
            for public views where
            ViewType.when_shared_publicly_requires_realtime_events is True.
        :param updated_field_ids: An optional iterable of field ids which will be
            updated on rows passed to the checker. If the checker is used on the same
            row multiple times and that row has been updated it will return invalid
            results unless you have correctly populated this argument.
        """

        return FilteredViewRowChecker(
            model,
            self._get_views_queryset(table),
            only_include_views_which_want_realtime_events,
            updated_field_ids,
        )

    def get_checked_views_row_checker(
        self, table: Table, model: Type[GeneratedTableModel]
    ) -> FilteredViewRowChecker:
        """
        Checked views are the filtered public and restricted views wanting
        realtime events; an unfiltered view shows every row, so needs no check.

        :param table: The table of the views.
        :param model: The table model with all fields.
        :return: The row checker.
        """

        views_queryset = self._get_views_queryset(table).filter(
            Exists(ViewFilter.objects.filter(view=OuterRef("pk")))
        )
        return FilteredViewRowChecker(
            model, views_queryset, only_include_views_which_want_realtime_events=True
        )

    def get_needs_view_checks_expression(
        self,
        table: Table,
        dependant_field_ids: Optional[Set[int]],
        field_ids_with_unknown_before_values: Set[int],
    ) -> Expression:
        """
        True when a checked view filters on a field the cascade updates, and on
        none with unknown before values. It doesn't depend on the row, so Postgres
        evaluates it once per statement.

        :param table: The table of the views.
        :param dependant_field_ids: The field ids the cascade updates; None
            counts every filtered view.
        :param field_ids_with_unknown_before_values: The field ids changed
            without an update statement.
        :return: The boolean expression.
        """

        if dependant_field_ids is not None and not dependant_field_ids:
            return Value(False, output_field=BooleanField())
        view_filters = ViewFilter.objects.filter(view=OuterRef("pk"))
        filters_on_dependant_fields = (
            view_filters
            if dependant_field_ids is None
            else view_filters.filter(field_id__in=dependant_field_ids)
        )
        views = View.objects.filter(
            self._get_views_filter(),
            Exists(filters_on_dependant_fields),
            table_id=table.id,
            filters_disabled=False,
        )
        if field_ids_with_unknown_before_values:
            views = views.exclude(
                Exists(
                    view_filters.filter(
                        field_id__in=field_ids_with_unknown_before_values
                    )
                )
            )
        return Exists(views)

    def broadcast_to_types(self, view: View, payload: Dict, user=None):
        """
        Helper method that broadcasts the provided payload using the ViewRealtimeRows
        type, if the view matches the filter.

        :param view: The view object where to broadcast the payload to.
        :param payload: The payload that must be broadcasted.
        :param user: The user that triggered the event. Passed through to the
            broadcast method so that the original sender can be excluded.
        """

        for t in view_realtime_rows_registry.get_all():
            if getattr(view, self._is_name(t.type), False):
                t.broadcast(view, payload, user=user)

    def broadcast_force_rows_refresh_to_views(self, table: Table) -> None:
        """
        Needed because the table refresh only reaches workspace members.

        :param table: The table with too many changed rows.
        :return: None.
        """

        for view in self._get_views_annotated_with_types(table):
            view_type = view_type_registry.get_by_model(view.specific_class)
            if not view_type.when_shared_publicly_requires_realtime_events:
                continue
            for t in view_realtime_rows_registry.get_all():
                if getattr(view, self._is_name(t.type), False):
                    t.broadcast_force_rows_refresh(view)

    def broadcast_dependant_rows_updated_to_views(
        self,
        table: Table,
        model: GeneratedTableModel,
        rows: List[GeneratedTableModel],
        serialized_rows: List[Dict[str, Any]],
        updated_field_ids: List[int],
    ) -> None:
        """
        Broadcasts a dependency cascade update to the publicly shared and
        restricted views of the table, so a row matching a view's filters when
        this runs gets a `rows_updated` event carrying only that view's visible
        fields.

        The before row is an id-only skeleton, so the client resolves the before
        state from its buffered copy (the mechanism from #5642). Rows entering or
        leaving a view are sent by `get_dependant_rows_visibility_changes`; a
        client ignores updates of rows it doesn't hold.

        :param table: The table the cascade-affected rows belong to.
        :param model: The model of the table including all fields.
        :param rows: The affected rows with their post-cascade values.
        :param serialized_rows: The serialized post-cascade rows, aligned with
            `rows`, restricted per view before broadcasting.
        :param updated_field_ids: The ids of the fields whose values changed.
        """

        row_checker = self.get_views_row_checker(
            table, model, only_include_views_which_want_realtime_events=True
        )
        views = row_checker.get_filtered_views_where_rows_are_visible(rows)
        if not views:
            return

        view_handler = ViewHandler()
        for view, visible_row_ids in views:
            visible_rows = view_handler.restrict_rows_for_view(
                view, serialized_rows, visible_row_ids
            )
            if not visible_rows:
                continue
            self.broadcast_to_types(
                view,
                RealtimeRowMessages.rows_updated(
                    table_id=table.id,
                    serialized_rows_before_update=[
                        {"id": row["id"]} for row in visible_rows
                    ],
                    serialized_rows=visible_rows,
                    metadata={},
                    updated_field_ids=updated_field_ids,
                ),
            )

    def get_dependant_rows_visibility_changes(
        self, update: DependantRowsUpdate
    ) -> List[DependantRowsViewChange]:
        """
        A `rows_deleted` for the rows that left a checked view, a `rows_created`
        for those that entered. Must run while the cascade still locks the rows,
        so the rows show only its changes.

        :param update: The transaction's merged update of the table.
        :return: Per view, the rows that left or entered it, in order.
        """

        known_row_ids = sorted(
            update.before_visible_view_ids.keys() & update.before_rows.keys()
        )
        row_checker = update.checked_views_row_checker
        if not update.before_checked_view_ids or not known_row_ids or not row_checker:
            return []

        table = update.table
        model = table.get_model()
        views_rows = row_checker.get_filtered_views_where_row_ids_are_visible(
            known_row_ids,
            include_views_without_visible_rows=True,
            excluded_filter_field_ids=update.field_ids_with_unknown_before_values,
        )
        changes = split_views_rows_changes(
            [
                FilteredViewRows(
                    view,
                    {
                        row_id
                        for row_id in known_row_ids
                        if view.id in update.before_visible_view_ids[row_id]
                    },
                )
                for view, _ in views_rows
            ],
            views_rows,
        )

        view_handler = ViewHandler()
        unknown_value_keys = {
            f"field_{field_id}"
            for field_id in update.field_ids_with_unknown_before_values
        }
        rows_before = [
            {
                key: value
                for key, value in update.before_rows[row_id].items()
                if key not in unknown_value_keys
            }
            for row_id in known_row_ids
        ]
        view_changes = [
            DependantRowsViewChange(
                view,
                view_handler.restrict_rows_for_view(view, rows_before, deleted_row_ids),
                partial(RealtimeRowMessages.rows_deleted, table.id),
            )
            for view, deleted_row_ids in changes.deleted
        ]

        entered_row_ids = set().union(*(row_ids for _, row_ids in changes.created))
        if not entered_row_ids:
            return view_changes
        entered_rows = model.objects.filter(id__in=entered_row_ids).enhance_by_fields()
        serialized_rows = get_row_serializer_class(
            model, RowSerializer, is_response=True
        )(entered_rows, many=True).data
        for view, created_row_ids in changes.created:
            created_rows = view_handler.restrict_rows_for_view(
                view, serialized_rows, created_row_ids
            )
            if created_rows:
                view_changes.append(
                    DependantRowsViewChange(
                        view,
                        created_rows,
                        partial(
                            RealtimeRowMessages.rows_created,
                            table.id,
                            metadata={},
                            before=None,
                        ),
                    )
                )
        return view_changes
