import pytest

from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import WorkspaceActionScopeType
from baserow.core.subjects import UserSubjectType
from baserow_enterprise.audit_log.models import AuditLogEntry
from baserow_enterprise.role.actions import BatchAssignRoleActionType
from baserow_enterprise.role.handler import NewRoleAssignment, RoleAssignmentHandler
from baserow_enterprise.role.models import Role, RoleAssignment


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_batch_assign_role_cannot_be_undone(data_fixture, enterprise_data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    user2 = data_fixture.create_user()
    user3 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=user,
        members=[user2, user3],
    )
    database = data_fixture.create_database_application(workspace=workspace)

    table = data_fixture.create_database_table(database=database, user=user)

    team1 = enterprise_data_fixture.create_team(workspace=workspace, members=[])

    builder_role = Role.objects.get(uid="BUILDER")
    editor_role = Role.objects.get(uid="EDITOR")
    viewer_role = Role.objects.get(uid="VIEWER")

    new_role_assignments = [
        NewRoleAssignment(user2, editor_role, workspace),
        NewRoleAssignment(user2, builder_role, table),
        NewRoleAssignment(user2, viewer_role, database.application_ptr),
        NewRoleAssignment(user3, builder_role, workspace),
        NewRoleAssignment(user3, viewer_role, database.application_ptr),
        NewRoleAssignment(user3, builder_role, table),
        NewRoleAssignment(team1, viewer_role, workspace),
        NewRoleAssignment(team1, builder_role, table),
        NewRoleAssignment(team1, builder_role, database.application_ptr),
    ]

    action_type_registry.get_by_type(BatchAssignRoleActionType).do(
        user, new_role_assignments, workspace
    )

    assert RoleAssignment.objects.count() == 7

    assert AuditLogEntry.objects.count() == 1
    log_entry = AuditLogEntry.objects.first()
    assert log_entry.description.startswith("Multiple roles")

    actions_undone = ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )

    assert actions_undone == []
    assert RoleAssignment.objects.count() == 7


@pytest.mark.django_db
def test_batch_assign_role_description_for_one_item(
    data_fixture, enterprise_data_fixture
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    user2 = data_fixture.create_user()
    user3 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=user,
        members=[user2, user3],
    )

    editor_role = Role.objects.get(uid="EDITOR")

    new_role_assignments = [
        NewRoleAssignment(user2, editor_role, workspace),
    ]

    action_type_registry.get_by_type(BatchAssignRoleActionType).do(
        user, new_role_assignments, workspace
    )

    assert AuditLogEntry.objects.count() == 1
    log_entry = AuditLogEntry.objects.first()
    assert log_entry.description == (
        f'Role EDITOR assigned to subject type "User" ({user2.id}) '
        f'on scope type "workspace" ({workspace.id}).'
    )


@pytest.mark.django_db
def test_batch_assign_role_records_the_previous_role(
    data_fixture, enterprise_data_fixture
):
    user = data_fixture.create_user()
    user2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[user2])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, user=user)

    builder_role = Role.objects.get(uid="BUILDER")
    editor_role = Role.objects.get(uid="EDITOR")

    RoleAssignmentHandler().assign_role(user2, workspace, editor_role, scope=table)

    action_type_registry.get_by_type(BatchAssignRoleActionType).do(
        user, [NewRoleAssignment(user2, builder_role, table)], workspace
    )

    log_entry = AuditLogEntry.objects.get()
    assert log_entry.action_params["assignments"] == [
        [
            UserSubjectType.type,
            user2.id,
            "EDITOR",
            "BUILDER",
            "database_table",
            table.id,
        ]
    ]
