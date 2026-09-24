import pytest

from baserow.core.models import Agent
from baserow.core.registries import subject_type_registry
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import RoleAssignment


@pytest.mark.django_db
def test_workspace_roles_for_mixed_subject_types(
    data_fixture, enterprise_data_fixture, enable_enterprise, synced_roles
):
    """The same handler supports canonical and record-backed workspace roles."""
    admin = data_fixture.create_user()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[user])
    agent = Agent.objects.create(workspace=workspace, name="Writer")
    team = enterprise_data_fixture.create_team(workspace=workspace)
    subjects = [user, agent, team]
    handler = RoleAssignmentHandler()
    viewer = handler.get_role_by_uid("VIEWER")
    for subject in subjects:
        assignment = handler.assign_role(subject, workspace, viewer)
        assert assignment.subject == subject
        assert assignment.role == viewer

    assignments = handler.get_current_role_assignments(
        workspace, [(subject, workspace) for subject in subjects]
    )
    assert all(assignments[(subject, workspace)].role == viewer for subject in subjects)
    listed = {
        assignment.subject: assignment.role
        for assignment in handler.get_role_assignments(workspace, workspace)
    }
    assert all(listed[subject] == viewer for subject in subjects)
    assert RoleAssignment.objects.get().subject == team

    for subject in subjects:
        handler.remove_role(subject, workspace)
        assignment = handler.get_current_role_assignment(subject, workspace)
        if subject_type_registry.get_by_model(subject).has_direct_workspace_roles:
            assert assignment.role.uid == "NO_ACCESS"
        else:
            assert assignment is None
    assert not RoleAssignment.objects.exists()
