from django.db.models import Q

from baserow.core.registries import Instance, Registry


class ViewRealtimeRowsType(Instance):
    """
    Registering a new `ViewRealtimeRowsType` can be used to efficiently broadcast a row
    related realtime event of the views matching the query. It will be query and
    performance efficient because the process doesn't have to be repeated N number of
    times.
    """

    def get_views_filter(self) -> Q:
        """
        Should return a Q object that is applied to the queryset to fetch the views
        related to the type within the table.

        :return: A Q object containing the filter to get the views related to this type.
        """

        raise NotImplementedError(
            "Must implement the `get_views_filter` for each `ViewRealtimeRowsType` "
            "instance."
        )

    def broadcast(self, view, payload):
        """
        Called when a payload must be broadcasted to a view. The code should look like:

        ```
        view_page_type = page_registry.get("view")
        view_page_type.broadcast(
            payload,
            ...{'kwarg_for_the_page', view.slug},
        )
        ```

        :param view: The view where to broadcast to.
        :param payload: The row created, updated, or deleted payload that must be
            broadcasted.
        """

        raise NotImplementedError(
            "Must implement the `broadcast` for each `ViewRealtimeRowsType` instance."
        )


class ViewRealtimeRowsRegistry(Registry):
    name = "view_realtime_rows"


view_realtime_rows_registry = ViewRealtimeRowsRegistry()
