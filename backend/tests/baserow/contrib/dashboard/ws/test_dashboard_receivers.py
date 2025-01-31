from unittest.mock import patch

from django.db import transaction

import pytest

from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.data_sources.signals import dashboard_data_source_updated
from baserow.contrib.dashboard.widgets.handler import WidgetHandler
from baserow.contrib.dashboard.widgets.registries import widget_type_registry
from baserow.contrib.dashboard.widgets.signals import (
    widget_created,
    widget_deleted,
    widget_updated,
)
from baserow.core.services.registries import service_type_registry


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_widget_created_ws_receiver(mock_broadcast_to_channel_group, data_fixture):
    dashboard = data_fixture.create_dashboard_application()
    widget_type = widget_type_registry.get("summary")
    new_widget = WidgetHandler().create_widget(widget_type, dashboard, title="Widget")

    widget_created.send(None, widget=new_widget)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"dashboard-{dashboard.id}"
    assert args[0][1]["type"] == "widget_created"
    assert args[0][1]["dashboard_id"] == dashboard.id
    assert args[0][1]["widget"]["id"] == new_widget.id
    assert args[0][1]["widget"]["title"] == "Widget"


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_widget_updated_ws_receiver(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user(web_socket_id="test_websocket_id")
    dashboard = data_fixture.create_dashboard_application()
    widget = data_fixture.create_summary_widget(dashboard=dashboard)
    updated_widget = WidgetHandler().update_widget(
        widget, title="Updated title", description="Updated description"
    )

    widget_updated.send(None, user=user, widget=updated_widget.widget)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"dashboard-{dashboard.id}"
    assert args[0][1]["type"] == "widget_updated"
    assert args[0][1]["dashboard_id"] == dashboard.id
    assert args[0][1]["widget"]["id"] == updated_widget.widget.id
    assert args[0][1]["widget"]["title"] == "Updated title"
    assert args[0][1]["widget"]["description"] == "Updated description"
    assert args[0][2] == "test_websocket_id"


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_widget_deleted_ws_receiver(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user(web_socket_id="test_websocket_id")
    dashboard = data_fixture.create_dashboard_application()
    widget = data_fixture.create_summary_widget(dashboard=dashboard)

    widget_deleted.send(None, user=user, widget=widget)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"dashboard-{dashboard.id}"
    assert args[0][1]["type"] == "widget_deleted"
    assert args[0][1]["dashboard_id"] == dashboard.id
    assert args[0][1]["widget"]["id"] == widget.id
    assert args[0][2] == "test_websocket_id"


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_dashboard_data_source_updated_ws_receiver(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user(web_socket_id="test_websocket_id")
    dashboard = data_fixture.create_dashboard_application()
    table = data_fixture.create_database_table()
    field = data_fixture.create_number_field(table=table)
    widget_type = widget_type_registry.get("summary")
    widget = WidgetHandler().create_widget(widget_type, dashboard, title="Widget")
    service_type = service_type_registry.get_by_model(widget.data_source.service)

    with transaction.atomic():
        data_source_updated = DashboardDataSourceHandler().update_data_source(
            widget.data_source,
            service_type,
            table=table,
            field=field,
            aggregation_type="sum",
        )
        dashboard_data_source_updated.send(
            None, user=user, data_source=data_source_updated.data_source
        )

    assert data_source_updated.data_source.service.table_id == table.id

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"dashboard-{dashboard.id}"
    assert args[0][1]["type"] == "data_source_updated"
    assert args[0][1]["dashboard_id"] == dashboard.id
    assert args[0][1]["data_source"]["id"] == data_source_updated.data_source.id
    assert args[0][1]["data_source"]["table_id"] == table.id
    assert args[0][1]["data_source"]["view_id"] is None
    assert args[0][1]["data_source"]["field_id"] == field.id
    assert args[0][1]["data_source"]["aggregation_type"] == "sum"
    assert args[0][2] == "test_websocket_id"
