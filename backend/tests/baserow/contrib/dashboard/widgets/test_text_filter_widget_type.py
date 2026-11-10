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
from baserow.core.formula import BaserowFormulaObject
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid


@pytest.mark.django_db
@pytest.mark.parametrize("mode", ["input", "dropdown"])
@pytest.mark.parametrize("multiple", [False, True])
@pytest.mark.parametrize(
    "default_value,single_default,multiple_defaults",
    [
        ("get('literal')", "get('literal')", ["get('literal')"]),
        (["France", "Belgium"], "France", ["France", "Belgium"]),
    ],
)
def test_text_widget_export_import_and_duplicate(
    data_fixture, mode, multiple, default_value, single_default, multiple_defaults
):
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
        default_value=default_value,
        mode=mode,
        multiple=multiple,
        options=BaserowFormulaObject.create("France, Belgium", mode="raw"),
    )
    assert isinstance(widget, TextFilterWidget)
    expected_default = (
        multiple_defaults if mode == "dropdown" and multiple else single_default
    )
    assert widget.default_value == expected_default
    assert not DashboardDataSource.objects.filter(dashboard=dashboard).exists()
    config = ImportExportConfig(include_permission_data=True)
    serialized = json.loads(
        json.dumps(DashboardApplicationType().export_serialized(dashboard, config))
    )
    serialized["widgets"][0]["default_value"] = default_value
    imported = DashboardApplicationType().import_serialized(
        dashboard.workspace, serialized, config, id_mapping={}
    )
    duplicated = CoreHandler().duplicate_application(user, dashboard)
    for application in [imported, duplicated]:
        copy = TextFilterWidget.objects.get(dashboard=application)
        assert copy.mode == mode
        assert copy.multiple == multiple
        assert copy.options == BaserowFormulaObject.create(
            "France, Belgium", mode="raw"
        )
        assert (copy.title, copy.description, copy.placeholder, copy.default_value) == (
            "Search",
            "Enter text",
            "Type here",
            expected_default,
        )
        assert not DashboardDataSource.objects.filter(dashboard=application).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("default_value", ["Initial", ["France", "Belgium"]])
def test_text_widget_configuration_undo_redo(data_fixture, default_value):
    """Undo restores both settings, including clearing a configured default."""
    user = data_fixture.create_user(session_id="text-widget")
    dashboard = data_fixture.create_dashboard_application(user=user)
    multiple = isinstance(default_value, list)
    empty_default = [] if multiple else ""
    widget = WidgetService().create_widget(
        user,
        "text_filter",
        dashboard.id,
        title="Text",
        mode="dropdown",
        multiple=multiple,
    )
    assert (widget.placeholder, widget.default_value) == ("", empty_default)
    action_type_registry.get_by_type(UpdateWidgetActionType).do(
        user,
        widget.id,
        "text_filter",
        {"placeholder": "Search here", "default_value": default_value},
    )
    widget.refresh_from_db()
    assert (widget.placeholder, widget.default_value) == ("Search here", default_value)
    scopes = [ApplicationActionScopeType.value(application_id=dashboard.id)]
    undone = ActionHandler.undo(user, scopes, "text-widget")
    assert_undo_redo_actions_are_valid(undone, [UpdateWidgetActionType])
    widget.refresh_from_db()
    assert (widget.placeholder, widget.default_value) == ("", empty_default)
    redone = ActionHandler.redo(user, scopes, "text-widget")
    assert_undo_redo_actions_are_valid(redone, [UpdateWidgetActionType])
    widget.refresh_from_db()
    assert (widget.placeholder, widget.default_value) == ("Search here", default_value)
    WidgetService().update_widget(user, widget.id, placeholder="", default_value="")
    widget.refresh_from_db()
    assert (widget.placeholder, widget.default_value) == ("", empty_default)


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("multiple", [False, True])
def test_changing_options_and_clearing_defaults_is_one_undo_action(
    data_fixture, multiple
):
    user = data_fixture.create_user(session_id="change-options")
    dashboard = data_fixture.create_dashboard_application(user=user)
    original_options = BaserowFormulaObject.create("France, Belgium", mode="raw")
    original_default = ["France", "Belgium"] if multiple else "France"
    new_options = BaserowFormulaObject.create("Germany, Spain", mode="raw")
    cleared = [] if multiple else ""
    widget = WidgetService().create_widget(
        user,
        "text_filter",
        dashboard.id,
        title="Country",
        mode="dropdown",
        multiple=multiple,
        options=original_options,
        default_value=original_default,
    )
    action_type_registry.get_by_type(UpdateWidgetActionType).do(
        user,
        widget.id,
        "text_filter",
        {"options": new_options, "default_value": cleared},
    )
    widget.refresh_from_db()
    assert (widget.options, widget.default_value) == (new_options, cleared)
    scopes = [ApplicationActionScopeType.value(application_id=dashboard.id)]
    undone = ActionHandler.undo(user, scopes, "change-options")
    assert_undo_redo_actions_are_valid(undone, [UpdateWidgetActionType])
    widget.refresh_from_db()
    assert (widget.options, widget.default_value) == (
        original_options,
        original_default,
    )
    redone = ActionHandler.redo(user, scopes, "change-options")
    assert_undo_redo_actions_are_valid(redone, [UpdateWidgetActionType])
    widget.refresh_from_db()
    assert (widget.options, widget.default_value) == (new_options, cleared)


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
            "options": BaserowFormulaObject.create("France, Belgium", mode="raw"),
        },
        format="json",
        **headers,
    )
    assert response.status_code == 200
    widget_id = response.json()["id"]
    assert response.json()["placeholder"] == "Type here"
    assert response.json()["default_value"] == "Initial"
    assert response.json()["mode"] == "input"
    assert response.json()["multiple"] is False
    widget = TextFilterWidget.objects.get(id=widget_id)
    public = PublicDashboardInfoSerializer(
        dashboard, context={"widgets": [widget], "data_sources": []}
    ).data
    assert public["widgets"][0]["default_value"] == "Initial"
    assert public["widgets"][0]["placeholder"] == "Type here"
    assert public["widgets"][0]["mode"] == "input"
    assert public["widgets"][0]["multiple"] is False
    assert public["widgets"][0]["options"] == widget.options
    detail_url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget_id})
    response = api_client.patch(
        detail_url,
        {
            "placeholder": "",
            "default_value": "",
            "mode": "dropdown",
            "multiple": True,
        },
        format="json",
        **headers,
    )
    assert response.status_code == 200
    widget.refresh_from_db()
    assert (widget.placeholder, widget.default_value) == ("", [])
    assert widget.mode == "dropdown"
    assert widget.multiple is True
    response = api_client.patch(
        detail_url, {"mode": "invalid"}, format="json", **headers
    )
    assert response.status_code == 400


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
    assert (widget.grid_width, widget.grid_height) == (2, 2)
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


