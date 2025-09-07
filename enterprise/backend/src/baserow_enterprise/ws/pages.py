from baserow.contrib.database.views.exceptions import ViewDoesNotExist
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.exceptions import PermissionDenied, UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow.ws.registries import PageType
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType
from baserow_enterprise.views.operations import (
    ListenToAllRestrictedViewEventsOperationType,
)


class RestrictedViewPageType(PageType):
    """
    This page is specifically made for the restricted view ownership type. When the
    user opens the restricted view, and they don't have permissions to listen for all
    the table events, then they will use this page to receive real-time events.

    If a row is updated in the table, then it only broadcasts the updates if it
    matches the filter to make sure the user only receives data that it's supposed to
    see in the view.
    """

    type = "restricted_view"
    parameters = ["restricted_view_id"]

    def can_add(self, user, web_socket_id, restricted_view_id, **kwargs):
        try:
            handler = ViewHandler()
            view = handler.get_view(restricted_view_id)

            if view.ownership_type != RestrictedViewOwnershipType.type:
                return False

            # Check if the user has any permissions to access the view. If so,
            # we'll allow the user to listen for events.
            CoreHandler().check_permissions(
                user,
                ListenToAllRestrictedViewEventsOperationType.type,
                workspace=view.table.database.workspace,
                context=view,
            )
        except (UserNotInWorkspace, ViewDoesNotExist, PermissionDenied):
            return False

        return True

    def get_group_name(self, restricted_view_id, **kwargs):
        return f"restricted-view-{restricted_view_id}"

    def get_permission_channel_group_name(self, restricted_view_id, **kwargs):
        return f"permissions-restricted-view-{restricted_view_id}"
