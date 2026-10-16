from django.urls import reverse

import pytest

from baserow.contrib.agent.models import AgentApplication
from baserow.core.action.models import Action
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


def application_url(application):
    return reverse("api:applications:item", kwargs={"application_id": application.id})


@pytest.mark.django_db
@pytest.mark.parametrize("role_uid,allowed", [("BUILDER", True), ("VIEWER", False)])
def test_default_roles_separate_reading_and_configuring_agents(
    enterprise_data_fixture,
    api_client,
    enable_enterprise,
    synced_roles,
    role_uid,
    allowed,
):
    owner = enterprise_data_fixture.create_user()
    member, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    agent = enterprise_data_fixture.create_agent_application(
        workspace=workspace, name="Original"
    )
    RoleAssignmentHandler().assign_role(
        member, workspace, Role.objects.get(uid=role_uid)
    )
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    assert api_client.get(application_url(agent), **headers).status_code == 200
    url = reverse("api:applications:list", kwargs={"workspace_id": workspace.id})
    response = api_client.get(url, **headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [agent.id]
    response = api_client.post(
        url, {"name": "New", "type": "agent"}, format="json", **headers
    )
    assert response.status_code == (200 if allowed else 401)
    response = api_client.patch(
        application_url(agent), {"name": "Changed"}, format="json", **headers
    )
    assert response.status_code == (200 if allowed else 401)
    response = api_client.delete(application_url(agent), **headers)
    assert response.status_code == (204 if allowed else 401)
    if not allowed:
        agent.refresh_from_db()
        assert agent.name == "Original"
        assert not agent.trashed
        assert AgentApplication.objects.count() == 1
        assert not Action.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "workspace_role,agent_role", [("NO_ACCESS", "VIEWER"), ("VIEWER", "NO_ACCESS")]
)
def test_application_roles_grant_or_hide_agents_independently(
    enterprise_data_fixture,
    api_client,
    enable_enterprise,
    synced_roles,
    workspace_role,
    agent_role,
):
    owner = enterprise_data_fixture.create_user()
    member, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    first = enterprise_data_fixture.create_agent_application(
        workspace=workspace, name="First agent"
    )
    second = enterprise_data_fixture.create_agent_application(
        workspace=workspace, name="Second agent", order=1
    )
    roles = RoleAssignmentHandler()
    roles.assign_role(member, workspace, Role.objects.get(uid=workspace_role))
    assignment = roles.assign_role(
        member, workspace, Role.objects.get(uid=agent_role), scope=first.application_ptr
    )
    assert assignment.scope_type.model == "application"
    visible, hidden = (first, second) if agent_role == "VIEWER" else (second, first)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    assert api_client.get(application_url(visible), **headers).status_code == 200
    assert api_client.get(application_url(hidden), **headers).status_code == 401
    for url in [
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
        reverse("api:applications:list"),
    ]:
        response = api_client.get(url, **headers)
        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [visible.id]
        assert hidden.name not in response.content.decode()
    assert (
        api_client.patch(
            application_url(visible), {"name": "Changed"}, format="json", **headers
        ).status_code
        == 401
    )


@pytest.mark.django_db
def test_agent_restore_requires_application_restore_permission(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    owner = enterprise_data_fixture.create_user()
    member = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    agent = enterprise_data_fixture.create_agent_application(workspace=workspace)
    RoleAssignmentHandler().assign_role(
        member, workspace, Role.objects.get(uid="VIEWER")
    )
    CoreHandler().delete_application(owner, agent)
    with pytest.raises(PermissionException):
        TrashHandler.restore_item(member, "application", agent.id)
    assert AgentApplication.objects_and_trash.get(id=agent.id).trashed


@pytest.mark.django_db
def test_application_builder_role_edits_only_assigned_agent(
    enterprise_data_fixture, api_client, enable_enterprise, synced_roles
):
    owner = enterprise_data_fixture.create_user()
    member, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    granted = enterprise_data_fixture.create_agent_application(
        workspace=workspace, name="Granted"
    )
    hidden = enterprise_data_fixture.create_agent_application(
        workspace=workspace, name="Secret"
    )
    roles = RoleAssignmentHandler()
    roles.assign_role(member, workspace, Role.objects.get(uid="NO_ACCESS"))
    roles.assign_role(
        member,
        workspace,
        Role.objects.get(uid="BUILDER"),
        scope=granted.application_ptr,
    )
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.patch(
        application_url(granted), {"name": "Changed"}, format="json", **headers
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Changed"
    assert (
        api_client.patch(
            application_url(hidden), {"name": "Changed"}, format="json", **headers
        ).status_code
        == 401
    )
    assert api_client.delete(application_url(granted), **headers).status_code == 204
    assert not AgentApplication.objects.filter(id=granted.id).exists()
    assert AgentApplication.objects.get(id=hidden.id).name == "Secret"


@pytest.mark.django_db
def test_agent_duplication_requires_application_permission(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    owner = enterprise_data_fixture.create_user()
    member = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    agent = enterprise_data_fixture.create_agent_application(workspace=workspace)
    RoleAssignmentHandler().assign_role(
        member,
        workspace,
        Role.objects.get(uid="NO_ACCESS"),
        scope=agent.application_ptr,
    )
    with pytest.raises(PermissionException):
        CoreHandler().duplicate_application(member, agent)
    assert AgentApplication.objects.count() == 1