@pytest.mark.django_db
def test_multiple_default_values_api_and_dispatch(api_client, data_fixture):
    from django.urls import reverse

    from baserow.contrib.dashboard.api.public.serializers import (
        PublicDashboardInfoSerializer,
    )

    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.post(
        reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": dashboard.id}),
        {
            "type": "text_filter",
            "title": "Country",
            "mode": "dropdown",
            "multiple": True,
            "default_value": ["France", "Belgium", "A country, with a comma"],
        },
        format="json",
        **headers,
    )
    assert response.status_code == 200
    defaults = ["France", "Belgium", "A country, with a comma"]
    widget = TextFilterWidget.objects.get(id=response.json()["id"])
    assert widget.default_value == defaults
    assert response.json()["default_value"] == defaults
    assert widget.get_type().get_filter_value(widget, {}) == defaults
    assert widget.get_type().get_filter_value(widget, {str(widget.id): []}) == []
    public = PublicDashboardInfoSerializer(
        dashboard, context={"widgets": [widget], "data_sources": []}
    ).data
    assert public["widgets"][0]["default_value"] == defaults
    url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget.id})
    for invalid in [{"country": "France"}, ["France", 1], None, 42]:
        response = api_client.patch(
            url, {"default_value": invalid}, format="json", **headers
        )
        assert response.status_code == 400
    response = api_client.patch(url, {"multiple": False}, format="json", **headers)
    assert response.status_code == 200
    widget.refresh_from_db()
    assert widget.get_type().get_filter_value(widget, {}) == "France"
    response = api_client.patch(
        url, {"multiple": True, "default_value": []}, format="json", **headers
    )
    assert response.status_code == 200
    widget.refresh_from_db()
    assert widget.default_value == []
    assert widget.get_type().get_filter_value(widget, {}) == []


@pytest.mark.django_db
@pytest.mark.parametrize("narrowing", [{"multiple": False}, {"mode": "input"}])
@pytest.mark.parametrize(
    "defaults, single", [(["France", "Belgium"], "France"), ([], "")]
)
def test_mode_only_api_updates_persist_default_cardinality(
    api_client, data_fixture, narrowing, defaults, single
):
    from django.urls import reverse

    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = WidgetService().create_widget(
        user,
        "text_filter",
        dashboard.id,
        title="Country",
        mode="dropdown",
        multiple=True,
        default_value=defaults,
    )
    url = reverse("api:dashboard:widgets:item", kwargs={"widget_id": widget.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.patch(url, narrowing, format="json", **headers)
    assert response.status_code == 200
    widget.refresh_from_db()
    assert response.json()["default_value"] == single
    assert widget.default_value == single
    response = api_client.patch(
        url, {"mode": "dropdown", "multiple": True}, format="json", **headers
    )
    assert response.status_code == 200
    widget.refresh_from_db()
    retained = [single] if single else []
    assert response.json()["default_value"] == retained
    assert widget.default_value == retained
    assert widget.get_type().get_filter_value(widget, {}) == retained


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_mode_only_update_restores_defaults_on_undo(data_fixture):
    user = data_fixture.create_user(session_id="default-cardinality")
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = WidgetService().create_widget(
        user,
        "text_filter",
        dashboard.id,
        title="Country",
        mode="dropdown",
        multiple=True,
        default_value=["France", "Belgium"],
    )
    action_type_registry.get_by_type(UpdateWidgetActionType).do(
        user, widget.id, "text_filter", {"multiple": False}
    )
    widget.refresh_from_db()
    assert (widget.multiple, widget.default_value) == (False, "France")
    scopes = [ApplicationActionScopeType.value(application_id=dashboard.id)]
    undone = ActionHandler.undo(user, scopes, "default-cardinality")
    assert_undo_redo_actions_are_valid(undone, [UpdateWidgetActionType])
    widget.refresh_from_db()
    assert (widget.multiple, widget.default_value) == (True, ["France", "Belgium"])
    redone = ActionHandler.redo(user, scopes, "default-cardinality")
    assert_undo_redo_actions_are_valid(redone, [UpdateWidgetActionType])
    widget.refresh_from_db()
    assert (widget.multiple, widget.default_value) == (False, "France")
