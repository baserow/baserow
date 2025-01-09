from unittest.mock import patch

import pytest

from baserow.contrib.dashboard.widgets.handler import WidgetHandler
from baserow.contrib.dashboard.widgets.registries import widget_type_registry
from baserow.contrib.dashboard.widgets.signals import widget_created


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
