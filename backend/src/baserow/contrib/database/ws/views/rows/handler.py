from typing import Dict, List, Optional

from django.db.models import BooleanField, Case, Q, Value, When

from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.row_checker import FilteredViewRowChecker

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

    def broadcast_to_types(self, view: View, payload: Dict):
        """
        Helper method that broadcasts the provided payload using the ViewRealtimeRows
        type, if the view matches the filter.

        :param view: The view object where to broadcast the payload to.
        :param payload: The payload that must be broadcasted.
        """

        for t in view_realtime_rows_registry.get_all():
            if getattr(view, self._is_name(t.type), False):
                t.broadcast(view, payload)
