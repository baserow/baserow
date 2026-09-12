from unittest.mock import patch

import pytest

from baserow.contrib.dashboard.widgets.actions import UpdateWidgetLayoutActionType
from baserow.contrib.dashboard.widgets.layout import WidgetLayoutHandler
from baserow.contrib.dashboard.widgets.operations import (
    ListWidgetsOperationType,
    UpdateWidgetLayoutOperationType,
)
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.core.action.handler import ActionHandler
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.exceptions import PermissionException
from baserow.test_utils.helpers import (
    assert_undo_redo_actions_are_valid,
    assert_undo_redo_actions_fails_with_error,
)


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("command", ["undo", "redo"])
@pytest.mark.parametrize("hide_all", [False, True])
def test_layout_replay_preserves_newly_hidden_widgets(
    data_fixture, stub_check_permissions, command, hide_all
):
    user = data_fixture.create_user(session_id="layout-session")
    dashboard = data_fixture.create_dashboard_application(user=user)
    widgets = [
        WidgetService().create_widget(user, "summary", dashboard.id, title=title)
        for title in ("First", "Second")
    ]
    original = WidgetLayoutHandler(widgets).current_layout
    UpdateWidgetLayoutActionType.do(
        user, dashboard.id, [{**item, "grid_height": 5} for item in original]
    )
    scopes = [ApplicationActionScopeType.value(dashboard.id)]
    if command == "redo":
        ActionHandler.undo(user, scopes, "layout-session")

    for widget in widgets:
        widget.refresh_from_db()
    before = WidgetLayoutHandler(widgets).current_layout
    hidden_ids = {widget.id for widget in widgets} if hide_all else {widgets[1].id}
    hidden_updated_on = widgets[1].updated_on

    def filter_visible(actor, operation_name, queryset, workspace=None, context=None):
        assert operation_name == ListWidgetsOperationType.type
        assert workspace == dashboard.workspace
        return queryset.exclude(id__in=hidden_ids)

    with (
        stub_check_permissions() as stub,
        patch(
            "baserow.contrib.dashboard.widgets.service.widgets_layout_updated.send"
        ) as layout_signal,
    ):
        stub.filter_queryset = filter_visible
        actions = getattr(ActionHandler, command)(user, scopes, "layout-session")

    assert_undo_redo_actions_are_valid(actions, [UpdateWidgetLayoutActionType])
    for widget in widgets:
        widget.refresh_from_db()
    expected = [
        item
        if item["id"] in hidden_ids
        else {**item, "grid_height": 4 if command == "undo" else 5}
        for item in before
    ]
    assert WidgetLayoutHandler(widgets).current_layout == expected
    assert widgets[1].updated_on == hidden_updated_on
    assert layout_signal.call_count == (0 if hide_all else 1)


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.parametrize("command", ["undo", "redo"])
@pytest.mark.parametrize(
    "denied_operation",
    [ListWidgetsOperationType.type, UpdateWidgetLayoutOperationType.type],
)
def test_layout_replay_rechecks_permissions(
    data_fixture, stub_check_permissions, command, denied_operation
):
    user = data_fixture.create_user(session_id="layout-session")
    dashboard = data_fixture.create_dashboard_application(user=user)
    widget = WidgetService().create_widget(user, "summary", dashboard.id, title="First")
    UpdateWidgetLayoutActionType.do(
        user,
        dashboard.id,
        [{**WidgetLayoutHandler.from_widget(widget), "grid_height": 5}],
    )
    scopes = [ApplicationActionScopeType.value(dashboard.id)]
    if command == "redo":
        ActionHandler.undo(user, scopes, "layout-session")
    widget.refresh_from_db()
    before = WidgetLayoutHandler.from_widget(widget)
    before_updated_on = widget.updated_on

    def check_permissions(checks, workspace=None, include_trash=False):
        return {
            check: PermissionException()
            if check.operation_name == denied_operation
            else True
            for check in checks
        }

    with stub_check_permissions() as stub:
        stub.check_multiple_permissions = check_permissions
        actions = getattr(ActionHandler, command)(user, scopes, "layout-session")

    assert_undo_redo_actions_fails_with_error(actions, [UpdateWidgetLayoutActionType])
    assert "PermissionException" in actions[0].error
    widget.refresh_from_db()
    assert WidgetLayoutHandler.from_widget(widget) == before
    assert widget.updated_on == before_updated_on
