from django.contrib.contenttypes.models import ContentType

import pytest

from baserow.contrib.dashboard.widgets.actions import (
    CreateWidgetActionType,
    DeleteWidgetActionType,
    UpdateWidgetActionType,
    UpdateWidgetLayoutActionType,
)
from baserow.contrib.dashboard.widgets.models import SummaryWidget
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_create_widget(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, name="Dashboard 1", description="Description 1", user=user
    )

    # do
    action_type_registry.get_by_type(CreateWidgetActionType).do(
        user,
        dashboard.id,
        "summary",
        {"title": "Widget title", "description": "Widget description"},
    )

    dashboard_widgets = WidgetService().get_widgets(user, dashboard.id)
    assert len(dashboard_widgets) == 1
    widget = dashboard_widgets[0]
    assert widget.title == "Widget title"
    assert widget.description == "Widget description"
    assert widget.content_type == ContentType.objects.get_for_model(SummaryWidget)

    # undo
    ActionHandler.undo(
        user,
        [ApplicationActionScopeType.value(application_id=dashboard.id)],
        session_id,
    )

    dashboard_widgets = WidgetService().get_widgets(user, dashboard.id)
    assert len(dashboard_widgets) == 0

    # redo
    actions_redone = ActionHandler.redo(
        user,
        [ApplicationActionScopeType.value(application_id=dashboard.id)],
        session_id,
    )
    assert_undo_redo_actions_are_valid(actions_redone, [CreateWidgetActionType])

    dashboard_widgets = WidgetService().get_widgets(user, dashboard.id)
    assert len(dashboard_widgets) == 1
    widget = dashboard_widgets[0]
    assert widget.title == "Widget title"
    assert widget.description == "Widget description"
    assert widget.content_type == ContentType.objects.get_for_model(SummaryWidget)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_update_widget(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, name="Dashboard 1", description="Description 1", user=user
    )
    original_title = "Widget title"
    original_description = "Widget description"
    widget = WidgetService().create_widget(
        user,
        "summary",
        dashboard.id,
        title=original_title,
        description=original_description,
    )

    # do
    updated_data = {"title": "New title", "description": "New description"}
    updated_widget = action_type_registry.get_by_type(UpdateWidgetActionType).do(
        user, widget.id, "summary", updated_data
    )

    assert updated_widget.title == "New title"
    assert updated_widget.description == "New description"

    # undo
    ActionHandler.undo(
        user,
        [ApplicationActionScopeType.value(application_id=dashboard.id)],
        session_id,
    )

    updated_widget.refresh_from_db()
    assert updated_widget.title == original_title
    assert updated_widget.description == original_description

    # redo
    actions_redone = ActionHandler.redo(
        user,
        [ApplicationActionScopeType.value(application_id=dashboard.id)],
        session_id,
    )
    assert_undo_redo_actions_are_valid(actions_redone, [UpdateWidgetActionType])

    updated_widget.refresh_from_db()
    assert updated_widget.title == "New title"
    assert updated_widget.description == "New description"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_delete_widget(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, name="Dashboard 1", description="Description 1", user=user
    )
    widget = WidgetService().create_widget(
        user,
        "summary",
        dashboard.id,
        title="Widget title",
        description="Widget description",
    )
    second_widget = WidgetService().create_widget(
        user,
        "summary",
        dashboard.id,
        title="Second widget",
    )
    widget.grid_width = 6
    widget.save(update_fields=["grid_width"])
    second_widget.grid_width = 6
    second_widget.save(update_fields=["grid_width"])
    dashboard_widgets = WidgetService().get_widgets(user, dashboard.id)
    assert len(dashboard_widgets) == 2

    # do
    action_type_registry.get_by_type(DeleteWidgetActionType).do(user, widget.id)

    dashboard_widgets = WidgetService().get_widgets(user, dashboard.id)
    assert len(dashboard_widgets) == 1
    second_widget.refresh_from_db()
    assert (second_widget.grid_x, second_widget.grid_y) == (0, 0)

    # undo
    ActionHandler.undo(
        user,
        [ApplicationActionScopeType.value(application_id=dashboard.id)],
        session_id,
    )

    dashboard_widgets = WidgetService().get_widgets(user, dashboard.id)
    assert len(dashboard_widgets) == 2
    restored_widget = next(item for item in dashboard_widgets if item.id == widget.id)
    assert restored_widget.title == "Widget title"
    assert restored_widget.description == "Widget description"
    assert restored_widget.content_type == ContentType.objects.get_for_model(
        SummaryWidget
    )
    restored_widget.refresh_from_db()
    second_widget.refresh_from_db()
    assert (restored_widget.grid_x, restored_widget.grid_y) == (0, 0)
    assert (second_widget.grid_x, second_widget.grid_y) == (0, 4)

    # redo
    actions_redone = ActionHandler.redo(
        user,
        [ApplicationActionScopeType.value(application_id=dashboard.id)],
        session_id,
    )
    assert_undo_redo_actions_are_valid(actions_redone, [DeleteWidgetActionType])

    dashboard_widgets = WidgetService().get_widgets(user, dashboard.id)
    assert len(dashboard_widgets) == 1
    second_widget.refresh_from_db()
    assert (second_widget.grid_x, second_widget.grid_y) == (0, 0)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_update_widget_layout(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, user=user
    )
    first_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="First"
    )
    second_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Second"
    )
    new_layout = [
        {
            "id": first_widget.id,
            "grid_x": 0,
            "grid_y": 0,
            "grid_width": 2,
            "grid_height": 4,
        },
        {
            "id": second_widget.id,
            "grid_x": 2,
            "grid_y": 0,
            "grid_width": 2,
            "grid_height": 4,
        },
    ]

    action_type_registry.get_by_type(UpdateWidgetLayoutActionType).do(
        user, dashboard.id, new_layout
    )
    second_widget.refresh_from_db()
    assert (second_widget.grid_x, second_widget.grid_y) == (2, 0)
    ActionHandler.undo(
        user,
        [ApplicationActionScopeType.value(application_id=dashboard.id)],
        session_id,
    )
    second_widget.refresh_from_db()
    assert (second_widget.grid_x, second_widget.grid_y) == (0, 4)

    actions_redone = ActionHandler.redo(
        user,
        [ApplicationActionScopeType.value(application_id=dashboard.id)],
        session_id,
    )
    assert_undo_redo_actions_are_valid(actions_redone, [UpdateWidgetLayoutActionType])
    second_widget.refresh_from_db()
    assert (second_widget.grid_x, second_widget.grid_y) == (2, 0)
