from django.db.models import QuerySet

from baserow.contrib.dashboard.models import Dashboard
from baserow.core.telemetry.utils import baserow_trace_handler

from .exceptions import DashboardDoesNotExist


@baserow_trace_handler
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

    def get_dashboard_for_update(self, dashboard_id: int) -> Dashboard:
        """
        Get a dashboard by Id and lock its row for the rest of the transaction.

        :param dashboard_id: The Id of the dashboard to retrieve.
        :raises DashboardDoesNotExist: If the dashboard doesn't exist.
        :return: The locked model instance of the requested Dashboard.
        """

        return self.get_dashboard(
            dashboard_id,
            base_queryset=Dashboard.objects.select_for_update(of=("self",)),
        )

    def update_slug(self, dashboard: Dashboard, slug: str) -> Dashboard:
        """
        Replaces the slug used to address the dashboard publicly. Anyone holding a
        link with the old slug loses access.

        :param dashboard: The dashboard whose slug must be updated.
        :param slug: The new slug.
        :return: The updated dashboard.
        """

        dashboard.slug = slug
        dashboard.save()
        return dashboard
