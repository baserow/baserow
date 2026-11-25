import json
from uuid import uuid4

from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.agent.action_tools.handler import AgentActionHandler
from baserow.contrib.agent.action_tools.registries import agent_action_type_registry
from baserow.contrib.agent.action_tools.service import AgentActionService
from baserow.contrib.agent.action_tools.tools import BoundActionTool, get_approval_key
from baserow.contrib.agent.constants import AGENT_TRIGGER_TYPES_ENABLED
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.database.search.handler import SearchHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.tools.errors import ToolInputError

from ..utils import agent_url

# The automation node types that only mean something inside a workflow, or that
# an Agent doesn't host yet, each with why.
NODE_TYPES_NOT_HOSTED = {
    "router": "branches a workflow",
    "goto": "jumps to another node of a workflow",
    "iterator": "repeats the nodes it contains",
    "wait": "pauses a workflow run",
    "response": "answers the request that started a workflow",
    "manual": "is started from the workflow editor",
    "local_baserow_fields_updated": "not hosted yet",
    "local_baserow_create_rows": "not hosted yet",
    "local_baserow_update_rows": "not hosted yet",
    "start_workflow": "not hosted yet",
    "ai_agent": "not hosted yet",
    "csv_file_reader": "not hosted yet",
    "xls_file_reader": "not hosted yet",
    "code": "not hosted yet",
}


def input_of(name, input_type="string", required=True):
    return {
        "id": str(uuid4()),
        "name": name,
        "type": input_type,
        "description": "",
        "required": required,
    }


def reads(action_input):
    return {"formula": f"get('tool_input.{action_input['id']}')", "mode": "simple"}


@pytest.fixture
def people(data_fixture, api_user):
    """An Agent that acts as an identity, next to a table of its workspace."""

    workspace = data_fixture.create_workspace(user=api_user)
    database = data_fixture.create_database_application(workspace=workspace)
    table, fields, rows = data_fixture.build_table(
        user=api_user,
        database=database,
        columns=[("Name", "text"), ("Status", "text")],
        rows=[["Ada", "open"], ["Bob", "closed"], ["Cleo", "open"]],
    )
    agent = data_fixture.create_agent_application(user=api_user, workspace=workspace)
    identity = data_fixture.create_identity(workspace=workspace)
    AgentHandler().update_configuration(
        agent, run_as_subject_type="auth.User", run_as_subject_id=identity.id
    )
    return agent, table, fields, rows


def add_action(api_client, agent, type_name, **values):
    """Add an action of a type and configure it, like its editor does."""

    response = api_client.post(agent_url(agent, "actions:list"), {"type": type_name})
    assert response.status_code == 200, response.json()
    created = response.json()
    assert created["type"] == type_name
    if values:
        response = api_client.patch(
            agent_url(agent, "actions:item", action_id=created["id"]), values
        )
        assert response.status_code == 200, response.json()
    return response.json()


def call(action_id, arguments):
    """Call an action like a reply does, with values that waited as JSON."""

    action = AgentActionHandler().get_action(action_id)
    tool = BoundActionTool.from_action(action)
    identity = AgentHandler().get_run_identity(action.agent)
    resolved_values = json.loads(
        json.dumps(tool.action_type.prepare(action, arguments))
    )
    preview = tool.action_type.get_preview(action, resolved_values, arguments)
    result = tool.action_type.dispatch(action, resolved_values, identity, arguments)
    return tool.action_type.get_tool_result(action, result), preview["values"]


def test_every_automation_node_type_is_hosted_or_left_out_on_purpose():
    offered = {
        *agent_action_type_registry.get_types(),
        *AGENT_TRIGGER_TYPES_ENABLED,
    }
    node_types = set(automation_node_type_registry.get_types())

    assert node_types - offered - set(NODE_TYPES_NOT_HOSTED) == set()
    assert offered & set(NODE_TYPES_NOT_HOSTED) == set()


@pytest.mark.django_db
def test_create_row_and_update_row_are_two_actions_on_one_service_type(
    api_client, people
):
    agent, table, fields, rows = people
    name = input_of("name")
    created = add_action(
        api_client,
        agent,
        "local_baserow_create_row",
        inputs=[name],
        service={
            "table_id": table.id,
            "field_mappings": [
                {"field_id": fields[0].id, "value": reads(name), "enabled": True},
                {"field_id": fields[1].id, "value": "'new'", "enabled": True},
            ],
        },
    )
    assert created["service"]["type"] == "local_baserow_upsert_row"
    assert created["errors"] == {}
    assert created["ask_first"] is True

    result, preview = call(created["id"], {"name": "Dana"})

    assert preview == {
        "table": table.name,
        "fields": {"Name": "Dana", "Status": "new"},
    }
    assert result["Name"] == "Dana"
    model = table.get_model()
    assert model.objects.count() == 4

    action = AgentActionHandler().get_action(created["id"])
    assert get_approval_key(action) == get_approval_key(
        AgentActionHandler().get_action(created["id"])
    )

    updated = add_action(api_client, agent, "local_baserow_update_row")
    assert [item["name"] for item in updated["inputs"]] == ["row_id"]
    assert updated["errors"] == {"table_id": "required"}
    row_id = updated["inputs"][0]
    response = api_client.patch(
        agent_url(agent, "actions:item", action_id=updated["id"]),
        {
            "service": {
                "table_id": table.id,
                "field_mappings": [
                    {"field_id": fields[1].id, "value": "'done'", "enabled": True}
                ],
            }
        },
    )
    assert response.json()["errors"] == {}

    call(updated["id"], {row_id["name"]: rows[0].id})

    assert model.objects.count() == 4
    assert getattr(model.objects.get(id=rows[0].id), fields[1].db_column) == "done"

    response = api_client.patch(
        agent_url(agent, "actions:item", action_id=updated["id"]),
        {"service": {"row_id": ""}},
    )
    assert response.json()["errors"] == {"row_id": "required"}


