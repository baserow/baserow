from typing import Any

from django.conf import settings
from django.contrib.auth.models import AnonymousUser

from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.operations import (
    ListenToAllDatabaseTableEventsOperationType,
)
from baserow.contrib.database.views.exceptions import (
    NoAuthorizationToPubliclySharedView,
    ViewDoesNotExist,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.exceptions import PermissionDenied, UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow.ws.registries import PageType, PresenceFocusType


class TablePageType(PageType):
    type = "table"
    parameters = ["table_id"]

    def can_add(self, user, web_socket_id, table_id, **kwargs):
        """
        The user should only have access to this page if the table exists and if they
        have access to the table.
        """

        if not table_id:
            return False

        try:
            handler = TableHandler()
            table = handler.get_table(table_id)
            CoreHandler().check_permissions(
                user,
                ListenToAllDatabaseTableEventsOperationType.type,
                workspace=table.database.workspace,
                context=table,
            )
        except (UserNotInWorkspace, TableDoesNotExist, PermissionDenied):
            return False

        return True

    def get_group_name(self, table_id, **kwargs):
        return f"table-{table_id}"

    def get_permission_channel_group_name(self, table_id, **kwargs):
        return f"permissions-table-{table_id}"

    def get_presence_space_name(self, table_id: int | None, **kwargs) -> str | None:
        """All table subscribers share one presence space per table."""

        return table_presence_space_name(table_id)

    def filter_focus_for_recipient(
        self,
        page_parameters: dict[str, Any],
        focus: dict[str, Any] | None,
        focus_type: PresenceFocusType | None,
    ) -> bool:
        # Table subscribers already have full row/field visibility; no filtering needed.
        return True


def table_presence_space_name(table_id: int) -> str | None:
    """
    Return the canonical presence space name for a table.

    :param table_id: The database table id.
    :return: The space name string, or None if table_id is falsy.
    """

    if table_id is None or table_id <= 0:
        return None
    return f"table-{table_id}"


class PublicViewPageType(PageType):
    type = "view"
    parameters = ["slug", "token"]

    def get_presence_space_name(self, slug=None, token=None, **kwargs) -> str | None:
        if not slug:
            return None
        try:
            view = ViewHandler().get_public_view_by_slug(
                AnonymousUser(), slug, authorization_token=token
            )
        except (ViewDoesNotExist, NoAuthorizationToPubliclySharedView):
            return None
        return table_presence_space_name(view.table_id)

    def filter_focus_for_recipient(self, page_parameters, focus, focus_type) -> bool:
        return False

    def can_add(self, user, web_socket_id, slug, token=None, **kwargs):
        """
        The user should only have access to this page if the view exists and:
        - the user have access to the workspace
        - the view is public and not password protected
        - the view is public, password protected and the token provided is valid.
        """

        if settings.DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS:
            return False

        if not slug:
            return False

        try:
            handler = ViewHandler()
            view = handler.get_public_view_by_slug(
                user, slug, authorization_token=token
            )
        except (ViewDoesNotExist, NoAuthorizationToPubliclySharedView):
            return False

        view_type = view_type_registry.get_by_model(view.specific_class)
        if not view_type.when_shared_publicly_requires_realtime_events:
            return False

        return True

    def get_group_name(self, slug, **kwargs):
        return f"view-{slug}"


class RowPageType(PageType):
    type = "row"
    parameters = ["table_id", "row_id"]

    def can_add(self, user, web_socket_id, table_id, row_id, **kwargs):
        """
        The user should only have access to this page if the table and row exist
        and if he has access to the table.
        """

        if not table_id:
            return False

        try:
            handler = TableHandler()
            table = handler.get_table(table_id)
            CoreHandler().check_permissions(
                user,
                ListenToAllDatabaseTableEventsOperationType.type,
                workspace=table.database.workspace,
                context=table,
            )
            row_handler = RowHandler()
            row_handler.get_row(user, table, row_id)
        except (
            UserNotInWorkspace,
            TableDoesNotExist,
            PermissionDenied,
            RowDoesNotExist,
        ):
            return False

        return True

    def get_group_name(self, table_id, row_id, *args, **kwargs):
        return f"table-{table_id}-row-{row_id}"

    def get_permission_channel_group_name(self, table_id, **kwargs):
        return f"permissions-table-{table_id}"
