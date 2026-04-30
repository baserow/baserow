from baserow.contrib.whiteboard.exceptions import WhiteboardDoesNotExist
from baserow.contrib.whiteboard.handler import WhiteboardHandler
from baserow.contrib.whiteboard.operations import ReadWhiteboardOperationType
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.ws.registries import PageType


class WhiteboardPageType(PageType):
    type = "whiteboard"
    parameters = ["whiteboard_id"]

    def can_add(self, user, web_socket_id, whiteboard_id, **kwargs):
        """
        The user can only join this page if the whiteboard exists and they
        have read access to it.
        """

        if not whiteboard_id:
            return False

        try:
            whiteboard = WhiteboardHandler().get_whiteboard(whiteboard_id)
            CoreHandler().check_permissions(
                user,
                ReadWhiteboardOperationType.type,
                workspace=whiteboard.workspace,
                context=whiteboard,
            )
        except (WhiteboardDoesNotExist, PermissionException):
            return False

        return True

    def get_group_name(self, whiteboard_id, **kwargs):
        return f"whiteboard-{whiteboard_id}"

    def get_permission_channel_group_name(self, whiteboard_id, **kwargs):
        return f"permissions-whiteboard-{whiteboard_id}"
