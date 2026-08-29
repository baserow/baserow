from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_application.handler import AgentApplicationHandler


@pytest.fixture
def agent_application(data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    return user, token, application


@pytest.mark.django_db
def test_get_agent_definition(api_client, agent_application):
    user, token, application = agent_application

    url = reverse(
        "api:agent:agent",
        kwargs={"application_id": application.id},
    )
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    assert response.json()["name"] == "Agent"
    assert response.json()["application_id"] == application.id


@pytest.mark.django_db
def test_get_agent_definition_without_access(
    api_client, data_fixture, agent_application
):
    _, _, application = agent_application
    _, other_token = data_fixture.create_user_and_token()

    url = reverse(
        "api:agent:agent",
        kwargs={"application_id": application.id},
    )
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {other_token}")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_update_agent_definition(api_client, agent_application):
    user, token, application = agent_application
    agent = AgentApplicationHandler().get_main_agent(application)

    url = reverse(
        "api:agent:agent_item",
        kwargs={"agent_id": agent.id},
    )
    response = api_client.patch(
        url,
        {
            "instructions": "Prioritize the roadmap.",
            "ai_generative_ai_type": "openai",
            "ai_generative_ai_model": "gpt-test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    agent.refresh_from_db()
    assert agent.instructions == "Prioritize the roadmap."
    assert agent.ai_generative_ai_model == "gpt-test"


@pytest.mark.django_db
def test_update_unknown_agent_definition(api_client, agent_application):
    _, token, _ = agent_application

    url = reverse(
        "api:agent:agent_item",
        kwargs={"agent_id": 0},
    )
    response = api_client.patch(
        url, {"name": "x"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_AGENT_DEFINITION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_partial_update_does_not_null_omitted_fields(api_client, agent_application):
    user, token, application = agent_application
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent,
        instructions="Keep me.",
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-test",
        ai_temperature=0.3,
    )

    url = reverse(
        "api:agent:agent_item",
        kwargs={"agent_id": agent.id},
    )
    response = api_client.patch(
        url, {"name": "Renamed"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    agent.refresh_from_db()
    assert agent.name == "Renamed"
    # Omitted fields must survive a partial update.
    assert agent.instructions == "Keep me."
    assert agent.ai_generative_ai_type == "openai"
    assert agent.ai_generative_ai_model == "gpt-test"
    assert agent.ai_temperature == 0.3


@pytest.mark.django_db
def test_create_agent_application_via_core_endpoint(api_client, data_fixture):
    """
    Creating through the polymorphic application serializer maps the raw
    request dict through the serializer fields during validation; the
    pending approvals count field must tolerate that.
    """

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        f"/api/applications/workspace/{workspace.id}/",
        {
            "name": "Company finder",
            "type": "agent",
            "init_with_data": True,
            "description": "Find startups.",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    data = response.json()
    assert data["type"] == "agent"
    assert data["description"] == "Find startups."
    assert data["pending_approvals_count"] == 0
