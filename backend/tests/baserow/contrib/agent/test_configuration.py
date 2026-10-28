from django.urls import reverse

import pytest

from baserow.api.applications.serializers import (
    PolymorphicApplicationResponseSerializer,
)
from baserow.contrib.agent.actions import UpdateAgentConfigurationActionType
from baserow.contrib.agent.handler import AgentHandler
from baserow.core.ai_provider.resolution import (
    clear_ai_provider_state_cache,
    load_ai_provider_state,
)
from baserow.core.models import Agent

from .utils import agent_url


@pytest.mark.django_db
@pytest.mark.parametrize(
    "values,readiness,errors",
    [
        ({}, "ready", {}),
        ({"instructions": " "}, "incomplete", {"instructions": "required"}),
        ({"provider_type": None}, "incomplete", {"provider_type": "required"}),
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
def test_configuration_reports_missing_and_unavailable_fields(
    configured_agent, values, readiness, errors
):
    configuration = AgentHandler().get_configuration(configured_agent(**values))

    assert (configuration["readiness"], configuration["errors"]) == (
        readiness,
        errors,
    )


@pytest.mark.django_db
@pytest.mark.parametrize("workspace_count", [1, 5])
def test_application_readiness_uses_bulk_provider_state(
    configured_agent, django_assert_num_queries, workspace_count
):
    agents = []
    for _ in range(workspace_count):
        ready = configured_agent()
        agents.extend(
            [
                ready,
                configured_agent(workspace=ready.workspace, instructions=""),
                configured_agent(
                    workspace=ready.workspace, model_identifier="unavailable-model"
                ),
            ]
        )
    clear_ai_provider_state_cache()

    # The provider/model/override/feature-setting load is fixed, and serializing
    # readiness must not fetch provider state again for any Agent or workspace.
    with django_assert_num_queries(4):
        provider_states = load_ai_provider_state(agent.workspace for agent in agents)
        payload = PolymorphicApplicationResponseSerializer(
            agents, many=True, context={"ai_provider_states": provider_states}
        ).data

    assert [agent["readiness"] for agent in payload] == [
        "ready",
        "incomplete",
        "unavailable",
    ] * workspace_count


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
    "values,error_field,error_code",
    [
        pytest.param(
            {"instructions": "x" * 100001},
            "instructions",
            "max_length",
            id="instructions-too-long",
        ),
        pytest.param(
            {"provider_type": "x" * 256},
            "provider_type",
            "max_length",
            id="provider-too-long",
        ),
        pytest.param(
            {"model_identifier": "x" * 256},
            "model_identifier",
            "max_length",
            id="model-too-long",
        ),
        pytest.param(
            {"model_identifier": {}},
            "model_identifier",
            "invalid",
            id="model-object",
        ),
        pytest.param(
            {"model_identifier": []},
            "model_identifier",
            "invalid",
            id="model-list",
        ),
        pytest.param(
            {"instructions": None},
            "instructions",
            "null",
            id="instructions-null",
        ),
        pytest.param(
            {"unknown": "value"},
            "non_field_errors",
            "invalid",
            id="unknown-field",
        ),
    ],
)
def test_configuration_update_rejects_invalid_values(
    configured_agent, api_client, api_user, values, error_field, error_code
):
    agent = configured_agent(user=api_user)
    original = (agent.instructions, agent.provider_type, agent.model_identifier)

    response = api_client.patch(
        agent_url(agent, "configuration"),
        {"instructions": "Changed", "provider_type": "anthropic", **values},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert payload["detail"][error_field][0]["code"] == error_code

    agent.refresh_from_db()
    assert (agent.instructions, agent.provider_type, agent.model_identifier) == original


@pytest.mark.django_db
def test_run_as_identity_is_set_reported_and_cleared(
    configured_agent, api_client, api_user
):
    agent = configured_agent(user=api_user)
    identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
    url = agent_url(agent, "configuration")
    run_as = {"type": "core.Agent", "id": identity.id, "name": "Investor"}

    response = api_client.patch(
        url, {"run_as_subject_type": "core.Agent", "run_as_subject_id": identity.id}
    )
    assert response.json()["run_as"] == {**run_as, "trashed": False}

    identity.trashed = True
    identity.save()
    assert api_client.get(url).json()["run_as"] == {**run_as, "trashed": True}

    identity.delete()
    assert api_client.get(url).json()["run_as"] is None

    response = api_client.patch(
        url, {"run_as_subject_type": None, "run_as_subject_id": None}
    )
    agent.refresh_from_db()
    assert (response.status_code, agent.run_as_subject_id) == (200, None)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "case,error",
    [
        ("other-workspace", "ERROR_AGENT_RUN_AS_SUBJECT_DOES_NOT_EXIST"),
        ("trashed", "ERROR_AGENT_RUN_AS_SUBJECT_DOES_NOT_EXIST"),
        ("user", "ERROR_REQUEST_BODY_VALIDATION"),
        ("id-only", "ERROR_REQUEST_BODY_VALIDATION"),
    ],
)
def test_run_as_rejects_subjects_the_agent_cannot_act_as(
    data_fixture, configured_agent, api_client, api_user, case, error
):
    agent = configured_agent(user=api_user)
    identity = Agent.objects.create(
        workspace=(
            data_fixture.create_workspace()
            if case == "other-workspace"
            else agent.workspace
        ),
        name="Investor",
        trashed=case == "trashed",
    )
    values = (
        {"run_as_subject_type": "auth.User", "run_as_subject_id": api_user.id}
        if case == "user"
        else {"run_as_subject_type": "core.Agent", "run_as_subject_id": identity.id}
    )
    if case == "id-only":
        del values["run_as_subject_type"]

    response = api_client.patch(agent_url(agent, "configuration"), values)

    assert (response.status_code, response.json()["error"]) == (400, error)
    agent.refresh_from_db()
    assert agent.run_as_subject_id is None


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", ["agent", "workspace"])
def test_agent_payload_includes_only_public_readiness(
    configured_agent, api_client, api_user, endpoint
):
    agent = configured_agent(user=api_user, instructions=" ")
    url = (
        agent_url(agent, "item")
        if endpoint == "agent"
        else reverse(
            "api:applications:list", kwargs={"workspace_id": agent.workspace_id}
        )
    )

    payload = api_client.get(url).json()

    if endpoint == "workspace":
        [payload] = payload
    assert payload["readiness"] == "incomplete"
    assert not {
        "instructions",
        "provider_type",
        "model_identifier",
        "errors",
    }.intersection(payload)


@pytest.mark.django_db
def test_configuration_is_served_only_by_the_agent_endpoints(
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
    application_response = api_client.patch(
        application_url, {"instructions": "Ignored", "readiness": "unavailable"}
    )

    configuration = {
        "readiness": "ready",
        "instructions": "PRIVATE",
        "provider_type": "openai",
        "model_identifier": "test-model",
        "run_as": None,
        "errors": {},
    }
    assert response.json() == configuration
    assert api_client.get(agent_url(agent, "configuration")).json() == configuration
    assert application_response.json()["readiness"] == "ready"
    assert broadcast.call_args.args[4]["type"] == "application_updated"
    assert broadcast.call_args.args[4]["application"]["readiness"] == "ready"
    assert "PRIVATE" not in str(broadcast.call_args)
    assert "PRIVATE" not in api_client.get(application_url).content.decode()
    assert api_client.get(agent_url(database, "configuration")).status_code == 404
