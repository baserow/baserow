import pytest

from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import (
    action_scope_registry,
    action_type_registry,
)
from baserow.core.action.scopes import (
    AllWorkspacesActionScopeType,
    RootActionScopeType,
    WorkspaceActionScopeType,
)
from baserow.core.actions import UpdateApplicationActionType


@pytest.mark.django_db
def test_all_workspaces_scope_resolves_to_the_workspaces_of_the_user(data_fixture):
    user = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user)
    data_fixture.create_workspace()

    resolved = action_scope_registry.resolve(
        user, [RootActionScopeType.value(), AllWorkspacesActionScopeType.value()]
    )

    assert resolved == [
        RootActionScopeType.value(),
        WorkspaceActionScopeType.value(workspace_1.id),
        WorkspaceActionScopeType.value(workspace_2.id),
    ]


@pytest.mark.django_db
def test_scopes_of_other_types_resolve_to_themselves(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    scopes = [RootActionScopeType.value(), WorkspaceActionScopeType.value(workspace.id)]

    assert action_scope_registry.resolve(user, scopes) == scopes


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_application_action_is_undoable_from_all_workspaces_and_its_own_workspace(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(
        workspace=workspace_1, name="Before"
    )

    def rename():
        action_type_registry.get_by_type(UpdateApplicationActionType).do(
            user, application, name="After"
        )

    rename()
    # Looking at another workspace never sees it.
    assert (
        ActionHandler.undo(
            user, [WorkspaceActionScopeType.value(workspace_2.id)], session_id
        )
        == []
    )
    # The all workspaces homepage does.
    undone = ActionHandler.undo(
        user, [AllWorkspacesActionScopeType.value()], session_id
    )
    assert [action.type for action in undone] == [UpdateApplicationActionType.type]
    application.refresh_from_db()
    assert application.name == "Before"

    # And so does its own workspace, after redoing it from the homepage.
    ActionHandler.redo(user, [AllWorkspacesActionScopeType.value()], session_id)
    application.refresh_from_db()
    assert application.name == "After"
    undone = ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_1.id)], session_id
    )
    assert [action.type for action in undone] == [UpdateApplicationActionType.type]
    application.refresh_from_db()
    assert application.name == "Before"
