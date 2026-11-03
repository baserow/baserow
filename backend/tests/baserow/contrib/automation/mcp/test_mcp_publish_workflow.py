"""Publishing a workflow over MCP."""

import json
from unittest.mock import patch

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.operations import (
    PublishAutomationWorkflowOperationType,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import Table
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.mcp.groups import GROUP_AUTOMATION_READ
from baserow.core.mcp.registries import mcp_tool_registry
from tests.baserow.contrib.automation.tools.conftest import (
    create_node,
    create_workflow,
)

TOOLS = [
    "create_automation",
    "create_workflows",
    "update_nodes",
    "create_tables",
    "list_workflows",
    "publish_workflow",
]


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


def _listed_state(endpoint, workflow_id):
    automations = _json(_call(endpoint, "list_workflows", {}))["automations"]
    return next(
        workflow["state"]
        for automation in automations
        for workflow in automation["workflows"]
        if workflow["id"] == workflow_id
    )


def _published(workflow_id):
    return AutomationWorkflow.objects.filter(automation__published_from=workflow_id)


def _build_workflow_over_mcp(data_fixture):
    """Orders and Log tables, and a draft that logs every new order."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, allowed_tools=TOOLS
    )
    database = data_fixture.create_database_application(workspace=workspace)

    async def callback(client):
        tables = _json(
            await client.call_tool(
                "create_tables",
                {
                    "database_id": database.id,
                    "tables": [
                        {"name": name, "primary_field_name": "Name", "fields": []}
                        for name in ("Orders", "Log")
                    ],
                },
            )
        )["created_tables"]
        automation = _json(
            await client.call_tool("create_automation", {"name": "Flows"})
        )["created_automation"]
        orders, log = tables
        (workflow,) = _json(
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
                                            "value": "Written",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
            )
        )["created_workflows"]
        return orders, log, workflow

    orders, log, workflow = _session(endpoint, callback)
    return endpoint, orders, log, workflow


def _create_order(user, orders):
    table = Table.objects.get(id=orders["id"])
    primary = table.field_set.get(primary=True)
    RowHandler().create_rows(user, table, [{primary.db_column: "go"}])


def _logged(log):
    rows = Table.objects.get(id=log["id"]).get_model().objects.order_by("id")
    return [getattr(row, f"field_{log['primary_field']['id']}") for row in rows]


@pytest.mark.django_db(transaction=True)
def test_workflow_built_and_published_over_mcp_writes_the_row(data_fixture):
    endpoint, orders, log, workflow = _build_workflow_over_mcp(data_fixture)
    assert workflow["state"] == "draft"
    assert _listed_state(endpoint, workflow["id"]) == "draft"

    # A draft doesn't run.
    _create_order(endpoint.user, orders)
    assert _logged(log) == []

    result = _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))

    assert result == {
        "published_workflow": {
            "id": workflow["id"],
            "name": "Log new orders",
            "state": "live",
        }
    }
    assert _listed_state(endpoint, workflow["id"]) == "live"

    _create_order(endpoint.user, orders)
    assert _logged(log) == ["Written"]


@pytest.mark.django_db(transaction=True)
def test_edits_reach_the_live_workflow_only_after_publishing_again(data_fixture):
    endpoint, orders, log, workflow = _build_workflow_over_mcp(data_fixture)
    _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))

    log_node = AutomationNode.objects.get(workflow_id=workflow["id"], label="Log it")
    _json(
        _call(
            endpoint,
            "update_nodes",
            {
                "workflow_id": workflow["id"],
                "nodes": [
                    {
                        "node_id": log_node.id,
                        "values": [
                            {
                                "field_id": log["primary_field"]["id"],
                                "value": "Edited",
                            }
                        ],
                    }
                ],
            },
        )
    )

    _create_order(endpoint.user, orders)
    assert _logged(log) == ["Written"]

    _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))
    assert _listed_state(endpoint, workflow["id"]) == "live"

    _create_order(endpoint.user, orders)
    assert _logged(log) == ["Written", "Edited"]


@pytest.mark.django_db(transaction=True)
def test_publishing_twice_leaves_one_live_version(data_fixture):
    endpoint, orders, log, workflow = _build_workflow_over_mcp(data_fixture)

    for _ in range(2):
        result = _json(
            _call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]})
        )
        assert result["published_workflow"]["state"] == "live"

    assert _published(workflow["id"]).filter(state=WorkflowState.LIVE).count() == 1
    assert _listed_state(endpoint, workflow["id"]) == "live"

    _create_order(endpoint.user, orders)
    assert _logged(log) == ["Written"]


@pytest.mark.django_db
def test_automation_read_cannot_publish(data_fixture):
    read_tools = [
        tool.name
        for tool in mcp_tool_registry.get_all()
        if tool.group == GROUP_AUTOMATION_READ
    ]
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=read_tools)
    automation = data_fixture.create_automation_application(
        workspace=endpoint.workspace
    )
    workflow, _ = create_workflow(endpoint.user, automation)

    result = _call(endpoint, "publish_workflow", {"workflow_id": workflow.id})

    assert result.isError is True
    assert result.content[0].text == "Tool 'publish_workflow' not found."
    assert not _published(workflow.id).exists()


@pytest.mark.django_db
def test_publish_needs_the_publish_permission(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["publish_workflow"])
    automation = data_fixture.create_automation_application(
        workspace=endpoint.workspace
    )
    workflow, _ = create_workflow(endpoint.user, automation)
    check_permissions = CoreHandler.check_permissions

    def deny_publish(self, actor, operation_name, *args, **kwargs):
        if operation_name == PublishAutomationWorkflowOperationType.type:
            raise PermissionException(actor)
        return check_permissions(self, actor, operation_name, *args, **kwargs)

    with patch.object(CoreHandler, "check_permissions", deny_publish):
        result = _call(endpoint, "publish_workflow", {"workflow_id": workflow.id})

    assert result.isError is True
    assert "permission" in result.content[0].text
    assert not _published(workflow.id).exists()


@pytest.mark.django_db
def test_publish_refuses_a_workflow_of_another_workspace(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["publish_workflow"])
    # The user is a member of the other workspace too.
    other = data_fixture.create_automation_application(
        workspace=data_fixture.create_workspace(user=endpoint.user)
    )
    workflow, _ = create_workflow(endpoint.user, other)

    result = _call(endpoint, "publish_workflow", {"workflow_id": workflow.id})

    assert result.isError is True
    assert result.content[0].text == "Not found in this workspace."
    assert not _published(workflow.id).exists()


@pytest.mark.django_db(transaction=True)
def test_publish_refuses_the_published_copy_itself(data_fixture):
    endpoint, _, _, workflow = _build_workflow_over_mcp(data_fixture)
    _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))
    copy = _published(workflow["id"]).get()

    result = _call(endpoint, "publish_workflow", {"workflow_id": copy.id})

    assert result.isError is True
    assert result.content[0].text == "Not found in this workspace."


@pytest.mark.django_db
def test_publish_refuses_untrusted_content_like_the_api(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["publish_workflow"])
    automation = data_fixture.create_automation_application(
        workspace=endpoint.workspace
    )
    workflow, trigger = create_workflow(endpoint.user, automation)
    _add_create_row_node(endpoint, workflow, trigger)
    workflow.untrusted_content = True
    workflow.save(update_fields=["untrusted_content"])

    result = _call(endpoint, "publish_workflow", {"workflow_id": workflow.id})

    assert result.isError is True
    assert (
        result.content[0].text
        == "Review and trust the imported content before publishing."
    )
    assert not _published(workflow.id).exists()


def _add_create_row_node(endpoint, workflow, reference_node):
    """An action node after the reference node, with no table."""

    return create_node(
        endpoint.user,
        workflow,
        "local_baserow_create_row",
        service={},
        reference_node_id=reference_node.id,
    )


@pytest.mark.django_db
def test_publish_refuses_a_workflow_without_a_trigger(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["publish_workflow"])
    automation = data_fixture.create_automation_application(
        workspace=endpoint.workspace
    )
    workflow = data_fixture.create_automation_workflow(
        user=endpoint.user, automation=automation, create_trigger=False
    )

    result = _call(endpoint, "publish_workflow", {"workflow_id": workflow.id})

    assert result.isError is True
    assert result.content[0].text == (
        "This workflow has no trigger, so it would never run. Nothing was published."
    )
    assert not _published(workflow.id).exists()


@pytest.mark.django_db
def test_publish_refuses_a_workflow_with_nothing_after_its_trigger(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["publish_workflow"])
    automation = data_fixture.create_automation_application(
        workspace=endpoint.workspace
    )
    workflow, _ = create_workflow(endpoint.user, automation)

    result = _call(endpoint, "publish_workflow", {"workflow_id": workflow.id})

    assert result.isError is True
    assert result.content[0].text == (
        "This workflow has no action after its trigger, so it would do nothing. "
        "Nothing was published."
    )
    assert not _published(workflow.id).exists()


@pytest.mark.django_db(transaction=True)
def test_publish_refuses_a_workflow_left_empty_over_mcp(data_fixture):
    endpoint, orders, _, workflow = _build_workflow_over_mcp(data_fixture)
    endpoint.allowed_tools = [*TOOLS, "delete_nodes"]
    endpoint.save()
    nodes = AutomationNode.objects.filter(workflow_id=workflow["id"])
    for node in nodes.order_by("-id"):
        _json(_call(endpoint, "delete_nodes", {"node_ids": [node.id]}))

    result = _call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]})

    assert result.isError is True
    assert "no trigger" in result.content[0].text
    assert not _published(workflow["id"]).exists()


@pytest.mark.django_db(transaction=True)
def test_publish_of_a_sound_workflow_has_no_warnings(data_fixture):
    endpoint, _, _, workflow = _build_workflow_over_mcp(data_fixture)

    result = _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))

    assert "warnings" not in result


@pytest.mark.django_db(transaction=True)
def test_publish_warns_about_a_row_trigger_and_action_with_no_table(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["publish_workflow"])
    automation = data_fixture.create_automation_application(
        workspace=endpoint.workspace
    )
    workflow, trigger = create_workflow(endpoint.user, automation)
    action = _add_create_row_node(endpoint, workflow, trigger)

    result = _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow.id}))

    assert result["published_workflow"]["state"] == "live"
    assert result["warnings"] == [
        f"Node {trigger.id} ({trigger.label}): no table is set, so it never fires.",
        f"Node {action.id} ({action.label}): no table is set, so every run fails here.",
    ]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("node_type", ["update_row", "delete_row"])
def test_publish_warns_about_a_row_id_left_empty_by_a_bad_formula(
    data_fixture, node_type
):
    endpoint, orders, log, _ = _build_workflow_over_mcp(data_fixture)
    automation = Automation.objects.filter(workspace=endpoint.workspace).get()
    values = (
        {"values": [{"field_id": log["primary_field"]["id"], "value": "Changed"}]}
        if node_type == "update_row"
        else {}
    )
    created = _json(
        _call(
            endpoint,
            "create_workflows",
            {
                "automation_id": automation.id,
                "workflows": [
                    {
                        "name": "Bad row",
                        "trigger": {
                            "ref": "trigger",
                            "label": "Order created",
                            "type": "rows_created",
                            "rows_triggers_settings": {"table_id": orders["id"]},
                        },
                        "nodes": [
                            {
                                "ref": "change",
                                "label": "Change it",
                                "type": node_type,
                                "previous_node_ref": "trigger",
                                "table_id": log["id"],
                                "row_id": "get('previous_node.nothing.0.id')",
                                **values,
                            }
                        ],
                    }
                ],
            },
        )
    )
    (workflow,) = created["created_workflows"]
    assert created["formula_errors"][0]["field"] == "row_id"
    node = AutomationNode.objects.get(workflow_id=workflow["id"], label="Change it")

    result = _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))

    assert result["warnings"] == [
        f"Node {node.id} (Change it): no row_id is set, so every run fails here."
    ]


@pytest.mark.django_db
def test_create_workflows_says_the_result_is_a_draft(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["create_workflows"])

    async def callback(client):
        return (await client.list_tools()).tools

    (tool,) = _session(endpoint, callback)

    assert "drafts" in tool.description
    assert "publish_workflow" in tool.description


@pytest.mark.django_db(transaction=True)
def test_create_workflows_reports_the_state_of_a_reused_live_workflow(data_fixture):
    endpoint, orders, log, workflow = _build_workflow_over_mcp(data_fixture)
    _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))

    automation = Automation.objects.get(workflows=workflow["id"])
    result = _json(
        _call(
            endpoint,
            "create_workflows",
            {
                "automation_id": automation.id,
                "workflows": [
                    {
                        "name": "Log new orders",
                        "trigger": {
                            "ref": "trigger",
                            "label": "Order created",
                            "type": "rows_created",
                            "rows_triggers_settings": {"table_id": orders["id"]},
                        },
                        "nodes": [],
                    }
                ],
            },
        )
    )

    assert result["reused_workflows"][0]["state"] == "live"


@pytest.mark.django_db
def test_publish_tells_a_client_what_publishing_does(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["publish_workflow"])

    async def callback(client):
        return (await client.list_tools()).tools

    (tool,) = _session(endpoint, callback)

    assert tool.annotations.destructiveHint is True
    assert "approval" in tool.description
    assert "earlier nodes" in tool.description
    assert "fresh error count" in tool.description
    assert "list_nodes" not in tool.description
