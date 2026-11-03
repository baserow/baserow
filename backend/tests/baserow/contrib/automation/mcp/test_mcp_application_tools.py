"""The application create and update tools over MCP, one per application type."""

import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.automation.models import Automation
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.database.models import Database
from baserow.core.integrations.models import Integration
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.mcp.groups import (
    GROUP_AUTOMATION_EDIT,
    GROUP_DASHBOARD_EDIT,
    GROUP_DATABASE_EDIT,
)
from baserow.core.mcp.registries import mcp_tool_registry

NOT_FOUND = "Not found in this workspace."


def _session(endpoint, callback):
    async def inner():
        token = current_key.set(endpoint.key)
        try:
            async with client_session(BaserowMCPServer()._mcp_server) as client:
                return await callback(client)
        finally:
            current_key.reset(token)

    with transaction.atomic():
        return async_to_sync(inner)()


def _call(endpoint, name, arguments):
    async def callback(client):
        return await client.call_tool(name, arguments)

    return _session(endpoint, callback)


def _json(result):
    assert result.isError is False, result.content[0].text
    return json.loads(result.content[0].text)


@pytest.mark.parametrize(
    "tool,group",
    [
        ("create_database", GROUP_DATABASE_EDIT),
        ("update_database", GROUP_DATABASE_EDIT),
        ("create_automation", GROUP_AUTOMATION_EDIT),
        ("update_automation", GROUP_AUTOMATION_EDIT),
        ("create_dashboard", GROUP_DASHBOARD_EDIT),
        ("update_dashboard", GROUP_DASHBOARD_EDIT),
    ],
)
def test_application_tools_are_in_the_edit_group_of_their_type(tool, group):
    registered = mcp_tool_registry.get(tool)

    assert registered.group == group
    assert registered.read_only is False
    assert registered.destructive is False


def test_there_are_no_application_delete_tools():
    names = {tool.name for tool in mcp_tool_registry.get_all()}

    for application_type in ("database", "automation", "dashboard", "builder"):
        assert f"delete_{application_type}" not in names
        assert f"delete_{application_type}s" not in names


def test_each_create_tool_takes_one_name():
    for tool in ("create_database", "create_automation", "create_dashboard"):
        schema = mcp_tool_registry.get(tool).input_schema.model_json_schema()
        assert set(schema["properties"]) == {"name"}
        assert schema["required"] == ["name"]
        assert schema["properties"]["name"]["maxLength"] == 160


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tool,key,model",
    [
        ("create_database", "created_database", Database),
        ("create_automation", "created_automation", Automation),
        ("create_dashboard", "created_dashboard", Dashboard),
    ],
)
def test_create_tool_creates_its_type_over_mcp(data_fixture, tool, key, model):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=[tool])

    created = _json(_call(endpoint, tool, {"name": "Thing"}))[key]

    assert model.objects.get(id=created["id"]).workspace_id == endpoint.workspace_id


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tool,id_argument,make",
    [
        ("update_database", "database_id", "create_automation_application"),
        ("update_automation", "automation_id", "create_dashboard_application"),
        ("update_dashboard", "dashboard_id", "create_database_application"),
    ],
)
def test_update_tool_refuses_another_type_over_mcp(
    data_fixture, tool, id_argument, make
):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=[tool])
    other = getattr(data_fixture, make)(workspace=endpoint.workspace, name="Other")

    result = _call(endpoint, tool, {id_argument: other.id, "name": "New"})

    assert result.isError is True
    assert result.content[0].text == NOT_FOUND
    other.refresh_from_db()
    assert other.name == "Other"


@pytest.mark.django_db
def test_created_database_and_automation_take_tables_and_a_workflow_straight_away(
    data_fixture,
):
    tools = [
        "create_database",
        "create_tables",
        "create_automation",
        "create_workflows",
    ]
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=tools)

    async def callback(client):
        database = _json(await client.call_tool("create_database", {"name": "Sales"}))[
            "created_database"
        ]
        tables = _json(
            await client.call_tool(
                "create_tables",
                {
                    "database_id": database["id"],
                    "tables": [
                        {"name": "Orders", "primary_field_name": "Name", "fields": []},
                        {"name": "Log", "primary_field_name": "Name", "fields": []},
                    ],
                },
            )
        )["created_tables"]
        automation = _json(
            await client.call_tool("create_automation", {"name": "Flows"})
        )["created_automation"]
        orders, log = tables
        workflows = _json(
            await client.call_tool(
                "create_workflows",
                {
                    "automation_id": automation["id"],
                    "workflows": [
                        {
                            "name": "Log new orders",
                            "trigger": {
                                "ref": "trigger",
                                "label": "Order created",
                                "type": "rows_created",
                                "rows_triggers_settings": {"table_id": orders["id"]},
                            },
                            "nodes": [
                                {
                                    "ref": "log",
                                    "label": "Log it",
                                    "type": "create_row",
                                    "previous_node_ref": "trigger",
                                    "table_id": log["id"],
                                    "values": [
                                        {
                                            "field_id": log["primary_field"]["id"],
                                            "value": "New",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
            )
        )
        return automation, workflows

    automation, workflows = _session(endpoint, callback)

    (workflow,) = workflows["created_workflows"]
    assert [node["ref"] for node in workflow["nodes"]] == ["trigger", "log"]
    assert Integration.objects.filter(application_id=automation["id"]).count() == 1
