from django.urls import reverse

import pytest
from rest_framework.exceptions import ValidationError

from baserow.contrib.agent.actions import UpdateAgentConfigurationActionType
from baserow.contrib.agent.handler import AgentHandler


def agent_url(agent, view, **kwargs):
    return reverse(f"api:agent:{view}", kwargs={"agent_id": agent.id, **kwargs})


@pytest.mark.django_db
@pytest.mark.parametrize(
    "values,state,errors",
    [
        ({}, "ready", {}),
        ({"instructions": " "}, "incomplete", {"instructions": "required"}),
        (
            {"model_identifier": "other-model"},
            "unavailable",
            {"model_identifier": "unavailable"},
        ),
        (
            {"provider_type": "anthropic"},
            "unavailable",
            {"provider_type": "unavailable", "model_identifier": "unavailable"},
        ),
    ],
)
def test_configuration_reports_missing_and_unavailable_settings(
    configured_agent, values, state, errors
):
    configuration = AgentHandler().get_configuration(configured_agent(**values))

    assert (configuration["state"], configuration["errors"]) == (state, errors)


@pytest.mark.django_db
def test_configuration_update_saves_drafts_and_records_changed_field_names(
    data_fixture, mocker
):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)
    registered = mocker.spy(
        UpdateAgentConfigurationActionType, "send_action_done_signal"
    )

    UpdateAgentConfigurationActionType.do(
        user, agent.id, instructions="Line 1\nLine 2", provider_type=" "
    )
    UpdateAgentConfigurationActionType.do(user, agent.id, instructions="Line 1\nLine 2")

    agent.refresh_from_db()
    assert (agent.instructions, agent.provider_type) == ("Line 1\nLine 2", None)
    registered.assert_called_once()
    assert registered.call_args.args[1] == {
        "agent_id": agent.id,
        "changed_fields": ["instructions"],
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "values",
    [
        {"name": " "},
        {"instructions": "x" * 100001},
        {"provider_type": "x" * 256},
        {"model_identifier": 12},
    ],
)
def test_configuration_update_rejects_invalid_values(configured_agent, values):
    agent = configured_agent()

    with pytest.raises(ValidationError):
        AgentHandler().update_configuration(agent, **values)

    agent.refresh_from_db()
    assert AgentHandler().get_configuration(agent)["state"] == "ready"


@pytest.mark.django_db
def test_settings_are_served_only_by_the_agent_endpoints(
    data_fixture,
    configured_agent,
    api_client,
    api_user,
    mocker,
    django_capture_on_commit_callbacks,
):
    agent = configured_agent(user=api_user)
    database = data_fixture.create_database_application(workspace=agent.workspace)
    broadcast = mocker.patch("baserow.ws.signals.broadcast_to_permitted_users.delay")
    application_url = reverse(
        "api:applications:item", kwargs={"application_id": agent.id}
    )

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.patch(
            agent_url(agent, "configuration"), {"instructions": "PRIVATE"}
        )
    api_client.patch(application_url, {"instructions": "Ignored"})

    assert response.json()["instructions"] == "PRIVATE"
    assert api_client.get(agent_url(agent, "readiness")).json() == {"state": "ready"}
    assert broadcast.call_args.args[4]["type"] == "application_updated"
    assert "PRIVATE" not in str(broadcast.call_args)
    assert "PRIVATE" not in api_client.get(application_url).content.decode()
    agent.refresh_from_db()
    assert agent.instructions == "PRIVATE"
    assert api_client.get(agent_url(database, "configuration")).status_code == 404
