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
@pytest.mark.parametrize("sorts", [None, "+name", "-name"])
def test_agent_pagination_with_duplicate_names(data_fixture, api_client, sorts):
    """Tied names must have stable ordering across page boundaries."""

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    agents = Agent.objects.bulk_create(
        [Agent(workspace=workspace, name=f"Agent {i % 3}") for i in range(400)]
    )
    expected = sorted(agents, key=lambda agent: agent.id)
    if sorts:
        expected.sort(key=lambda agent: agent.name, reverse=sorts == "-name")

    url = reverse("api:agents:workspace", kwargs={"workspace_id": workspace.id})
    result_ids = []
    for page in range(1, 5):
        params = {"page": page, "size": 100}
        if sorts:
            params["sorts"] = sorts
        response = api_client.get(url, params, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == 200
        assert response.json()["count"] == 400
        result_ids.extend(agent["id"] for agent in response.json()["results"])

    assert result_ids == [agent.id for agent in expected]
    assert len(set(result_ids)) == 400


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
@pytest.mark.parametrize("method", ["post", "patch", "delete"])
def test_nonmember_agent_mutations_return_user_not_in_workspace(
    data_fixture, api_client, method
):
    """All Agent mutations expose the standard workspace-membership API error."""

    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    agent = Agent.objects.create(workspace=workspace, name="Writer")
    _, token = data_fixture.create_user_and_token()
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    workspace_url = reverse(
        "api:agents:workspace", kwargs={"workspace_id": workspace.id}
    )
    agent_url = reverse("api:agents:item", kwargs={"agent_id": agent.id})

    if method == "post":
        response = api_client.post(
            workspace_url, {"name": "Denied"}, format="json", **headers
        )
    elif method == "patch":
        response = api_client.patch(
            agent_url, {"name": "Denied"}, format="json", **headers
        )
    else:
        response = api_client.delete(agent_url, **headers)

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    assert list(
        Agent.objects.filter(workspace=workspace).values_list("name", flat=True)
    ) == ["Writer"]


def test_agent_list_openapi_schema_matches_paginated_response(api_client):
    """The published list contract includes pagination, filters, and team summaries."""

    schema = api_client.get(reverse("api:json_schema")).json()
    operation = schema["paths"]["/api/agents/workspace/{workspace_id}/"]["get"]
    assert {parameter["name"] for parameter in operation["parameters"]} == {
        "workspace_id",
        "page",
        "size",
        "search",
        "sorts",
    }

    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    components = schema["components"]["schemas"]
    pagination = components[response_schema["$ref"].split("/")[-1]]
    assert set(pagination["properties"]) == {
        "count",
        "next",
        "previous",
        "results",
    }

    agent_ref = pagination["properties"]["results"]["items"]["$ref"]
    agent_schema = components[agent_ref.split("/")[-1]]
    teams_schema = agent_schema["properties"]["teams"]
    assert teams_schema["type"] == "array"
    team_ref = teams_schema["items"]["$ref"]
    assert set(components[team_ref.split("/")[-1]]["properties"]) == {"id", "name"}


def test_agent_openapi_operations_have_stable_ids_and_explicit_path_parameters(
    api_client,
):
    """Agent client operations have stable names and typed path parameters."""

    schema = api_client.get(reverse("api:json_schema")).json()
    operations = [
        (
            "/api/agents/workspace/{workspace_id}/",
            "get",
            "list_workspace_agents",
            "workspace_id",
        ),
        (
            "/api/agents/workspace/{workspace_id}/",
            "post",
            "create_workspace_agent",
            "workspace_id",
        ),
        ("/api/agents/{agent_id}/", "patch", "update_agent", "agent_id"),
        ("/api/agents/{agent_id}/", "delete", "delete_agent", "agent_id"),
    ]

    for path, method, operation_id, parameter_name in operations:
        operation = schema["paths"][path][method]
        assert operation["operationId"] == operation_id
        path_parameters = [
            parameter
            for parameter in operation["parameters"]
            if parameter["in"] == "path"
        ]
        assert len(path_parameters) == 1
        assert path_parameters[0]["name"] == parameter_name
        assert path_parameters[0]["schema"]["type"] == "integer"


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
