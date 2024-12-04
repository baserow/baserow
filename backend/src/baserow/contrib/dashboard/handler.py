from django.db.models import QuerySet

from baserow.contrib.dashboard.models import Dashboard

from .exceptions import DashboardDoesNotExist


class DashboardHandler:
    def get_dashboard(
        self, dashboard_id: int, base_queryset: QuerySet | None = None
    ) -> Dashboard:
        """
        Get a dashboard by Id.

        :param dashboard_id: The Id of the dashboard to retrieve.
        :param: base_queryset: Optional queryset to be used.
        :raises DashboardDoesNotExist: If the dashboard doesn't exist.
        :return: The model instance of the requested Dashboard.
        """

        if base_queryset is None:
            base_queryset = Dashboard.objects

        try:
            return base_queryset.select_related("workspace").get(id=dashboard_id)
        except Dashboard.DoesNotExist:
            raise DashboardDoesNotExist
