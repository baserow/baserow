from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.whiteboard.ws.signals import whiteboard_content_updated
from baserow.ws.registries import page_registry


@receiver(whiteboard_content_updated)
def _broadcast_whiteboard_content_updated(sender, whiteboard, user=None, **kwargs):
    def send_ws_message():
        page_type = page_registry.get("whiteboard")
        payload = {
            "type": "whiteboard_content_updated",
            "whiteboard_id": whiteboard.id,
        }
        page_type.broadcast(
            payload,
            whiteboard_id=whiteboard.id,
            ignore_web_socket_id=getattr(user, "web_socket_id", None),
        )

    transaction.on_commit(send_ws_message)
