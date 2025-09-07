from baserow.contrib.database.views.handler import CachingFilteredViewRowChecker
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType


class EnterpriseViewHandler:
    def get_restricted_views_row_checker(
        self,
        table,
        model,
        only_include_views_which_want_realtime_events,
        updated_field_ids=None,
    ):
        """
        @TODO docs
        """

        queryset = (
            table.view_set.filter(ownership_type=RestrictedViewOwnershipType.type)
            .prefetch_related("viewfilter_set", "filter_groups")
            .all()
        )
        return CachingFilteredViewRowChecker(
            model,
            queryset,
            only_include_views_which_want_realtime_events,
            updated_field_ids,
        )
