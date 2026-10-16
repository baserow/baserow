from django.urls import reverse

import pytest


@pytest.mark.django_db
@pytest.mark.workspace_search
def test_agent_search_uses_workspace_application_access(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    agent = data_fixture.create_agent_application(
        workspace=workspace, name="Search agent"
    )
    database = data_fixture.create_database_application(
        workspace=workspace, name="Search database"
    )
    data_fixture.create_agent_application(name="Search private agent")

    response = api_client.get(
        reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id}),
        {"query": "Search"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200
    assert {item["id"] for item in response.json()["results"]} == {
        agent.id,
        database.id,
    }
    result = next(item for item in response.json()["results"] if item["id"] == agent.id)
    assert result["type"] == "agent"
    assert result["subtitle"] == "Agents"
