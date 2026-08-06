from django.urls import reverse

import pytest

from baserow.core.agents.service import AgentService
from baserow.core.models import Agent, WorkspaceUser
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_admin_can_crud_search_and_soft_delete_agents(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    url = reverse("api:agents:workspace", kwargs={"workspace_id": workspace.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.post(
        url, {"name": "Writer", "role_uid": "MEMBER"}, format="json", **headers
    )
    assert response.status_code == 200
    agent_id = response.json()["id"]
    assert response.json()["last_active"] is None

    api_client.post(url, {"name": "Other"}, format="json", **headers)
    response = api_client.get(f"{url}?search=Writer&sorts=%2Bname", **headers)
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["name"] == "Writer"

    item_url = reverse("api:agents:item", kwargs={"agent_id": agent_id})
    response = api_client.patch(
        item_url, {"name": "Writer 2"}, format="json", **headers
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Writer 2"

    assert api_client.delete(item_url, **headers).status_code == 204
    assert not Agent.objects.filter(id=agent_id).exists()
    assert Agent.objects_and_trash.filter(id=agent_id, trashed=True).exists()


@pytest.mark.django_db
def test_member_can_list_but_cannot_mutate_agents(data_fixture, api_client):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    member, token = data_fixture.create_user_and_token()
    WorkspaceUser.objects.create(
        user=member, workspace=workspace, permissions="MEMBER", order=0
    )
    Agent.objects.create(workspace=workspace, name="Visible")
    url = reverse("api:agents:workspace", kwargs={"workspace_id": workspace.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    assert api_client.get(url, **headers).status_code == 200
    assert (
        api_client.post(url, {"name": "Denied"}, format="json", **headers).status_code
        == 401
    )


@pytest.mark.django_db
def test_cannot_create_agent_when_feature_flag_is_disabled(
    data_fixture, api_client, settings
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    url = reverse("api:agents:workspace", kwargs={"workspace_id": workspace.id})
    settings.FEATURE_FLAGS = []

    response = api_client.post(
        url,
        {"name": "Writer", "role_uid": "MEMBER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 403
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"
    assert not Agent.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db
def test_duplicate_agent_names_and_model_defaults(data_fixture):
    workspace = data_fixture.create_workspace()
    first = Agent.objects.create(workspace=workspace, name="Same")
    second = Agent.objects.create(workspace=workspace, name="Same")

    assert first.role_uid == "MEMBER"
    assert first.last_active is None
    assert first.id != second.id


@pytest.mark.django_db
def test_admin_can_restore_agent(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = Agent.objects.create(workspace=workspace, name="Writer")

    AgentService().delete_agent(user, agent)
    restored_agent = TrashHandler.restore_item(user, "agent", agent.id)

    assert restored_agent == agent
    assert Agent.objects.filter(id=agent.id).exists()
