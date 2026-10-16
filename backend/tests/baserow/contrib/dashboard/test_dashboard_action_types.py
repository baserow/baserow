import pytest

from baserow.contrib.dashboard.actions import RotateDashboardSlugActionType
from baserow.contrib.dashboard.models import Dashboard
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import (
    ApplicationActionScopeType,
    WorkspaceActionScopeType,
)
from baserow.core.actions import UpdateApplicationActionType
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_update_dashboard_application(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, name="Dashboard 1", description="Description 1", user=user
    )

    # update dashboard description
    action_type_registry.get_by_type(UpdateApplicationActionType).do(
        user, dashboard, name="Updated name", description="Updated description"
    )

    dashboard.refresh_from_db()
    assert dashboard.name == "Updated name"
    assert dashboard.description == "Updated description"

    # undo
    ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    dashboard.refresh_from_db()
    assert dashboard.name == "Dashboard 1"
    assert dashboard.description == "Description 1"

    # redo
    actions_redone = ActionHandler.redo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_redone, [UpdateApplicationActionType])

    dashboard.refresh_from_db()
    assert dashboard.name == "Updated name"
    assert dashboard.description == "Updated description"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_rotate_dashboard_slug(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    dashboard = data_fixture.create_dashboard_application(user=user, public=True)
    original_slug = dashboard.slug

    dashboard = action_type_registry.get_by_type(RotateDashboardSlugActionType).do(
        user, dashboard.id
    )
    rotated_slug = dashboard.slug
    assert rotated_slug != original_slug

    ActionHandler.undo(
        user, [ApplicationActionScopeType.value(dashboard.id)], session_id
    )

    dashboard.refresh_from_db()
    assert dashboard.slug == original_slug

    actions_redone = ActionHandler.redo(
        user, [ApplicationActionScopeType.value(dashboard.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_redone, [RotateDashboardSlugActionType])

    dashboard.refresh_from_db()
    assert dashboard.slug == rotated_slug


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_update_dashboard_public_password(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, user=user
    )

    action_type_registry.get_by_type(UpdateApplicationActionType).do(
        user,
        dashboard,
        public=True,
        public_password=Dashboard.make_password("secret-password"),
    )

    dashboard.refresh_from_db()
    assert dashboard.public is True
    assert dashboard.check_public_password("secret-password")

    ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    dashboard.refresh_from_db()
    assert dashboard.public is False
    assert dashboard.public_password == ""

    ActionHandler.redo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    dashboard.refresh_from_db()
    assert dashboard.public is True
    assert dashboard.check_public_password("secret-password")
