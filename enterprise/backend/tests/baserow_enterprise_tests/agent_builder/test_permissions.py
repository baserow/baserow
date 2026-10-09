from django.urls import reverse

import pytest

from baserow.core.action.models import Action
from baserow.core.exceptions import PermissionException
from baserow.core.models import Operation
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.agent_builder.models import AgentDefinition
from baserow_enterprise.agent_builder.service import AgentService
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role

from .test_api import agent_url, agents_url, application_url


@pytest.mark.django_db
@pytest.mark.parametrize("role_uid,allowed", [("BUILDER", True), ("VIEWER", False)])
def test_default_roles_separate_reading_agents_from_configuring_agents(
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
    builder = enterprise_data_fixture.create_agent_builder_application(
        workspace=workspace
    )
    agent = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Original"
    )
    RoleAssignmentHandler().assign_role(
        member, workspace, Role.objects.get(uid=role_uid)
    )
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.get(agent_url(agent), **headers)
    assert response.status_code == 200
    assert response.json()["id"] == agent.id
    response = api_client.get(agents_url(builder), **headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [agent.id]
    response = api_client.post(
        agents_url(builder), {"name": "New"}, format="json", **headers
    )
    assert response.status_code == (200 if allowed else 401)
    response = api_client.patch(
        agent_url(agent), {"name": "Changed"}, format="json", **headers
    )
    assert response.status_code == (200 if allowed else 401)
    response = api_client.delete(agent_url(agent), **headers)
    assert response.status_code == (204 if allowed else 401)
    if not allowed:
        agent.refresh_from_db()
        assert agent.name == "Original"
        assert not agent.trashed
        assert AgentDefinition.objects.count() == 1
        assert not Action.objects.exists()


@pytest.mark.django_db
def test_child_no_access_hides_agent_from_every_serialized_application(
    enterprise_data_fixture, api_client, enable_enterprise, synced_roles
):
    owner = enterprise_data_fixture.create_user()
    member, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    builder = enterprise_data_fixture.create_agent_builder_application(
        workspace=workspace
    )
    visible = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Visible"
    )
    hidden = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Secret", order=2
    )
    handler = RoleAssignmentHandler()
    handler.assign_role(member, workspace, Role.objects.get(uid="VIEWER"))
    handler.assign_role(
        member, workspace, Role.objects.get(uid="NO_ACCESS"), scope=hidden
    )
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.get(agent_url(hidden), **headers)
    assert response.status_code == 401
    assert response.json()["error"] == "PERMISSION_DENIED"
    response = api_client.get(agents_url(builder), **headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [visible.id]
    for url in [
        application_url(builder),
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
        reverse("api:applications:list"),
    ]:
        response = api_client.get(url, **headers)
        assert response.status_code == 200
        data = response.json()
        if isinstance(data, list):
            data = next(item for item in data if item["id"] == builder.id)
        assert "agents" not in data
        assert "Secret" not in response.content.decode()


@pytest.mark.django_db
def test_child_scoped_role_grants_only_that_agent_under_restricted_parent(
    enterprise_data_fixture, api_client, enable_enterprise, synced_roles
):
    owner = enterprise_data_fixture.create_user()
    member, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    builder = enterprise_data_fixture.create_agent_builder_application(
        workspace=workspace
    )
    visible = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Granted"
    )
    hidden = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Hidden", order=2
    )
    other_builder = enterprise_data_fixture.create_agent_builder_application(
        workspace=workspace
    )
    other = enterprise_data_fixture.create_agent_definition(agent_builder=other_builder)
    handler = RoleAssignmentHandler()
    handler.assign_role(member, workspace, Role.objects.get(uid="NO_ACCESS"))
    handler.assign_role(
        member, workspace, Role.objects.get(uid="VIEWER"), scope=visible
    )
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    assert api_client.get(agent_url(visible), **headers).status_code == 200
    assert api_client.get(agent_url(hidden), **headers).status_code == 401
    assert api_client.get(agent_url(other), **headers).status_code == 401
    response = api_client.get(agents_url(builder), **headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [visible.id]
    response = api_client.get(agents_url(other_builder), **headers)
    assert response.status_code == 200
    assert response.json() == []
    assert (
        api_client.patch(
            agent_url(visible), {"name": "Changed"}, format="json", **headers
        ).status_code
        == 401
    )
    assert (
        api_client.post(
            agents_url(builder), {"name": "New"}, format="json", **headers
        ).status_code
        == 401
    )


@pytest.mark.django_db
def test_list_permission_without_read_permission_does_not_leak_agent_names(
    enterprise_data_fixture, api_client, enable_enterprise, synced_roles
):
    owner = enterprise_data_fixture.create_user()
    member, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    builder = enterprise_data_fixture.create_agent_builder_application(
        workspace=workspace
    )
    enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Secret"
    )
    role = Role.objects.create(
        uid="agent_lister", name="Agent lister", workspace=workspace
    )
    operation_names = [
        "application.read",
        "workspace.list_applications",
        "agent_builder.list_agents",
    ]
    assert Operation.objects.filter(name__in=operation_names).count() == len(
        operation_names
    )
    role.operations.set(Operation.objects.filter(name__in=operation_names))
    RoleAssignmentHandler._init = False
    RoleAssignmentHandler().assign_role(member, workspace, role)
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.get(agents_url(builder), **headers)
    assert response.status_code == 200
    assert response.json() == []
    response = api_client.get(application_url(builder), **headers)
    assert response.status_code == 200
    assert "agents" not in response.json()
    assert "Secret" not in response.content.decode()


