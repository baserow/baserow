import json

from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest

from baserow.contrib.agent.action_tools.exceptions import AgentActionTypeNotAvailable
from baserow.contrib.agent.action_tools.handler import AgentActionHandler
from baserow.contrib.agent.action_tools.service import AgentActionService
from baserow.contrib.agent.action_tools.tools import BoundActionTool, get_approval_key
from baserow.contrib.agent.constants import ACTION_MAX_RESULT_CHARACTERS
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.integrations.local_baserow.integration_types import (
    LocalBaserowIntegrationType,
)
from baserow.core.exceptions import PermissionDenied
from baserow.core.registries import application_type_registry
from baserow.core.services.types import DispatchResult
from baserow.core.tools import ToolContext
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


def configure(data_fixture, user, agent, table, action, role_uid="VIEWER"):
    identity = data_fixture.create_identity(
        workspace=agent.workspace, role_uid=role_uid
    )
    AgentHandler().update_configuration(
        agent, run_as_subject_type="auth.User", run_as_subject_id=identity.id
    )
    AgentActionService().update_action(
        user, agent.id, action.id, service_values={"table_id": table.id}
    )
    return reload(action)


def identity_of(action):
    return AgentHandler().get_run_identity(action.agent)


def reload(action):
    return AgentActionHandler().get_action(action.id)


@pytest.mark.django_db
def test_a_new_search_reads_without_asking_and_waits_for_identity_and_table(
    search_setup,
):
    user, agent, table, fields, action = search_setup
    assert action.ask_first is False
    assert [(i["name"], i["type"], i["required"]) for i in action.inputs] == [
        ("query", "string", True)
    ]
    assert AgentActionHandler().get_configuration_errors(action) == {
        "run_as": "required",
        "table_id": "required",
    }
    assert not application_type_registry.get("agent").supports_integration_type(
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
    result = tool.action_type.dispatch(action, resolved_values, identity_of(action))
    assert result.data["results"][0]["row"]["Document"] == (
        "Recipe for a chocolate cake"
    )
    assert get_approval_key(action) == get_approval_key(reload(action))
    assert tool.changes_data is False
    email = data_fixture.create_agent_action(agent=agent)
    assert BoundActionTool.from_action(email).changes_data is True


@pytest.mark.django_db
def test_a_filter_can_read_the_inputs(data_fixture, search_setup):
    user, agent, table, fields, action = search_setup
    action = configure(data_fixture, user, agent, table, action)
    service_filter = data_fixture.create_local_baserow_table_service_filter(
        service=action.service, field=fields[1], value="'private'"
    )
    action = reload(action)
    action_type = LocalBaserowSemanticSearchAgentActionType()
    assert action_type.get_configuration_errors(action, identity_of(action)) == {}
    result = action_type.dispatch(
        action,
        action_type.prepare(action, {"query": "chocolate cake"}),
        identity_of(action),
    )
    assert [item["row"]["Category"] for item in result.data["results"]] == ["private"]

    service_filter.value = f"get('tool_input.{action.inputs[0]['id']}')"
    service_filter.save()
    action = reload(action)
    assert action_type.get_configuration_errors(action, identity_of(action)) == {}
    arguments = {"query": "private"}
    result = action_type.dispatch(
        action, action_type.prepare(action, arguments), identity_of(action), arguments
    )
    assert [item["row"]["Category"] for item in result.data["results"]] == ["private"]

    service_filter.value = "get('tool_input.removed')"
    service_filter.save()
    assert action_type.get_configuration_errors(
        reload(action), identity_of(action)
    ) == {"filters": "invalid"}


@pytest.mark.django_db
def test_a_table_out_of_reach_is_unavailable(data_fixture, search_setup):
    user, agent, table, fields, action = search_setup
    action = configure(data_fixture, user, agent, table, action)
    TrashHandler.trash(user, table.database.workspace, table.database, table)
    assert AgentActionHandler().get_configuration_errors(reload(action)) == {
        "table_id": "unavailable"
    }
    TrashHandler.restore_item(user, "table", table.id)
    no_access = configure(
        data_fixture, user, agent, table, action, role_uid="NO_ACCESS"
    )
    assert AgentActionHandler().get_configuration_errors(no_access) == {
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
def test_a_search_without_a_field_to_search_in_is_left_out(data_fixture, search_setup):
    user, agent, table, fields, action = search_setup
    action = configure(data_fixture, user, agent, table, action)
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=False)

    assert AgentActionHandler().get_configuration_errors(reload(action)) == {
        "search_field_ids": "unavailable"
    }
    assert AgentActionHandler().get_callable_actions(agent) == []


@pytest.mark.django_db
def test_the_model_reads_the_best_matches_whole_and_the_rest_cut(
    data_fixture, search_setup
):
    user, agent, _, _, action = search_setup
    long_text = "Chocolate cake recipe with flour, sugar and eggs. " * 1000
    table, fields, _ = data_fixture.build_table(
        user=user,
        database=data_fixture.create_database_application(workspace=agent.workspace),
        columns=[("Document", "long_text")],
        rows=[[long_text], [long_text], [long_text]],
    )
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)
    index(table)
    action = configure(data_fixture, user, agent, table, action)
    action_type = LocalBaserowSemanticSearchAgentActionType()

    result = action_type.dispatch(
        action,
        action_type.prepare(action, {"query": "chocolate cake"}),
        identity_of(action),
    )
    tool_result = action_type.get_tool_result(action, result)

    assert len(json.dumps(result.data)) > ACTION_MAX_RESULT_CHARACTERS
    assert tool_result["truncated"] is True
    assert (
        len(json.dumps(tool_result, ensure_ascii=False))
        <= ACTION_MAX_RESULT_CHARACTERS + 100
    )
    best = tool_result["results"][0]
    assert best == {**result.data["results"][0], "row": best["row"]}
    assert best["row"]["Document"].endswith("…")
    assert long_text.startswith(best["row"]["Document"][:-1])
    assert len(tool_result["results"]) < len(result.data["results"])


