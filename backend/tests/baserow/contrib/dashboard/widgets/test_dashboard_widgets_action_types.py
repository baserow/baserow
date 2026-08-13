from unittest.mock import call, patch

from django.contrib.contenttypes.models import ContentType

import pytest

from baserow.contrib.dashboard.widgets.actions import (
    CreateWidgetActionType,
    DeleteWidgetActionType,
    UpdateWidgetActionType,
    UpdateWidgetLayoutActionType,
)
from baserow.contrib.dashboard.widgets.models import SummaryWidget
from baserow.contrib.dashboard.widgets.operations import UpdateWidgetLayoutOperationType
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.handler import CoreHandler
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
    first_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="First widget"
    )
    second_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Second widget"
    )
    second_widget.grid_y = 4
    second_widget.save(update_fields=["grid_y"])

    # do
    widget = action_type_registry.get_by_type(CreateWidgetActionType).do(
        user,
        dashboard.id,
        "summary",
        {"title": "Widget title", "description": "Widget description"},
    )

    dashboard_widgets = WidgetService().get_widgets(user, dashboard.id)
    assert len(dashboard_widgets) == 3
    assert widget.title == "Widget title"
    assert widget.description == "Widget description"
    assert widget.content_type == ContentType.objects.get_for_model(SummaryWidget)
    assert (widget.grid_x, widget.grid_y) == (2, 0)

    # undo
    ActionHandler.undo(
        user,
        [ApplicationActionScopeType.value(application_id=dashboard.id)],
        session_id,
    )

    dashboard_widgets = WidgetService().get_widgets(user, dashboard.id)
    assert len(dashboard_widgets) == 2
    second_widget.refresh_from_db()
    assert (second_widget.grid_x, second_widget.grid_y) == (2, 4)

    # redo
    actions_redone = ActionHandler.redo(
        user,
        [ApplicationActionScopeType.value(application_id=dashboard.id)],
        session_id,
    )
    assert_undo_redo_actions_are_valid(actions_redone, [CreateWidgetActionType])

    dashboard_widgets = WidgetService().get_widgets(user, dashboard.id)
    assert len(dashboard_widgets) == 3
    widget.refresh_from_db()
    second_widget.refresh_from_db()
    assert widget.title == "Widget title"
    assert widget.description == "Widget description"
    assert widget.content_type == ContentType.objects.get_for_model(SummaryWidget)
    assert (widget.grid_x, widget.grid_y) == (2, 0)
    assert (second_widget.grid_x, second_widget.grid_y) == (2, 4)


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
    widget.grid_x = 0
    widget.grid_y = 0
    widget.grid_width = 6
    widget.save(update_fields=["grid_x", "grid_y", "grid_width"])
    second_widget.grid_x = 0
    second_widget.grid_y = 4
    second_widget.grid_width = 6
    second_widget.save(update_fields=["grid_x", "grid_y", "grid_width"])
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
            "grid_x": 4,
            "grid_y": 0,
            "grid_width": 2,
            "grid_height": 4,
        },
    ]

    action_type_registry.get_by_type(UpdateWidgetLayoutActionType).do(
        user, dashboard.id, new_layout
    )
    second_widget.refresh_from_db()
    assert (second_widget.grid_x, second_widget.grid_y) == (4, 0)
    ActionHandler.undo(
        user,
        [ApplicationActionScopeType.value(application_id=dashboard.id)],
        session_id,
    )
    second_widget.refresh_from_db()
    assert (second_widget.grid_x, second_widget.grid_y) == (2, 0)

    actions_redone = ActionHandler.redo(
        user,
        [ApplicationActionScopeType.value(application_id=dashboard.id)],
        session_id,
    )
    assert_undo_redo_actions_are_valid(actions_redone, [UpdateWidgetLayoutActionType])
    second_widget.refresh_from_db()
    assert (second_widget.grid_x, second_widget.grid_y) == (4, 0)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_grid_create_action_undo_redo_uses_one_layout_snapshot_without_layout_permission(
    data_fixture, monkeypatch
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    dashboard = data_fixture.create_dashboard_application(user=user)
    WidgetService().create_widget(user, "summary", dashboard.id, title="Existing")
    action_type = action_type_registry.get_by_type(CreateWidgetActionType)
    action_type.do(user, dashboard.id, "summary", {"title": "Created"})

    checked_operations = []
    original_check_permissions = CoreHandler.check_permissions

    def capture_check_permissions(self, actor, operation_name, *args, **kwargs):
        checked_operations.append(operation_name)
        return original_check_permissions(self, actor, operation_name, *args, **kwargs)

    monkeypatch.setattr(CoreHandler, "check_permissions", capture_check_permissions)

    with (
        patch(
            "baserow.contrib.dashboard.widgets.signals.widget_created.send"
        ) as widget_created_mock,
        patch(
            "baserow.contrib.dashboard.widgets.signals.widget_deleted.send"
        ) as widget_deleted_mock,
        patch(
            "baserow.contrib.dashboard.widgets.signals.widgets_layout_updated.send"
        ) as widgets_layout_updated_mock,
    ):
        ActionHandler.undo(
            user,
            [ApplicationActionScopeType.value(application_id=dashboard.id)],
            session_id,
        )

        widget_created_mock.assert_not_called()
        widget_deleted_mock.assert_not_called()
        widgets_layout_updated_mock.assert_called_once()
        assert UpdateWidgetLayoutOperationType.type not in checked_operations

        checked_operations.clear()
        widget_created_mock.reset_mock()
        widget_deleted_mock.reset_mock()
        widgets_layout_updated_mock.reset_mock()

        ActionHandler.redo(
            user,
            [ApplicationActionScopeType.value(application_id=dashboard.id)],
            session_id,
        )

    widget_created_mock.assert_not_called()
    widget_deleted_mock.assert_not_called()
    widgets_layout_updated_mock.assert_called_once()
    assert UpdateWidgetLayoutOperationType.type not in checked_operations


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_grid_delete_action_undo_redo_uses_one_layout_snapshot(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    dashboard = data_fixture.create_dashboard_application(user=user)
    deleted_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Deleted"
    )
    WidgetService().create_widget(user, "summary", dashboard.id, title="Existing")
    action_type_registry.get_by_type(DeleteWidgetActionType).do(user, deleted_widget.id)

    with (
        patch(
            "baserow.contrib.dashboard.widgets.signals.widget_created.send"
        ) as widget_created_mock,
        patch(
            "baserow.contrib.dashboard.widgets.signals.widget_deleted.send"
        ) as widget_deleted_mock,
        patch(
            "baserow.contrib.dashboard.widgets.signals.widgets_layout_updated.send"
        ) as widgets_layout_updated_mock,
    ):
        ActionHandler.undo(
            user,
            [ApplicationActionScopeType.value(application_id=dashboard.id)],
            session_id,
        )

        widget_created_mock.assert_not_called()
        widget_deleted_mock.assert_not_called()
        widgets_layout_updated_mock.assert_called_once()

        widget_created_mock.reset_mock()
        widget_deleted_mock.reset_mock()
        widgets_layout_updated_mock.reset_mock()

        ActionHandler.redo(
            user,
            [ApplicationActionScopeType.value(application_id=dashboard.id)],
            session_id,
        )

    widget_created_mock.assert_not_called()
    widget_deleted_mock.assert_not_called()
    widgets_layout_updated_mock.assert_called_once()


@pytest.mark.django_db
def test_legacy_widget_actions_use_their_pre_grid_operations():
    legacy_create_params = CreateWidgetActionType.serialized_to_params(
        {
            "dashboard_id": 1,
            "dashboard_name": "Dashboard",
            "widget_id": 2,
            "widget_title": "Widget",
            "widget_type": "summary",
        }
    )
    legacy_delete_params = DeleteWidgetActionType.serialized_to_params(
        {
            "dashboard_id": 1,
            "dashboard_name": "Dashboard",
            "widget_id": 2,
            "widget_title": "Widget",
        }
    )

    assert legacy_create_params.original_layout is None
    assert legacy_create_params.new_layout is None
    assert legacy_delete_params.original_layout is None
    assert legacy_delete_params.new_layout is None

    with patch("baserow.contrib.dashboard.widgets.actions.WidgetService") as service:
        CreateWidgetActionType.undo(None, legacy_create_params, None)
        CreateWidgetActionType.redo(None, legacy_create_params, None)
        DeleteWidgetActionType.undo(None, legacy_delete_params, None)
        DeleteWidgetActionType.redo(None, legacy_delete_params, None)

    service.return_value.delete_widget_legacy.assert_has_calls(
        [
            call(None, legacy_create_params.widget_id),
            call(None, legacy_delete_params.widget_id),
        ]
    )
    service.return_value.restore_widget_legacy.assert_has_calls(
        [
            call(None, legacy_create_params.widget_id),
            call(None, legacy_delete_params.widget_id),
        ]
    )
