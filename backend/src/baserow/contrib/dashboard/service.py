from django.contrib.auth.models import AbstractUser

from baserow.contrib.dashboard.handler import DashboardHandler
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.dashboard.operations import UpdateDashboardSlugOperationType
from baserow.core.handler import CoreHandler
from baserow.core.signals import application_updated


class DashboardService:
    def __init__(self):
        self.handler = DashboardHandler()

    def rotate_slug(self, user: AbstractUser, dashboard_id: int) -> Dashboard:
        """
        Replaces the public slug of the dashboard with a freshly generated one.

        :param user: The user on whose behalf the slug is rotated.
        :param dashboard_id: The Id of the dashboard to update.
        :raises DashboardDoesNotExist: If the dashboard doesn't exist.
        :raises PermissionException: If the user can't update the slug.
        :return: The updated dashboard.
        """

        return self.update_slug(user, dashboard_id, Dashboard.create_new_slug())

    def update_slug(
        self, user: AbstractUser, dashboard_id: int, slug: str
    ) -> Dashboard:
        """
        Sets the public slug of the dashboard and notifies the workspace through
        the `application_updated` signal, so clients pick up the new link.

        :param user: The user on whose behalf the slug is updated.
        :param dashboard_id: The Id of the dashboard to update.
        :param slug: The new slug.
        :raises DashboardDoesNotExist: If the dashboard doesn't exist.
        :raises PermissionException: If the user can't update the slug.
        :return: The updated dashboard.
        """

        dashboard = self.handler.get_dashboard_for_update(dashboard_id)

        CoreHandler().check_permissions(
            user,
            UpdateDashboardSlugOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard,
        )

        dashboard = self.handler.update_slug(dashboard, slug)

        application_updated.send(self, application=dashboard, user=user)

        return dashboard