@pytest.mark.django_db
def test_agent_restore_requires_the_child_restore_permission(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    owner = enterprise_data_fixture.create_user()
    member = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    builder = enterprise_data_fixture.create_agent_builder_application(
        workspace=workspace
    )
    agent = enterprise_data_fixture.create_agent_definition(agent_builder=builder)
    RoleAssignmentHandler().assign_role(
        member, workspace, Role.objects.get(uid="VIEWER")
    )
    AgentService().delete_agent(owner, agent.id)

    with pytest.raises(PermissionException):
        TrashHandler.restore_item(member, "agent_builder_agent", agent.id)
    assert AgentDefinition.objects_and_trash.get(id=agent.id).trashed
    restored = TrashHandler.restore_item(owner, "agent_builder_agent", agent.id)
    assert restored.id == agent.id
    assert AgentDefinition.objects.get(id=agent.id) == agent


@pytest.mark.django_db
def test_foreign_workspace_agent_list_is_empty(
    enterprise_data_fixture, api_client, enable_enterprise, synced_roles
):
    _, token = enterprise_data_fixture.create_user_and_token()
    agent = enterprise_data_fixture.create_agent_definition(name="Secret")
    response = api_client.get(
        agents_url(agent.agent_builder), HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_reorder_preserves_hidden_and_trashed_agent_positions(
    enterprise_data_fixture, api_client, enable_enterprise, synced_roles
):
    owner = enterprise_data_fixture.create_user()
    member, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    builder = enterprise_data_fixture.create_agent_builder_application(
        workspace=workspace
    )
    first = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, order=1
    )
    hidden = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, order=2
    )
    second = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, order=3
    )
    trashed = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, order=4, trashed=True
    )
    handler = RoleAssignmentHandler()
    handler.assign_role(member, workspace, Role.objects.get(uid="BUILDER"))
    handler.assign_role(
        member, workspace, Role.objects.get(uid="NO_ACCESS"), scope=hidden
    )
    response = api_client.post(
        reverse("api:agent_builder:order", kwargs={"agent_builder_id": builder.id}),
        {"agent_ids": [second.id, first.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 204
    assert list(
        AgentDefinition.objects_and_trash.filter(agent_builder=builder).values_list(
            "id", "order"
        )
    ) == [(second.id, 1), (hidden.id, 2), (first.id, 3), (trashed.id, 4)]
    response = api_client.post(
        reverse("api:agent_builder:order", kwargs={"agent_builder_id": builder.id}),
        {"agent_ids": [hidden.id, second.id, first.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_AGENT_NOT_IN_AGENT_BUILDER"
    hidden.refresh_from_db()
    assert hidden.order == 2
