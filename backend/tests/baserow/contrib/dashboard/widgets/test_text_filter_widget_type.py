import json

import pytest

from baserow.contrib.dashboard.application_types import DashboardApplicationType
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.widgets.actions import UpdateWidgetActionType
from baserow.contrib.dashboard.widgets.models import TextFilterWidget
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid


@pytest.mark.django_db
def test_text_widget_export_import_and_duplicate(data_fixture):
    """Literal settings survive application round trips without a data source."""
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = WidgetService().create_widget(
        user,
        "text_filter",
        dashboard.id,
        title="Search",
        description="Enter text",
        placeholder="Type here",
        default_value="get('literal')",
    )
    assert isinstance(widget, TextFilterWidget)
    assert not DashboardDataSource.objects.filter(dashboard=dashboard).exists()
    config = ImportExportConfig(include_permission_data=True)
    serialized = json.loads(
        json.dumps(DashboardApplicationType().export_serialized(dashboard, config))
    )
    imported = DashboardApplicationType().import_serialized(
        dashboard.workspace, serialized, config, id_mapping={}
    )
    duplicated = CoreHandler().duplicate_application(user, dashboard)
    for application in [imported, duplicated]:
        copy = TextFilterWidget.objects.get(dashboard=application)
        assert (copy.title, copy.description, copy.placeholder, copy.default_value) == (
            "Search",
            "Enter text",
            "Type here",
            "get('literal')",
        )
        assert not DashboardDataSource.objects.filter(dashboard=application).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_text_widget_configuration_undo_redo(data_fixture):
    """Undo restores both settings, including clearing a configured default."""
    user = data_fixture.create_user(session_id="text-widget")
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = WidgetService().create_widget(
        user, "text_filter", dashboard.id, title="Text"
    )
    assert (widget.placeholder, widget.default_value) == ("", "")
    action_type_registry.get_by_type(UpdateWidgetActionType).do(
        user,
        widget.id,
        "text_filter",
        {"placeholder": "Search here", "default_value": "Initial"},
    )
    widget.refresh_from_db()
    assert (widget.placeholder, widget.default_value) == ("Search here", "Initial")
    scopes = [ApplicationActionScopeType.value(application_id=dashboard.id)]
    undone = ActionHandler.undo(user, scopes, "text-widget")
    assert_undo_redo_actions_are_valid(undone, [UpdateWidgetActionType])
    widget.refresh_from_db()
    assert (widget.placeholder, widget.default_value) == ("", "")
    redone = ActionHandler.redo(user, scopes, "text-widget")
    assert_undo_redo_actions_are_valid(redone, [UpdateWidgetActionType])
    widget.refresh_from_db()
    assert (widget.placeholder, widget.default_value) == ("Search here", "Initial")
    WidgetService().update_widget(user, widget.id, placeholder="", default_value="")
    widget.refresh_from_db()
    assert (widget.placeholder, widget.default_value) == ("", "")


@pytest.mark.django_db
def test_text_widget_crud_serializers(api_client, data_fixture):
    """Both dashboard APIs expose literal configuration, never viewer input."""
    from django.urls import reverse

    from baserow.contrib.dashboard.api.public.serializers import (
        PublicDashboardInfoSerializer,
    )

    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    url = reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": dashboard.id})
    response = api_client.post(
        url,
        {
            "type": "text_filter",
            "title": "Search",
            "placeholder": "Type here",
            "default_value": "Initial",
        },
        format="json",
        **headers,
    )
    assert response.status_code == 200
    widget_id = response.json()["id"]
    assert response.json()["placeholder"] == "Type here"
    assert response.json()["default_value"] == "Initial"
    widget = TextFilterWidget.objects.get(id=widget_id)
    public = PublicDashboardInfoSerializer(
        dashboard, context={"widgets": [widget], "data_sources": []}
    ).data
    assert public["widgets"][0]["default_value"] == "Initial"
    assert public["widgets"][0]["placeholder"] == "Type here"
    detail_url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget_id})
    response = api_client.patch(
        detail_url,
        {
            "placeholder": "",
            "default_value": "",
        },
        format="json",
        **headers,
    )
    assert response.status_code == 200
    widget.refresh_from_db()
    assert (widget.placeholder, widget.default_value) == ("", "")


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_text_widget_creation_undo_redo(data_fixture):
    """Creation undo/redo restores a text widget and its literal configuration."""
    from baserow.contrib.dashboard.widgets.actions import CreateWidgetActionType

    user = data_fixture.create_user(session_id="create-text-widget")
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = action_type_registry.get_by_type(CreateWidgetActionType).do(
        user,
        dashboard.id,
        "text_filter",
        {"title": "Search", "placeholder": "Enter text", "default_value": "Initial"},
    )
    assert (widget.grid_width, widget.grid_height) == (2, 4)
    scopes = [ApplicationActionScopeType.value(application_id=dashboard.id)]
    undone = ActionHandler.undo(user, scopes, "create-text-widget")
    assert_undo_redo_actions_are_valid(undone, [CreateWidgetActionType])
    assert not TextFilterWidget.objects.filter(id=widget.id).exists()
    redone = ActionHandler.redo(user, scopes, "create-text-widget")
    assert_undo_redo_actions_are_valid(redone, [CreateWidgetActionType])
    widget.refresh_from_db()
    assert (widget.title, widget.placeholder, widget.default_value) == (
        "Search",
        "Enter text",
        "Initial",
    )
