import json
from dataclasses import asdict
from unittest.mock import ANY

from django.db import DEFAULT_DB_ALIAS
from django.urls import reverse

import pytest
from freezegun import freeze_time

from baserow.api.applications.serializers import (
    PolymorphicApplicationResponseSerializer,
)
from baserow.contrib.agent.actions import UpdateAgentConfigurationActionType
from baserow.contrib.agent.api.serializers import AgentConfigurationSerializer
from baserow.contrib.agent.constants import (
    AgentConfigurationErrorCode,
    AgentReadinessState,
    AgentRunAsState,
)
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.types import AgentConfiguration
from baserow.core.action.registries import action_type_registry
from baserow.core.agents.subjects import AgentSubjectType
from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel
from baserow.core.ai_provider.resolution import (
    clear_ai_provider_state_cache,
    load_ai_provider_state,
)
from baserow.core.models import Agent
from baserow.core.signals import application_updated

from .utils import agent_url


@pytest.mark.django_db
@pytest.mark.parametrize(
    "values,readiness,errors",
    [
        ({}, AgentReadinessState.READY, {}),
        (
            {"instructions": " "},
            AgentReadinessState.INCOMPLETE,
            {"instructions": AgentConfigurationErrorCode.REQUIRED},
        ),
        (
            {"provider_type": None},
            AgentReadinessState.INCOMPLETE,
            {"provider_type": AgentConfigurationErrorCode.REQUIRED},
        ),
        (
            {"model_identifier": "other-model"},
            AgentReadinessState.UNAVAILABLE,
            {"model_identifier": AgentConfigurationErrorCode.UNAVAILABLE},
        ),
        (
            {"provider_type": "anthropic"},
            AgentReadinessState.UNAVAILABLE,
            {
                "provider_type": AgentConfigurationErrorCode.UNAVAILABLE,
                "model_identifier": AgentConfigurationErrorCode.UNAVAILABLE,
            },
        ),
    ],
)
def test_configuration_reports_missing_and_unavailable_fields(
    configured_agent, values, readiness, errors
):
    configuration = AgentHandler().get_configuration(configured_agent(**values))

    assert isinstance(configuration, AgentConfiguration)
    assert configuration.run_as.status is AgentRunAsState.UNSET
    assert configuration.readiness is readiness
    assert configuration.errors == errors
    assert all(
        isinstance(error, AgentConfigurationErrorCode)
        for error in configuration.errors.values()
    )


@pytest.mark.django_db
@pytest.mark.parametrize("workspace_count", [1, 5])
def test_application_readiness_uses_bulk_provider_state(
    configured_agent, django_assert_num_queries, workspace_count
):
    agents = []
    for _ in range(workspace_count):
        ready = configured_agent()
        identity = Agent.objects.create(workspace=ready.workspace, name="Investor")
        ready.run_as_subject_type = "core.Agent"
        ready.run_as_subject_id = identity.id
        ready.save()
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
def test_configuration_update_records_full_snapshots_and_ignores_noop_drafts(
    data_fixture, mocker
):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)
    registered = mocker.spy(
        UpdateAgentConfigurationActionType, "send_action_done_signal"
    )
    updated = mocker.spy(application_updated, "send")

    action_type_registry.get_by_type(UpdateAgentConfigurationActionType).do(
        user, agent.id, instructions="Line 1\nLine 2", provider_type=" "
    )
    action_type_registry.get_by_type(UpdateAgentConfigurationActionType).do(
        user, agent.id, instructions="Line 1\nLine 2"
    )

    agent.refresh_from_db()
    assert (agent.instructions, agent.provider_type) == ("Line 1\nLine 2", None)
    registered.assert_called_once()
    updated.assert_called_once()
    original_values = {
        "instructions": "",
        "provider_type": None,
        "model_identifier": None,
        "reasoning_effort": None,
        "run_as_subject_type": None,
        "run_as_subject_id": None,
        "allowed_tools": [],
        "web_search_enabled": False,
        "ask_first_tools": [],
    }
    params = registered.call_args.args[1]
    assert params == {
        "agent_id": agent.id,
        "original_values": original_values,
        "new_values": {**original_values, "instructions": "Line 1\nLine 2"},
    }
    assert UpdateAgentConfigurationActionType.get_analytics_properties(params) == {
        "agent_id": agent.id,
        "changed_fields": ["instructions"],
    }
    round_tripped = UpdateAgentConfigurationActionType.serialized_to_params(
        json.loads(json.dumps(params))
    )
    assert asdict(round_tripped) == params


