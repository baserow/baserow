"""The automation tools over MCP."""

import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.mcp import BaserowMCPServer, current_key
from tests.baserow.contrib.automation.tools.conftest import (
    create_node,
    create_workflow,
)

READ_TOOLS = ["list_workflows", "list_nodes"]
EDIT_TOOLS = ["create_workflows", "add_nodes", "update_nodes"]
ALL_TOOLS = [*READ_TOOLS, *EDIT_TOOLS, "delete_nodes"]
KUMA_ONLY = ("ask_user", "navigate", "thought", "iterator", "load_")


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


@pytest.mark.django_db
def test_read_tools_over_mcp(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=READ_TOOLS)
    automation = data_fixture.create_automation_application(
        workspace=endpoint.workspace
    )
    workflow, trigger = create_workflow(endpoint.user, automation, "Flow")

    async def callback(client):
        listed = await client.list_tools()
        workflows = await client.call_tool("list_workflows", {})
        nodes = await client.call_tool("list_nodes", {"workflow_id": workflow.id})
        return listed, workflows, nodes

    listed, workflows, nodes = _session(endpoint, callback)

    tools = {tool.name: tool for tool in listed.tools}
    assert set(tools) == set(READ_TOOLS)
    for tool in tools.values():
        assert tool.annotations.readOnlyHint is True
        for kuma_only in KUMA_ONLY:
            assert kuma_only not in tool.description
    assert json.loads(workflows.content[0].text)["automations"][0]["workflows"] == [
        {"id": workflow.id, "name": "Flow", "state": "draft"}
    ]
    assert [node["id"] for node in json.loads(nodes.content[0].text)["nodes"]] == [
        trigger.id
    ]


@pytest.mark.django_db
def test_read_tools_over_mcp_hide_other_workspaces(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=READ_TOOLS)
    elsewhere = data_fixture.create_automation_application(
        workspace=data_fixture.create_workspace(user=endpoint.user)
    )
    workflow, _ = create_workflow(endpoint.user, elsewhere)

    for name, arguments in (
        ("list_workflows", {"automation_id": elsewhere.id}),
        ("list_nodes", {"workflow_id": workflow.id}),
    ):
        result = _call(endpoint, name, arguments)
        assert result.isError is True
        assert result.content[0].text == "Not found in this workspace."


@pytest.mark.django_db
def test_read_tools_over_mcp_reject_unknown_arguments(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=READ_TOOLS)

    result = _call(endpoint, "list_workflows", {"thought": "why"})

    assert result.isError is True
    assert "thought" in result.content[0].text


def _email(previous, **values):
    return {
        "ref": "mail",
        "type": "smtp_email",
        "label": "Mail",
        "previous_node_ref": previous,
        "to_emails": "team@example.com",
        "subject": "New order",
        "body": "Hello",
        **values,
    }


def _workflow(table):
    return {
        "name": "Orders",
        "trigger": {
            "ref": "trigger",
            "type": "rows_created",
            "rows_triggers_settings": {"table_id": table.id},
        },
        "nodes": [_email("trigger")],
    }


@pytest.mark.django_db
def test_write_tools_over_mcp(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=ALL_TOOLS)
    automation = data_fixture.create_automation_application(
        workspace=endpoint.workspace
    )
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)

    async def callback(client):
        listed = await client.list_tools()
        created = json.loads(
            (
                await client.call_tool(
                    "create_workflows",
                    {"automation_id": automation.id, "workflows": [_workflow(table)]},
                )
            )
            .content[0]
            .text
        )
        workflow = created["created_workflows"][0]
        mail_id = workflow["nodes"][1]["id"]
        added = json.loads(
            (
                await client.call_tool(
                    "add_nodes",
                    {
                        "workflow_id": workflow["id"],
                        "nodes": [
                            _email(str(mail_id), ref="second", subject="concat(")
                        ],
                    },
                )
            )
            .content[0]
            .text
        )
        second_id = added["created_nodes"][0]["id"]
        updated = json.loads(
            (
                await client.call_tool(
                    "update_nodes",
                    {
                        "workflow_id": workflow["id"],
                        "nodes": [
                            {
                                "node_id": second_id,
                                "subject": "get('previous_node.1.0.id')",
                            }
                        ],
                    },
                )
            )
            .content[0]
            .text
        )
        deleted = json.loads(
            (await client.call_tool("delete_nodes", {"node_ids": [second_id]}))
            .content[0]
            .text
        )
        return listed, added, updated, deleted, second_id

    listed, added, updated, deleted, second_id = _session(endpoint, callback)

    tools = {tool.name: tool for tool in listed.tools}
    assert set(tools) == set(ALL_TOOLS)
    for tool in tools.values():
        for kuma_only in KUMA_ONLY:
            assert kuma_only not in tool.description
    assert added["formula_errors"][0]["field"] == "subject"
    assert "formula_errors" not in updated
    assert updated["updated_nodes"] == [{"node_id": second_id, "label": "Mail"}]
    assert deleted == {"deleted_node_ids": [second_id]}
    assert not AutomationNode.objects.filter(id=second_id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name", ["create_workflows", "add_nodes", "update_nodes", "delete_nodes"]
)
def test_write_tools_over_mcp_reject_unknown_arguments(data_fixture, name):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=ALL_TOOLS)

    result = _call(endpoint, name, {"thought": "why"})

    assert result.isError is True
    assert "thought" in result.content[0].text


@pytest.mark.django_db
def test_write_tools_over_mcp_hide_other_workspaces(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=ALL_TOOLS)
    elsewhere = data_fixture.create_automation_application(
        workspace=data_fixture.create_workspace(user=endpoint.user)
    )
    workflow, trigger = create_workflow(endpoint.user, elsewhere)
    mail = create_node(
        endpoint.user, workflow, "smtp_email", reference_node_id=trigger.id
    )
    here = data_fixture.create_automation_application(workspace=endpoint.workspace)
    here_workflow, _ = create_workflow(endpoint.user, here)

    calls = [
        (
            "create_workflows",
            {
                "automation_id": elsewhere.id,
                "workflows": [
                    {
                        "name": "X",
                        "trigger": {
                            "ref": "t",
                            "type": "periodic",
                            "periodic_interval": {"interval": "DAY"},
                        },
                    }
                ],
            },
        ),
        ("add_nodes", {"workflow_id": workflow.id, "nodes": [_email(str(trigger.id))]}),
    ]
    for name, arguments in calls:
        result = _call(endpoint, name, arguments)
        assert result.isError is True, name
        assert result.content[0].text == "Not found in this workspace.", name

    updated = json.loads(
        _call(
            endpoint,
            "update_nodes",
            {
                "workflow_id": here_workflow.id,
                "nodes": [{"node_id": mail.id, "label": "X"}],
            },
        )
        .content[0]
        .text
    )
    assert updated["errors"] == [
        f"Error updating node {mail.id}: Not found in this workspace."
    ]
    deleted = json.loads(
        _call(endpoint, "delete_nodes", {"node_ids": [mail.id]}).content[0].text
    )
    assert deleted["errors"] == [
        f"Error deleting node {mail.id}: Not found in this workspace."
    ]
    mail.refresh_from_db()
    assert mail.label != "X"
    assert AutomationWorkflow.objects.filter(automation=elsewhere).count() == 1
