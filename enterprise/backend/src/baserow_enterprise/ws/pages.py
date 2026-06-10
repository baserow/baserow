from baserow.contrib.database.views.exceptions import ViewDoesNotExist
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.ws.pages import table_presence_space_name
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
    parameters = ["restricted_view_id", "table_id"]

    def can_add(self, user, web_socket_id, restricted_view_id, table_id=None, **kwargs):
        try:
            handler = ViewHandler()
            view = handler.get_view(restricted_view_id)

            if view.ownership_type != RestrictedViewOwnershipType.type:
                return False

            # table_id is optional for backward compatibility: older clients
            # that don't send it still get the data channel but skip presence.
            # When provided, validate it matches the view's actual table to
            # prevent presence space spoofing.
            if table_id is not None and table_id != view.table_id:
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

    def get_presence_space_name(self, table_id, **kwargs) -> str | None:
        return table_presence_space_name(table_id)

    def filter_focus_for_recipient(self, page_parameters, focus, focus_type) -> bool:
        # Full implementation in Part 2 (focus types) — will use
        # DatabaseFocusType.is_visible_for_view for shape-aware filtering.
        return True
