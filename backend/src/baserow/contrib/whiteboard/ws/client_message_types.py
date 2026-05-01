from channels.db import database_sync_to_async

from baserow.contrib.whiteboard.exceptions import WhiteboardDoesNotExist
from baserow.contrib.whiteboard.handler import WhiteboardHandler
from baserow.contrib.whiteboard.operations import (
    UpdateWhiteboardContentOperationType,
)
from baserow.contrib.whiteboard.ws.pages import WhiteboardPageType
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.ws.registries import ClientMessageType


class BroadcastWhiteboardChangesMessageType(ClientMessageType):
    """
    Re-broadcasts an opaque payload (scene update, pointer movement) to every
    other client subscribed to the same whiteboard's page. Replaces the
    previous `POST /api/whiteboard/<id>/broadcast-changes/` endpoint to avoid
    the per-message HTTP auth + worker overhead — the WebSocket connection
    is already authenticated and the receiver is already subscribed.

    Inbound payload:
        {
            "type": "broadcast_whiteboard_changes",
            "whiteboard_id": <int>,
            "payload": <opaque dict — must include `type` for the receiver>
        }

    Nothing is persisted; persistence still flows through the HTTP `PUT`
    endpoint on the same throttle as before.
    """

    type = "broadcast_whiteboard_changes"

    async def handle(self, consumer, content):
        user = consumer.scope.get("user")
        web_socket_id = consumer.scope.get("web_socket_id")
        if not user:
            return

        whiteboard_id = content.get("whiteboard_id")
        payload = content.get("payload")
        if not isinstance(whiteboard_id, int) or not isinstance(payload, dict):
            return

        try:
            allowed = await database_sync_to_async(self._check_permission)(
                user, whiteboard_id
            )
        except WhiteboardDoesNotExist:
            return
        if not allowed:
            return

        WhiteboardPageType().broadcast(
            payload,
            ignore_web_socket_id=web_socket_id,
            whiteboard_id=whiteboard_id,
        )

    @staticmethod
    def _check_permission(user, whiteboard_id):
        whiteboard = WhiteboardHandler().get_whiteboard(int(whiteboard_id))
        try:
            CoreHandler().check_permissions(
                user,
                UpdateWhiteboardContentOperationType.type,
                workspace=whiteboard.workspace,
                context=whiteboard,
            )
        except PermissionException:
            return False
        return True
