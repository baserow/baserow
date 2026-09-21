from django.urls import reverse

import pytest

from baserow.core.agents.service import AgentService
from baserow.core.models import Agent, Operation
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.teams.models import TeamSubject
from baserow_enterprise.teams.operations import (
    CreateTeamSubjectOperationType,
    DeleteTeamSubjectOperationType,
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action,can_add,can_remove,allowed",
    [
        ("create", False, False, False),
        ("create", True, False, True),
        ("replace", False, False, False),
        ("replace", True, False, False),
        ("replace", False, True, False),
        ("replace", True, True, True),
        ("retain", False, False, True),
        ("omit", False, False, True),
    ],
)
def test_agent_team_changes_require_membership_permissions(
    data_fixture,
    enterprise_data_fixture,
    api_client,
    enable_enterprise,
    synced_roles,
    action,
    can_add,
    can_remove,
    allowed,
):
    """Agent permissions alone cannot grant team access; denied requests roll back."""

    admin = data_fixture.create_user()
    editor, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin, members=[editor])
    old_team = enterprise_data_fixture.create_team(workspace=workspace)
    new_team = enterprise_data_fixture.create_team(workspace=workspace)
    agent = AgentService().create_agent(
        admin, workspace, name="Original", team_ids=[old_team.id]
    )
    old_membership = TeamSubject.objects.get(team=old_team, subject_id=agent.id)

    role = Role.objects.create(
        uid="agent_editor", name="Agent editor", workspace=workspace
    )
    operations = ["agent.create", "agent.update"]
    if can_add:
        operations.append(CreateTeamSubjectOperationType.type)
    if can_remove:
        operations.append(DeleteTeamSubjectOperationType.type)
    role.operations.set(Operation.objects.filter(name__in=operations))
    RoleAssignmentHandler._init = False
    RoleAssignmentHandler().assign_role(editor, workspace, role)

    payload = {"name": "Changed"}
    if action != "omit":
        payload["team_ids"] = [old_team.id if action == "retain" else new_team.id]
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    if action == "create":
        url = reverse("api:agents:workspace", kwargs={"workspace_id": workspace.id})
        response = api_client.post(url, payload, format="json", **headers)
    else:
        url = reverse("api:agents:item", kwargs={"agent_id": agent.id})
        response = api_client.patch(url, payload, format="json", **headers)

    assert response.status_code == (200 if allowed else 401)
    agent.refresh_from_db()
    if not allowed:
        assert agent.name == "Original"
        assert list(Agent.objects.filter(workspace=workspace)) == [agent]
        assert list(TeamSubject.objects.filter(team__workspace=workspace)) == [
            old_membership
        ]
    elif action == "create":
        created = Agent.objects.get(id=response.json()["id"])
        assert created.name == "Changed"
        assert TeamSubject.objects.get(team=new_team).subject_id == created.id
        assert TeamSubject.objects.filter(id=old_membership.id).exists()
    else:
        assert agent.name == "Changed"
        memberships = TeamSubject.objects.filter(subject_id=agent.id)
        assert list(memberships.values_list("team_id", flat=True)) == [
            new_team.id if action == "replace" else old_team.id
        ]
