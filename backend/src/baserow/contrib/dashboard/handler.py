from dataclasses import dataclass
from typing import Any, Optional, Union

from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.db.models import QuerySet

from baserow.contrib.dashboard.models import Dashboard
from baserow.core.handler import CoreHandler
from baserow.core.operations import ReadApplicationOperationType
from baserow.core.public_sharing import (
    encode_public_access_token,
    is_public_access_token_valid,
)
from baserow.core.telemetry.utils import baserow_trace_handler
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import extract_allowed

from .exceptions import DashboardDoesNotExist, NoAuthorizationToPublicDashboard

# The fields that make up the public sharing state of a dashboard. The slug is
# left out on purpose, it can only be rotated.
DASHBOARD_SHARING_FIELDS = ["public", "public_password", "show_logo"]


@dataclass
class UpdatedDashboardSharing:
    """
    The outcome of `DashboardHandler.update_sharing`: the updated dashboard and
    the values of the provided sharing fields before and after the update.
    """

    dashboard: Dashboard
    original_values: dict[str, Any]
    new_values: dict[str, Any]


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

    def update_sharing(self, dashboard: Dashboard, **values) -> UpdatedDashboardSharing:
        """
        Updates the public sharing state of the dashboard. Only the
        `DASHBOARD_SHARING_FIELDS` are applied, any other value is ignored.

        :param dashboard: The dashboard whose sharing state must be updated.
        :param values: The new values. `public_password` must already be hashed
            with `Dashboard.make_password`, an empty string removes the password.
        :return: The updated dashboard with the original and the new values of
            the provided fields.
        """

        new_values = extract_allowed(values, DASHBOARD_SHARING_FIELDS)
        original_values = {key: getattr(dashboard, key) for key in new_values}

        for key, value in new_values.items():
            setattr(dashboard, key, value)
        dashboard.save()

        return UpdatedDashboardSharing(dashboard, original_values, new_values)

    def get_public_dashboard_by_slug(
        self,
        user: Union[AbstractUser, AnonymousUser],
        slug: str,
        authorization_token: Optional[str] = None,
        raise_authorization_error: bool = True,
    ) -> Dashboard:
        """
        Returns the dashboard with the provided slug if it is public, if the user
        can read it as a member of its workspace, or if a valid token is provided
        for a password protected dashboard. Mirrors how publicly shared views
        resolve their slug.

        :param user: The user on whose behalf the dashboard is requested, possibly
            anonymous.
        :param slug: The public slug of the dashboard.
        :param authorization_token: The token that grants access to a password
            protected dashboard when the user isn't a member of the workspace.
        :param raise_authorization_error: Whether a password protected dashboard
            raises when the token is missing or invalid.
        :raises DashboardDoesNotExist: If no dashboard has the slug, if it or its
            workspace is trashed, or if it isn't public and the user can't read it.
            The same error is used in all cases so that the slug never reveals
            whether a private dashboard exists.
        :raises NoAuthorizationToPublicDashboard: If the dashboard is password
            protected and the token is missing or invalid.
        :return: The requested dashboard.
        """

        try:
            dashboard = Dashboard.objects.select_related("workspace").get(slug=slug)
        except Dashboard.DoesNotExist as exc:
            raise DashboardDoesNotExist from exc

        if TrashHandler.item_has_a_trashed_parent(dashboard, check_item_also=True):
            raise DashboardDoesNotExist

        user_can_read_dashboard = user and CoreHandler().check_permissions(
            user,
            ReadApplicationOperationType.type,
            workspace=dashboard.workspace,
            context=dashboard,
            raise_permission_exceptions=False,
        )
        if not user_can_read_dashboard:
            if not dashboard.public:
                raise DashboardDoesNotExist

            token_is_valid = authorization_token and is_public_access_token_valid(
                dashboard.slug, dashboard.public_password, authorization_token
            )
            if (
                dashboard.public_has_password
                and not token_is_valid
                and raise_authorization_error
            ):
                raise NoAuthorizationToPublicDashboard

        return dashboard

    def encode_public_access_token(self, dashboard: Dashboard) -> str:
        """
        Creates the non-expiring token that grants access to the password
        protected public dashboard. Rotating the slug or changing the password
        invalidates it.

        :param dashboard: The password protected public dashboard.
        :return: The encoded token.
        """

        return encode_public_access_token(dashboard.slug, dashboard.public_password)