@pytest.mark.django_db
def test_update_row_checks_the_formulas_its_service_type_resolves(api_client, people):
    agent, table, fields, rows = people
    updated = add_action(
        api_client,
        agent,
        "local_baserow_update_row",
        service={
            "table_id": table.id,
            "field_mappings": [
                {
                    "field_id": fields[0].id,
                    "value": "get('tool_input.removed')",
                    "enabled": True,
                },
                {"field_id": fields[1].id, "value": "'done'", "enabled": True},
            ],
        },
    )
    assert updated["errors"] == {f"field_{fields[0].id}": "invalid"}

    action = AgentActionHandler().get_action(updated["id"])
    action_type = agent_action_type_registry.get(action.get_type_name())
    service = action.service.specific
    assert action_type.get_formulas(service) == {
        formula.key: formula.formula
        for formula in action_type.service_type.formulas_to_resolve(service)
    }


@pytest.mark.django_db
def test_list_rows_filters_and_searches_with_what_the_model_fills_in(
    api_client, people
):
    agent, table, fields, rows = people
    status = input_of("status")
    listed = add_action(api_client, agent, "local_baserow_list_rows")
    assert listed["ask_first"] is False
    response = api_client.patch(
        agent_url(agent, "actions:item", action_id=listed["id"]),
        {
            "inputs": [*listed["inputs"], status],
            "service": {
                "table_id": table.id,
                "filters": [
                    {"field": fields[1].id, "type": "equal", "value": reads(status)}
                ],
            },
        },
    )
    assert response.status_code == 200, response.json()
    assert response.json()["errors"] == {}

    result, preview = call(listed["id"], {"status": "open"})

    assert [row["Name"] for row in result["results"]] == ["Ada", "Cleo"]
    assert preview == {"table": table.name, "inputs": {"status": "open"}}

    SearchHandler.initialize_missing_search_data(table)
    SearchHandler.process_search_data_updates(table)
    result, _ = call(listed["id"], {"status": "open", "search": "Cleo"})

    assert [row["Name"] for row in result["results"]] == ["Cleo"]

    response = api_client.patch(
        agent_url(agent, "actions:item", action_id=listed["id"]),
        {"inputs": []},
    )
    assert response.json()["errors"] == {
        "filters": "invalid",
        "search_query": "invalid",
    }


@pytest.mark.django_db
def test_rows_are_read_changed_and_deleted_as_the_run_identity(
    api_client, data_fixture, people
):
    agent, table, fields, rows = people
    model = table.get_model()
    service = {"service": {"table_id": table.id}}

    got = add_action(api_client, agent, "local_baserow_get_row", **service)
    result, preview = call(got["id"], {"row_id": rows[1].id})
    assert result["Name"] == "Bob"
    assert preview == {"table": table.name, "row_id": rows[1].id}

    counted = add_action(api_client, agent, "local_baserow_aggregate_rows", **service)
    assert counted["errors"] == {
        "field_id": "required",
        "aggregation_type": "required",
    }
    response = api_client.patch(
        agent_url(agent, "actions:item", action_id=counted["id"]),
        {"service": {"field_id": fields[0].id, "aggregation_type": "not_empty_count"}},
    )
    assert response.json()["errors"] == {}
    result, preview = call(counted["id"], {})
    assert result == {"result": 3}
    assert preview == {
        "table": table.name,
        "field": fields[0].name,
        "aggregation_type": "not_empty_count",
    }
    view = data_fixture.create_grid_view(table=table)
    api_client.patch(
        agent_url(agent, "actions:item", action_id=counted["id"]),
        {"service": {"view_id": view.id}},
    )
    _, preview = call(counted["id"], {})
    assert preview["view"] == view.name

    deleted = add_action(api_client, agent, "local_baserow_delete_row", **service)
    result, _ = call(deleted["id"], {"row_id": rows[2].id})
    assert result == {"deleted": True}
    assert not model.objects.filter(id=rows[2].id).exists()

    row_id = {**deleted["inputs"][0], "required": False}
    response = api_client.patch(
        agent_url(agent, "actions:item", action_id=deleted["id"]),
        {"inputs": [row_id]},
    )
    assert response.json()["errors"] == {}
    with pytest.raises(ToolInputError):
        call(deleted["id"], {})
    assert model.objects.count() == 2

    response = api_client.patch(
        agent_url(agent, "actions:item", action_id=deleted["id"]),
        {"service": {"row_id": ""}},
    )
    assert response.json()["errors"] == {"row_id": "required"}

    AgentHandler().update_configuration(
        agent, run_as_subject_type=None, run_as_subject_id=None
    )
    response = api_client.get(agent_url(agent, "actions:list"))
    assert {item["errors"].get("run_as") for item in response.json()} == {"required"}


