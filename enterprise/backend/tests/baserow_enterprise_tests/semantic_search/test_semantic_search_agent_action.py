import json

from django.test import override_settings

import pytest

from baserow.contrib.agent.action_tools.exceptions import AgentActionTypeNotAvailable
from baserow.contrib.agent.action_tools.handler import AgentActionHandler
from baserow.contrib.agent.action_tools.service import AgentActionService
from baserow.contrib.agent.action_tools.tools import BoundActionTool, get_approval_key
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.integrations.local_baserow.integration_types import (
    LocalBaserowIntegrationType,
)
from baserow.core.registries import application_type_registry
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.integrations.local_baserow.agent_action_types import (
    LocalBaserowSemanticSearchAgentActionType,
)

from .utils import index

SEARCH = LocalBaserowSemanticSearchAgentActionType.type


@pytest.fixture
def search_setup(data_fixture, semantic_search):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table, fields, _ = data_fixture.build_table(
        user=user,
        database=database,
        columns=[("Document", "long_text"), ("Category", "text")],
        rows=[
            ["How to reset your password", "public"],
            ["Recipe for a chocolate cake", "public"],
            ["Monthly budget meeting notes", "private"],
        ],
    )
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)
    index(table)
    agent = data_fixture.create_agent_application(user=user, workspace=workspace)
    action = AgentActionService().create_action(user, agent.id, SEARCH)
    return user, agent, table, fields, action


def configure(data_fixture, user, agent, table, action):
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=agent
    )
    AgentActionService().update_action(
        user,
        agent.id,
        action.id,
        service_values={"integration_id": integration.id, "table_id": table.id},
    )
    return reload(action)


def reload(action):
    return AgentActionHandler().get_action(action.id)


@pytest.mark.django_db
def test_a_new_search_reads_without_asking_and_waits_for_integration_and_table(
    search_setup,
):
    user, agent, table, fields, action = search_setup
    assert action.ask_first is False
    assert [(i["name"], i["type"], i["required"]) for i in action.inputs] == [
        ("query", "string", True)
    ]
    assert AgentActionHandler().get_configuration_errors(action) == {
        "integration_id": "required",
        "table_id": "required",
    }
    assert application_type_registry.get("agent").supports_integration_type(
        LocalBaserowIntegrationType()
    )


@pytest.mark.django_db
def test_a_configured_search_returns_the_best_match_first(data_fixture, search_setup):
    user, agent, table, fields, action = search_setup
    action = configure(data_fixture, user, agent, table, action)
    assert AgentActionHandler().get_configuration_errors(action) == {}

    tool = BoundActionTool.from_action(action)
    resolved_values = tool.action_type.prepare(action, {"query": "chocolate cake"})
    assert json.loads(json.dumps(resolved_values)) == resolved_values
    assert tool.action_type.get_preview(
        action, resolved_values, {"query": "chocolate cake"}
    ) == {
        "values": {
            "table": table.name,
            "search_query": "chocolate cake",
            "max_results": 10,
        }
    }
    result = tool.action_type.dispatch(action, resolved_values)
    assert result.data["results"][0]["row"]["Document"] == (
        "Recipe for a chocolate cake"
    )
    assert get_approval_key(action) == get_approval_key(reload(action))
    assert tool.changes_data is False
    email = data_fixture.create_agent_action(agent=agent)
    assert BoundActionTool.from_action(email).changes_data is True


@pytest.mark.django_db
def test_a_filter_can_only_hold_fixed_values(data_fixture, search_setup):
    user, agent, table, fields, action = search_setup
    action = configure(data_fixture, user, agent, table, action)
    service_filter = data_fixture.create_local_baserow_table_service_filter(
        service=action.service, field=fields[1], value="'private'"
    )
    action = reload(action)
    action_type = LocalBaserowSemanticSearchAgentActionType()
    assert action_type.get_configuration_errors(action) == {}
    result = action_type.dispatch(
        action, action_type.prepare(action, {"query": "chocolate cake"})
    )
    assert [item["row"]["Category"] for item in result.data["results"]] == ["private"]

    service_filter.value = f"get('tool_input.{action.inputs[0]['id']}')"
    service_filter.save()
    assert action_type.get_configuration_errors(reload(action)) == {
        "filters": "invalid"
    }


@pytest.mark.django_db
def test_a_table_out_of_reach_is_unavailable(data_fixture, search_setup):
    user, agent, table, fields, action = search_setup
    action = configure(data_fixture, user, agent, table, action)
    TrashHandler.trash(user, table.database.workspace, table.database, table)
    assert AgentActionHandler().get_configuration_errors(reload(action)) == {
        "table_id": "unavailable"
    }
    other_table = data_fixture.create_database_table(user=user)
    service = action.service.specific
    service.table = other_table
    service.save()
    assert AgentActionHandler().get_configuration_errors(reload(action)) == {
        "table_id": "unavailable"
    }


@pytest.mark.django_db
def test_a_search_whose_integration_was_deleted_is_left_out(data_fixture, search_setup):
    user, agent, table, fields, action = search_setup
    action = configure(data_fixture, user, agent, table, action)
    TrashHandler.trash(
        user, agent.workspace, agent, action.service.integration.specific
    )

    errors = AgentActionHandler().get_configuration_errors(reload(action))

    assert list(errors) == ["integration_id"]
    assert AgentActionHandler().get_callable_actions(agent) == []


@pytest.mark.django_db
def test_search_is_usable_only_when_licensed_and_embeddings_are_set_up(
    data_fixture, enterprise_data_fixture, search_setup
):
    user, agent, table, fields, action = search_setup
    handler = AgentActionHandler()
    handler.check_type_usable(agent, SEARCH)
    with override_settings(BASEROW_EMBEDDINGS_API_URL=""):
        with pytest.raises(AgentActionTypeNotAvailable):
            handler.check_type_usable(agent, SEARCH)
    enterprise_data_fixture.delete_all_licenses()
    assert SEARCH in handler.available_action_types()
    with pytest.raises(AgentActionTypeNotAvailable):
        handler.check_type_usable(agent, SEARCH)
    assert handler.get_configuration_errors(reload(action))["type"] == "unavailable"
