from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.dashboard.api.data_sources.serializers import (
    DashboardDataSourceSerializer,
)
from baserow.contrib.dashboard.api.widgets.serializers import WidgetSerializer
from baserow.contrib.dashboard.data_sources import signals as data_source_signals
from baserow.contrib.dashboard.widgets import signals as widget_signals
from baserow.contrib.dashboard.widgets.registries import widget_type_registry
from baserow.core.services.registries import service_type_registry
from baserow.ws.registries import page_registry


@receiver(widget_signals.widget_created)
def widget_created(
    sender,
    widget,
    user=None,
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
        page_type.broadcast(
            payload,
            dashboard_id=widget.dashboard.id,
            ignore_web_socket_id=getattr(user, "web_socket_id", None)
            if user is not None
            else None,
        )

    transaction.on_commit(send_ws_message)


@receiver(widget_signals.widget_updated)
def widget_updated(
    sender,
    widget,
    user,
    **kwargs,
):
    def send_ws_message():
        page_type = page_registry.get("dashboard")
        widget_serializer = widget_type_registry.get_serializer(
            widget, WidgetSerializer
        )
        payload = {
            "type": "widget_updated",
            "dashboard_id": widget.dashboard.id,
            "widget": widget_serializer.data,
        }
        page_type.broadcast(
            payload,
            dashboard_id=widget.dashboard.id,
            ignore_web_socket_id=getattr(user, "web_socket_id", None),
        )

    transaction.on_commit(send_ws_message)


@receiver(widget_signals.widget_deleted)
def widget_deleted(
    sender,
    user,
    widget,
    **kwargs,
):
    def send_ws_message():
        page_type = page_registry.get("dashboard")
        widget_serializer = widget_type_registry.get_serializer(
            widget, WidgetSerializer
        )
        payload = {
            "type": "widget_deleted",
            "dashboard_id": widget.dashboard.id,
            "widget": widget_serializer.data,
        }
        page_type.broadcast(
            payload,
            dashboard_id=widget.dashboard.id,
            ignore_web_socket_id=getattr(user, "web_socket_id", None),
        )

    transaction.on_commit(send_ws_message)


@receiver(data_source_signals.dashboard_data_source_updated)
def dashboard_data_source_updated(sender, user, data_source, **kwargs):
    def send_ws_message():
        page_type = page_registry.get("dashboard")
        data_source_serializer = service_type_registry.get_serializer(
            data_source.service,
            DashboardDataSourceSerializer,
            context={"data_source": data_source},
        )
        payload = {
            "type": "data_source_updated",
            "dashboard_id": data_source.dashboard.id,
            "data_source": data_source_serializer.data,
        }
        page_type.broadcast(
            payload,
            dashboard_id=data_source.dashboard.id,
            ignore_web_socket_id=getattr(user, "web_socket_id", None),
        )

    transaction.on_commit(send_ws_message)