@pytest.mark.django_db
def test_configuration_audit_snapshots_record_normalized_values(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    registered = mocker.spy(
        UpdateAgentConfigurationActionType, "send_action_done_signal"
    )
    original_values = {
        "instructions": agent.instructions,
        "provider_type": agent.provider_type,
        "model_identifier": agent.model_identifier,
        "reasoning_effort": None,
        "run_as_subject_type": None,
        "run_as_subject_id": None,
        "allowed_tools": [],
        "web_search_enabled": False,
        "ask_first_tools": [],
    }

    action_type_registry.get_by_type(UpdateAgentConfigurationActionType).do(
        user,
        agent.id,
        instructions=" Keep whitespace\n",
        provider_type="  anthropic \n",
        model_identifier=" \n",
    )
    # Different request strings normalize to the same saved configuration.
    action_type_registry.get_by_type(UpdateAgentConfigurationActionType).do(
        user,
        agent.id,
        instructions=" Keep whitespace\n",
        provider_type="anthropic ",
        model_identifier="",
    )

    agent.refresh_from_db()
    registered.assert_called_once()
    params = registered.call_args.args[1]
    assert params == {
        "agent_id": agent.id,
        "original_values": original_values,
        "new_values": {
            **original_values,
            "instructions": " Keep whitespace\n",
            "provider_type": "anthropic",
            "model_identifier": None,
        },
    }
    assert (agent.instructions, agent.provider_type, agent.model_identifier) == (
        " Keep whitespace\n",
        "anthropic",
        None,
    )
    assert UpdateAgentConfigurationActionType.get_analytics_properties(params) == {
        "agent_id": agent.id,
        "changed_fields": ["instructions", "provider_type", "model_identifier"],
    }


@pytest.mark.django_db
def test_configuration_audit_snapshots_record_identity_assignment_replacement_and_clear(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    first = Agent.objects.create(workspace=agent.workspace, name="First")
    second = Agent.objects.create(workspace=agent.workspace, name="Second")
    registered = mocker.spy(
        UpdateAgentConfigurationActionType, "send_action_done_signal"
    )
    snapshots = [
        {
            "instructions": agent.instructions,
            "provider_type": agent.provider_type,
            "model_identifier": agent.model_identifier,
            "reasoning_effort": None,
            "run_as_subject_type": None,
            "run_as_subject_id": None,
            "allowed_tools": [],
            "web_search_enabled": False,
            "ask_first_tools": [],
        }
    ]
    for identity in (first, second, None):
        run_as = {
            "run_as_subject_type": AgentSubjectType.type if identity else None,
            "run_as_subject_id": identity.id if identity else None,
        }
        snapshots.append({**snapshots[-1], **run_as})
        action_type_registry.get_by_type(UpdateAgentConfigurationActionType).do(
            user, agent.id, **run_as
        )
        action_type_registry.get_by_type(UpdateAgentConfigurationActionType).do(
            user, agent.id, **run_as
        )

    assert registered.call_count == 3
    for index, registered_call in enumerate(registered.call_args_list):
        params = registered_call.args[1]
        assert params == {
            "agent_id": agent.id,
            "original_values": snapshots[index],
            "new_values": snapshots[index + 1],
        }
        changed_fields = (
            ["run_as_subject_id"]
            if index == 1
            else ["run_as_subject_type", "run_as_subject_id"]
        )
        assert UpdateAgentConfigurationActionType.get_analytics_properties(params) == {
            "agent_id": agent.id,
            "changed_fields": changed_fields,
        }
    agent.refresh_from_db()
    assert (agent.run_as_subject_type, agent.run_as_subject_id) == (None, None)


@pytest.mark.django_db
def test_configuration_audit_snapshots_record_tools_and_ignore_reordered_lists(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
    agent.run_as_subject_type, agent.run_as_subject_id = "core.Agent", identity.id
    agent.save()
    registered = mocker.spy(
        UpdateAgentConfigurationActionType, "send_action_done_signal"
    )
    updated = mocker.spy(application_updated, "send")

    configuration = action_type_registry.get_by_type(
        UpdateAgentConfigurationActionType
    ).do(user, agent.id, allowed_tools=["create_rows", "list_table_rows"])
    action_type_registry.get_by_type(UpdateAgentConfigurationActionType).do(
        user, agent.id, allowed_tools=["list_table_rows", "create_rows", "create_rows"]
    )
    registered.assert_called_once()
    updated.assert_called_once()
    params = registered.call_args.args[1]
    assert params["original_values"]["allowed_tools"] == []
    assert params["new_values"] == {
        **params["original_values"],
        "allowed_tools": ["list_table_rows", "create_rows"],
        "ask_first_tools": ["create_rows"],
    }
    assert configuration.allowed_tools == params["new_values"]["allowed_tools"]
    assert UpdateAgentConfigurationActionType.get_analytics_properties(params) == {
        "agent_id": agent.id,
        "changed_fields": ["allowed_tools", "ask_first_tools"],
    }

    action_type_registry.get_by_type(UpdateAgentConfigurationActionType).do(
        user, agent.id, allowed_tools=[]
    )
    cleared = registered.call_args.args[1]
    assert registered.call_count == updated.call_count == 2
    assert cleared["original_values"] == params["new_values"]
    assert cleared["new_values"] == params["original_values"]


@pytest.mark.django_db
def test_tool_configuration_updates_the_timestamp_only_when_values_change(
    configured_agent, api_client, api_user
):
    with freeze_time() as clock:
        agent = configured_agent(user=api_user)
        identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
        agent.run_as_subject_type, agent.run_as_subject_id = "core.Agent", identity.id
        agent.save()
        url = agent_url(agent, "configuration")
        created_on = agent.updated_on

        clock.tick(1)
        response = api_client.patch(
            url, {"allowed_tools": ["create_rows", "list_table_rows"]}
        )
        assert response.status_code == 200
        agent.refresh_from_db()
        tools_updated_on = agent.updated_on
        assert tools_updated_on > created_on

        clock.tick(1)
        response = api_client.patch(
            url,
            {"allowed_tools": ["list_table_rows", "create_rows", "create_rows"]},
        )
        assert response.status_code == 200
        agent.refresh_from_db()
        assert agent.updated_on == tools_updated_on

        clock.tick(1)
        response = api_client.patch(
            url, {"instructions": "New instructions", "allowed_tools": []}
        )
        assert response.status_code == 200
        agent.refresh_from_db()
        assert agent.updated_on > tools_updated_on
        assert not agent.allowed_tools.exists()


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
            {"reasoning_effort": "max"},
            "reasoning_effort",
            "invalid_choice",
            id="reasoning-effort-unknown",
        ),
        pytest.param(
            {"unknown": "value"},
            "non_field_errors",
            "invalid",
            id="unknown-field",
        ),
        pytest.param(
            {"ask_first_tools": ["create_rows"]},
            "ask_first_tools",
            "invalid",
            id="ask-first-without-allowed-tools",
        ),
        pytest.param(
            {"allowed_tools": ["list_tables"], "ask_first_tools": ["create_rows"]},
            "ask_first_tools",
            "invalid",
            id="ask-first-not-allowed",
        ),
        pytest.param(
            {"allowed_tools": ["create_rows"], "ask_first_tools": ["drop_database"]},
            "ask_first_tools",
            "invalid",
            id="ask-first-unknown",
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
    assert response.json()["run_as"] == {
        **run_as,
        "trashed": False,
        "status": "active",
    }

    identity.trashed = True
    identity.save()
    assert api_client.get(url).json()["run_as"] == {
        **run_as,
        "trashed": True,
        "status": "trashed",
    }

    identity.delete()
    assert api_client.get(url).json()["run_as"] == {
        **run_as,
        "name": None,
        "trashed": False,
        "status": "missing",
    }

    response = api_client.patch(
        url, {"run_as_subject_type": None, "run_as_subject_id": None}
    )
    agent.refresh_from_db()
    assert (response.status_code, agent.run_as_subject_id) == (200, None)
    assert response.json()["run_as"] is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "case", ["missing", "foreign", "unknown_type", "user", "type_only", "id_only"]
)
def test_configuration_preserves_unavailable_run_as_without_disclosing_subject(
    configured_agent, data_fixture, api_client, api_user, case
):
    agent = configured_agent(user=api_user)
    identity = Agent.objects.create(
        workspace=agent.workspace, name="PRIVATE_IDENTITY_NAME"
    )
    agent.run_as_subject_type = "core.Agent"
    agent.run_as_subject_id = identity.id
    if case == "missing":
        identity.delete()
    elif case == "foreign":
        identity.workspace = data_fixture.create_workspace()
        identity.save()
    elif case == "unknown_type":
        agent.run_as_subject_type = "unknown.subject"
    elif case == "user":
        agent.run_as_subject_type = "auth.User"
        agent.run_as_subject_id = api_user.id
    elif case == "type_only":
        agent.run_as_subject_id = None
    elif case == "id_only":
        agent.run_as_subject_type = None
    agent.save()

    response = api_client.get(agent_url(agent, "configuration"))

    assert response.status_code == 200
    assert response.json()["run_as"] == {
        "type": agent.run_as_subject_type,
        "id": agent.run_as_subject_id,
        "name": None,
        "trashed": False,
        "status": "missing",
    }
    assert "PRIVATE_IDENTITY_NAME" not in response.content.decode()


@pytest.mark.django_db
def test_configuration_serializes_the_resolved_identity_snapshot(
    configured_agent, django_assert_num_queries
):
    agent = configured_agent()
    identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
    agent.run_as_subject_type = "core.Agent"
    agent.run_as_subject_id = identity.id
    configuration = AgentHandler().get_configuration(agent)
    assert configuration.run_as.status is AgentRunAsState.ACTIVE
    identity.name = "Renamed"
    identity.save()

    with django_assert_num_queries(0):
        payload = AgentConfigurationSerializer(configuration).data

    assert payload["run_as"]["name"] == "Investor"
    assert payload["run_as"]["status"] == "active"


@pytest.mark.django_db
def test_run_as_subject_options_use_agent_scope_and_support_search_and_pagination(
    configured_agent, data_fixture, api_client, api_user
):
    agent = configured_agent(user=api_user)
    first = Agent.objects.create(workspace=agent.workspace, name="Review Alpha")
    second = Agent.objects.create(workspace=agent.workspace, name="Review Beta")
    Agent.objects.create(workspace=agent.workspace, name="Other identity")
    Agent.objects.create(workspace=agent.workspace, name="Review trash", trashed=True)
    other_workspace = data_fixture.create_workspace()
    Agent.objects.create(workspace=other_workspace, name="Review foreign")
    params = {
        "search": "review",
        "size": 1,
        # Caller-supplied scopes cannot alter the application-owned choices.
        "workspace_id": other_workspace.id,
        "subject_types": "auth.User",
    }
    url = agent_url(agent, "run_as_subjects")

    first_page = api_client.get(url, {**params, "page": 1})
    second_page = api_client.get(url, {**params, "page": 2})

    assert first_page.status_code == second_page.status_code == 200
    assert first_page.json()["count"] == second_page.json()["count"] == 2
    results = first_page.json()["results"] + second_page.json()["results"]
    assert [(item["subject_type"], item["subject_id"]) for item in results] == [
        ("core.Agent", first.id),
        ("core.Agent", second.id),
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("case", ["other_workspace", "trashed", "snapshot"])
def test_run_as_subject_options_reject_inaccessible_applications(
    configured_agent, api_client, api_user, case
):
    agent = configured_agent(user=None if case == "other_workspace" else api_user)
    if case == "trashed":
        agent.trashed = True
        agent.save()
    elif case == "snapshot":
        agent.workspace = None
        agent.save()

    response = api_client.get(agent_url(agent, "run_as_subjects"))

    assert response.status_code == (401 if case == "other_workspace" else 404)


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", ["configuration", "run_as_subjects"])
@pytest.mark.parametrize("authenticated", [True, False])
def test_run_as_recovery_only_pins_authenticated_reads(
    configured_agent, api_client, api_user, mocker, endpoint, authenticated
):
    agent = configured_agent(user=api_user)
    if not authenticated:
        api_client.credentials()
    pin = mocker.patch("baserow.api.mixins.set_db_alias")

    response = api_client.get(
        agent_url(agent, endpoint), HTTP_X_BASEROW_REALTIME_RECOVERY="true"
    )

    if authenticated:
        assert response.status_code == 200
        pin.assert_called_once_with(DEFAULT_DB_ALIAS)
    else:
        assert response.status_code == 401
        pin.assert_not_called()


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
@pytest.mark.parametrize(
    "tools,expected,write_tool",
    [
        (
            ["create_rows", "list_table_rows"],
            ["list_table_rows", "create_rows"],
            "create_rows",
        ),
        (
            ["update_database", "create_database", "list_databases"],
            ["list_databases", "create_database", "update_database"],
            "update_database",
        ),
    ],
)
def test_allowed_tools_are_replaced_and_validated(
    configured_agent, api_client, api_user, tools, expected, write_tool
):
    agent = configured_agent(user=api_user)
    identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
    agent.run_as_subject_type, agent.run_as_subject_id = "core.Agent", identity.id
    agent.save()
    url = agent_url(agent, "configuration")

    assert api_client.get(url).json()["allowed_tools"] == []
    response = api_client.patch(url, {"allowed_tools": tools})
    assert response.json()["allowed_tools"] == expected
    assert {
        "name": write_tool,
        "group": "database",
        "changes_data": True,
    } in response.json()["available_tools"]

    response = api_client.patch(
        url, {"allowed_tools": ["list_tables", "drop_database"]}
    )
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert api_client.get(url).json()["allowed_tools"] == expected

    assert api_client.patch(url, {"allowed_tools": []}).json()["allowed_tools"] == []


@pytest.mark.django_db
def test_workspace_tools_stay_off_without_a_selected_identity(
    configured_agent, api_client, api_user, mocker
):
    agent = configured_agent(user=api_user)
    registered = mocker.spy(
        UpdateAgentConfigurationActionType, "send_action_done_signal"
    )
    updated_on = agent.updated_on

    response = api_client.patch(
        agent_url(agent, "configuration"), {"allowed_tools": ["create_rows"]}
    )

    assert response.status_code == 200
    assert response.json()["run_as"] is None
    assert response.json()["allowed_tools"] == []
    assert response.json()["readiness"] == "ready"
    agent.refresh_from_db()
    assert not agent.allowed_tools.exists()
    assert agent.updated_on == updated_on
    registered.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("submitted_tools", [None, ["list_tables", "create_rows"]])
def test_no_workspace_access_clears_tools_in_the_configuration_update(
    configured_agent, api_client, api_user, mocker, submitted_tools
):
    with freeze_time() as clock:
        agent = configured_agent(user=api_user)
        identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
        agent.run_as_subject_type, agent.run_as_subject_id = "core.Agent", identity.id
        agent.save()
        AgentHandler().set_allowed_tools(agent, ["list_tables", "create_rows"])
        previous_updated_on = agent.updated_on
        registered = mocker.spy(
            UpdateAgentConfigurationActionType, "send_action_done_signal"
        )
        values = {"run_as_subject_type": None, "run_as_subject_id": None}
        if submitted_tools is not None:
            values["allowed_tools"] = submitted_tools

        clock.tick(1)
        response = api_client.patch(agent_url(agent, "configuration"), values)

        assert response.status_code == 200
        assert response.json()["run_as"] is None
        assert response.json()["allowed_tools"] == []
        agent.refresh_from_db()
        assert (agent.run_as_subject_type, agent.run_as_subject_id) == (None, None)
        assert not agent.allowed_tools.exists()
        assert agent.updated_on > previous_updated_on
        registered.assert_called_once()
        params = registered.call_args.args[1]
        assert params["original_values"]["allowed_tools"] == [
            "list_tables",
            "create_rows",
        ]
        assert params["new_values"]["allowed_tools"] == []
        assert params["new_values"]["run_as_subject_id"] is None


@pytest.mark.django_db
def test_selecting_an_identity_does_not_reactivate_legacy_default_tools(
    configured_agent, api_client, api_user
):
    agent = configured_agent(user=api_user)
    identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
    # Previous versions inserted read tools even with No workspace access.
    AgentHandler().set_allowed_tools(agent, ["list_tables", "create_rows"])
    url = agent_url(agent, "configuration")

    assert api_client.get(url).json()["allowed_tools"] == []
    assert agent.allowed_tools.count() == 2  # Reading does not mutate saved data.
    response = api_client.patch(
        url,
        {"run_as_subject_type": "core.Agent", "run_as_subject_id": identity.id},
    )

    assert response.status_code == 200
    assert response.json()["run_as"]["id"] == identity.id
    assert response.json()["allowed_tools"] == []
    assert not agent.allowed_tools.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("state", ["trashed", "missing"])
def test_unavailable_selected_identity_keeps_its_tool_configuration(
    configured_agent, api_client, api_user, state
):
    agent = configured_agent(user=api_user)
    identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
    agent.run_as_subject_type, agent.run_as_subject_id = "core.Agent", identity.id
    agent.save()
    AgentHandler().set_allowed_tools(agent, ["list_tables", "create_rows"])
    if state == "trashed":
        identity.trashed = True
        identity.save()
    else:
        identity.delete()

    response = api_client.patch(
        agent_url(agent, "configuration"), {"instructions": "Updated instructions"}
    )

    assert response.status_code == 200
    assert response.json()["run_as"]["status"] == state
    assert response.json()["allowed_tools"] == ["list_tables", "create_rows"]
    assert agent.allowed_tools.count() == 2


@pytest.mark.django_db
def test_clearing_workspace_access_rolls_back_both_identity_and_tools_on_failure(
    configured_agent, api_user, mocker
):
    agent = configured_agent(user=api_user)
    identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
    agent.run_as_subject_type, agent.run_as_subject_id = "core.Agent", identity.id
    agent.save()
    handler = AgentHandler()
    handler.set_allowed_tools(agent, ["create_rows"])
    set_allowed_tools = AgentHandler.set_allowed_tools

    def fail_after_clearing(self, agent, names, ask_first_names=None):
        set_allowed_tools(self, agent, names, ask_first_names)
        raise RuntimeError("Failed after clearing tools")

    mocker.patch.object(AgentHandler, "set_allowed_tools", fail_after_clearing)
    with pytest.raises(RuntimeError, match="Failed after clearing tools"):
        action_type_registry.get_by_type(UpdateAgentConfigurationActionType).do(
            api_user, agent.id, run_as_subject_type=None, run_as_subject_id=None
        )

    agent.refresh_from_db()
    assert agent.run_as_subject_id == identity.id
    assert handler.get_tool_configuration(agent)["allowed_tools"] == ["create_rows"]


@pytest.mark.django_db
def test_newly_allowed_change_tools_ask_first_unless_set_explicitly(
    configured_agent, api_client, api_user, mocker
):
    agent = configured_agent(user=api_user)
    identity = Agent.objects.create(workspace=agent.workspace, name="Investor")
    agent.run_as_subject_type, agent.run_as_subject_id = "core.Agent", identity.id
    agent.save()
    url = agent_url(agent, "configuration")
    registered = mocker.spy(
        UpdateAgentConfigurationActionType, "send_action_done_signal"
    )

    def ask_first_tools_after(values: dict) -> list[str]:
        return api_client.patch(url, values).json()["ask_first_tools"]

    assert ask_first_tools_after({"allowed_tools": ["create_rows", "list_tables"]}) == [
        "create_rows"
    ]
    assert ask_first_tools_after(
        {
            "allowed_tools": ["create_rows", "list_tables"],
            "ask_first_tools": ["list_tables"],
        }
    ) == ["list_tables"]
    allowed_tools = ["create_rows", "list_tables", "delete_rows"]
    assert ask_first_tools_after({"allowed_tools": allowed_tools}) == [
        "list_tables",
        "delete_rows",
    ]
    assert ask_first_tools_after(
        {
            "allowed_tools": allowed_tools,
            "ask_first_tools": ["delete_rows", "list_tables"],
        }
    ) == ["list_tables", "delete_rows"]
    assert api_client.get(url).json()["ask_first_tools"] == [
        "list_tables",
        "delete_rows",
    ]
    assert (
        ask_first_tools_after({"allowed_tools": allowed_tools, "ask_first_tools": []})
        == []
    )
    assert [
        UpdateAgentConfigurationActionType.get_analytics_properties(call.args[1])[
            "changed_fields"
        ]
        for call in registered.call_args_list
    ] == [
        ["allowed_tools", "ask_first_tools"],
        ["ask_first_tools"],
        ["allowed_tools", "ask_first_tools"],
        ["ask_first_tools"],
    ]


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
        "reasoning_effort": None,
        "applied_reasoning_effort": None,
        "run_as": None,
        "allowed_tools": [],
        "ask_first_tools": [],
        "available_tools": ANY,
        "web_search_enabled": False,
        "web_search_available": True,
        "web_search_blocked_by_tools": False,
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


@pytest.mark.django_db
def test_reasoning_effort_is_saved_reported_and_cleared(
    configured_agent, api_client, api_user
):
    agent = configured_agent(user=api_user)
    url = agent_url(agent, "configuration")

    assert api_client.get(url).json()["reasoning_effort"] is None

    response = api_client.patch(url, {"reasoning_effort": "high"})
    assert response.status_code == 200
    assert response.json()["reasoning_effort"] == "high"
    # Reasoning is optional, so it never affects readiness.
    assert response.json()["readiness"] == "ready"
    agent.refresh_from_db()
    assert agent.reasoning_effort == "high"

    response = api_client.patch(url, {"reasoning_effort": None})
    assert response.status_code == 200
    assert response.json()["reasoning_effort"] is None
    agent.refresh_from_db()
    assert agent.reasoning_effort is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_identifier,effort,applied",
    [
        ("gpt-5.1", "off", "off"),
        # Off becomes the lowest effort on a model that can't stop reasoning.
        ("o3", "off", "low"),
        # The next higher effort the model accepts.
        ("gpt-5-pro", "low", "high"),
        # A model without reasoning uses its default.
        ("gpt-4.1", "high", None),
        ("gpt-5.1", None, None),
    ],
)
def test_configuration_reports_the_reasoning_effort_replies_use(
    configured_agent, api_client, api_user, model_identifier, effort, applied
):
    agent = configured_agent(
        user=api_user, model_identifier=model_identifier, reasoning_effort=effort
    )
    AIProviderModel.objects.create(
        provider_config=AIProviderConfig.objects.get(workspace=agent.workspace),
        model_identifier=model_identifier,
    )

    response = api_client.get(agent_url(agent, "configuration"))

    assert response.json()["reasoning_effort"] == effort
    assert response.json()["applied_reasoning_effort"] == applied


@pytest.mark.django_db
def test_configuration_reports_no_applied_effort_for_an_unavailable_model(
    configured_agent, api_client, api_user
):
    agent = configured_agent(
        user=api_user, model_identifier="gpt-5-pro", reasoning_effort="low"
    )

    response = api_client.get(agent_url(agent, "configuration"))

    assert response.json()["errors"] == {"model_identifier": "unavailable"}
    assert response.json()["applied_reasoning_effort"] is None


@pytest.mark.django_db
def test_reasoning_effort_change_is_recorded(data_fixture, mocker):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)
    registered = mocker.spy(
        UpdateAgentConfigurationActionType, "send_action_done_signal"
    )

    UpdateAgentConfigurationActionType.do(user, agent.id, reasoning_effort="low")

    params = registered.call_args.args[1]
    assert params["original_values"]["reasoning_effort"] is None
    assert params["new_values"]["reasoning_effort"] == "low"
    assert UpdateAgentConfigurationActionType.get_analytics_properties(params) == {
        "agent_id": agent.id,
        "changed_fields": ["reasoning_effort"],
    }