def test_a_best_match_too_big_to_cut_its_texts_is_still_read():
    files = [{"url": "x" * ACTION_MAX_RESULT_CHARACTERS}]
    best = {"id": 1, "row": {"id": 1, "Photos": files, "Notes": "Refunds"}}
    result = DispatchResult(data={"results": [best], "has_next_page": False})

    tool_result = LocalBaserowSemanticSearchAgentActionType().get_tool_result(
        None, result
    )

    assert tool_result["results"] == [
        {"id": 1, "row": {"id": 1, "Photos": "…", "Notes": "Refunds"}}
    ]
    assert tool_result["truncated"] is True


@pytest.mark.django_db
def test_a_search_without_an_identity_is_left_out(data_fixture, search_setup):
    user, agent, table, fields, action = search_setup
    action = configure(data_fixture, user, agent, table, action)
    identity = identity_of(action)
    identity.profile.trashed = True
    identity.profile.save(update_fields=["trashed"])

    assert AgentActionHandler().get_configuration_errors(reload(action)) == {
        "run_as": "required"
    }
    assert AgentActionHandler().get_callable_actions(agent) == []


@pytest.mark.django_db
def test_a_search_reads_as_the_identity_and_never_through_an_integration(
    data_fixture, search_setup
):
    user, agent, table, fields, action = search_setup
    action = configure(data_fixture, user, agent, table, action)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=agent
    )
    AgentActionService().update_action(
        user,
        agent.id,
        action.id,
        service_values={"integration_id": integration.id},
    )
    action = reload(action)
    assert action.service.integration_id is None

    tool = BoundActionTool.from_action(action)
    identity = identity_of(action)
    ctx = ToolContext(user=identity, workspace=agent.workspace)
    assert tool._get_identity(ctx) == identity
    with pytest.raises(PermissionDenied):
        tool._get_identity(ToolContext(user=None, workspace=agent.workspace))

    other_workspace_identity = data_fixture.create_identity()
    with pytest.raises(PermissionDenied):
        tool.action_type.dispatch(
            action,
            tool.action_type.prepare(action, {"query": "chocolate cake"}),
            other_workspace_identity,
        )


@pytest.mark.django_db
def test_the_form_offers_the_tables_the_identity_can_read(data_fixture, search_setup):
    user, agent, table, fields, action = search_setup
    handler = AgentActionHandler()

    def tables(identity):
        options = {
            option.type: option for option in handler.list_action_types(agent, identity)
        }[SEARCH]
        return [
            table["id"]
            for database in options.form_choices["databases"]
            for table in database["tables"]
        ]

    assert tables(None) == []
    configure(data_fixture, user, agent, table, action)
    assert table.id in tables(identity_of(reload(action)))
    other_workspace_table = data_fixture.create_database_table(user=user)
    assert other_workspace_table.id not in tables(identity_of(reload(action)))


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


@pytest.mark.django_db
def test_the_action_types_endpoint_lists_the_identity_tables(
    api_client, data_fixture, search_setup
):
    user, agent, table, fields, action = search_setup
    configure(data_fixture, user, agent, table, action)
    token = data_fixture.generate_token(user)

    response = api_client.get(
        reverse("api:agent:actions:types", kwargs={"agent_id": agent.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200
    options = {item["type"]: item for item in response.json()}
    assert [
        listed["id"]
        for database in options[SEARCH]["form_choices"]["databases"]
        for listed in database["tables"]
    ] == [table.id]


@pytest.mark.django_db
def test_more_searches_only_add_the_query_of_their_fields(
    api_client, data_fixture, search_setup
):
    user, agent, table, fields, action = search_setup
    configure(data_fixture, user, agent, table, action)
    token = data_fixture.generate_token(user)
    url = reverse("api:agent:actions:list", kwargs={"agent_id": agent.id})

    def count_queries():
        with CaptureQueriesContext(connection) as callable_queries:
            callable_actions = AgentActionHandler().get_callable_actions(agent)
        with CaptureQueriesContext(connection) as list_queries:
            response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == 200
        assert all(not item["errors"] for item in response.json())
        return len(callable_actions), len(callable_queries), len(list_queries)

    one, callable_one, list_one = count_queries()
    for _ in range(4):
        added = AgentActionService().create_action(user, agent.id, SEARCH)
        AgentActionService().update_action(
            user, agent.id, added.id, service_values={"table_id": table.id}
        )
    five, callable_five, list_five = count_queries()

    assert (one, five) == (1, 5)
    # Each action's table is checked with the others; only its fields are read.
    assert callable_five - callable_one == 4
    assert list_five - list_one == 4
