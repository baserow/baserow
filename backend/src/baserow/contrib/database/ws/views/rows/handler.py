from typing import Any, Dict, List, Optional

from django.db.models import BooleanField, Case, Q, Value, When

from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.row_checker import (
    FilteredViewRowChecker,
    ViewHandler,
)
from baserow.contrib.database.ws.rows.messages import RealtimeRowMessages

from .registries import view_realtime_rows_registry


class ViewRealtimeRowsHandler:
    def _is_name(self, name):
        return f"_is_{name}"

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

        filters = {
            t.type: t.get_views_filter() for t in view_realtime_rows_registry.get_all()
        }
        combined_q = Q()
        for q in filters.values():
            combined_q |= q

        queryset = (
            table.view_set.filter(combined_q)
            .annotate(
                **{
                    self._is_name(name): Case(
                        When(q, then=Value(True)),
                        default=Value(False),
                        output_field=BooleanField(),
                    )
                    for name, q in filters.items()
                }
            )
            .select_related("table")
            .prefetch_related("viewfilter_set", "filter_groups", "table__field_set")
        )

        return FilteredViewRowChecker(
            model,
            queryset,
            only_include_views_which_want_realtime_events,
            updated_field_ids,
        )

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
        restricted views of the table, so a row still matching a view's filters
        gets a `rows_updated` event carrying only that view's visible fields.

        The before row is an id-only skeleton, so the client resolves the before
        state from its buffered copy (the mechanism from #5642). A row that a
        cascade pushes out of, or into, a filtered view is not reconciled here
        and settles on the next refresh (tracked in #5649): the pre-cascade
        visibility a delete or create would need can't be reconstructed after the
        cascade has run, and a public client has no filters to reject a row that
        no longer matches, so sending its new values (or a bare delete) would
        leak data or corrupt the client's row count.

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