@pytest.mark.django_db
def test_row_action_forms_choose_from_the_tables_the_identity_reads(
    api_client, data_fixture, people
):
    agent, table, fields, rows = people

    response = api_client.get(agent_url(agent, "actions:types"))

    assert response.status_code == 200, response.json()
    by_type = {item["type"]: item["form_choices"] for item in response.json()}
    for type_name in (
        "local_baserow_create_row",
        "local_baserow_update_row",
        "local_baserow_delete_row",
        "local_baserow_get_row",
        "local_baserow_list_rows",
        "local_baserow_aggregate_rows",
    ):
        (database,) = by_type[type_name]["databases"]
        assert [item["id"] for item in database["tables"]] == [table.id]
    assert by_type["slack_write_message"] is None
    reads_inputs = {
        item["type"]: item["filters_read_inputs"] for item in response.json()
    }
    assert reads_inputs["local_baserow_list_rows"] is True
    assert reads_inputs["slack_write_message"] is False
    view = data_fixture.create_grid_view(table=table)
    response = api_client.get(agent_url(agent, "actions:types"))
    by_type = {item["type"]: item["form_choices"] for item in response.json()}
    for type_name, view_ids in (
        ("local_baserow_get_row", [view.id]),
        ("local_baserow_list_rows", [view.id]),
        ("local_baserow_aggregate_rows", [view.id]),
        ("local_baserow_delete_row", []),
    ):
        (database,) = by_type[type_name]["databases"]
        assert [item["id"] for item in database["views"]] == view_ids


@pytest.mark.django_db
@pytest.mark.parametrize(
    "type_name",
    ["local_baserow_create_row", "local_baserow_list_rows"],
)
def test_listing_more_actions_of_a_type_costs_no_more_queries(
    api_client, api_user, data_fixture, people, type_name
):
    agent, table, fields, rows = people

    def add():
        action = AgentActionService().create_action(api_user, agent.id, type_name)
        service = action.service.specific
        service_values = {"table_id": table.id}
        if type_name == "local_baserow_create_row":
            service_values["field_mappings"] = [
                {"field_id": field.id, "value": "'x'", "enabled": True}
                for field in fields
            ]
        else:
            data_fixture.create_local_baserow_table_service_filter(
                service=service, field=fields[0], value="'Ada'"
            )
        AgentActionService().update_action(
            api_user, agent.id, action.id, service_values=service_values
        )

    def count_queries():
        with CaptureQueriesContext(connection) as queries:
            response = api_client.get(agent_url(agent, "actions:list"))
        assert [item["errors"] for item in response.json()] == [{}] * len(
            response.json()
        )
        return len(queries)

    add()
    one_action = count_queries()
    add()
    add()

    assert count_queries() == one_action


@pytest.mark.django_db
def test_actions_that_call_another_service_keep_their_integration(
    api_client, data_fixture, people
):
    agent, table, fields, rows = people

    slack = add_action(api_client, agent, "slack_write_message")
    assert [item["name"] for item in slack["inputs"]] == ["text"]
    assert slack["errors"] == {"integration_id": "required", "channel": "required"}

    integration = data_fixture.create_slack_bot_integration(application=agent)
    response = api_client.patch(
        agent_url(agent, "actions:item", action_id=slack["id"]),
        {"service": {"integration_id": integration.id, "channel": "general"}},
    )
    assert response.status_code == 200, response.json()
    assert response.json()["errors"] == {}


@pytest.mark.django_db
def test_a_copied_agent_keeps_the_type_of_actions_that_share_a_service_type(
    api_client, data_fixture, people
):
    agent, table, fields, rows = people
    add_action(api_client, agent, "local_baserow_update_row")
    config = ImportExportConfig(include_permission_data=True, is_duplicate=True)
    target = data_fixture.create_agent_application(workspace=agent.workspace)

    [copied] = AgentActionHandler().import_actions(
        target, AgentActionHandler().export_actions(agent, config), {}, config
    )

    assert copied.get_type_name() == "local_baserow_update_row"
    assert AgentActionHandler().get_action(copied.id).service.get_type().type == (
        "local_baserow_upsert_row"
    )
