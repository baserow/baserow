from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.dashboard.api.widgets.serializers import WidgetSerializer
from baserow.contrib.dashboard.widgets import signals as widget_signals
from baserow.contrib.dashboard.widgets.registries import widget_type_registry
from baserow.ws.registries import page_registry


@receiver(widget_signals.widget_created)
def widget_created(
    sender,
    widget,
    **kwargs,
):
    def send_ws_message():
        page_type = page_registry.get("dashboard")
        widget_serializer = widget_type_registry.get_serializer(
            widget, WidgetSerializer
        )
        payload = {
            "type": "widget_created",
            "dashboard_id": widget.dashboard.id,
            "widget": widget_serializer.data,
        }
        page_type.broadcast(payload, dashboard_id=widget.dashboard.id)

    transaction.on_commit(send_ws_message)
