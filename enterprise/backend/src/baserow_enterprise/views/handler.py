from baserow.contrib.database.views.row_checker import FilteredViewRowChecker
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType


class EnterpriseViewHandler:
    def get_restricted_views_row_checker(
        self,
        table,
        model,
        only_include_views_which_want_realtime_events,
        updated_field_ids=None,
    ) -> FilteredViewRowChecker:
        """
        Returns a FilteredViewRowChecker object which will have precalculated
        information about the restricted views in the provided table to aid with quickly
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
        :return: A list of non-specific public view instances.
        """

        queryset = (
            table.view_set.filter(ownership_type=RestrictedViewOwnershipType.type)
            .select_related("table")
            .prefetch_related("viewfilter_set", "filter_groups", "table__field_set")
            .all()
        )
        return FilteredViewRowChecker(
            model,
            queryset,
            only_include_views_which_want_realtime_events,
            updated_field_ids,
        )
