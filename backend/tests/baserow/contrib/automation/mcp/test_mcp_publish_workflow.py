"""Publishing and pausing a workflow over MCP."""

import json
from threading import Thread
from unittest.mock import patch

from django.db import connection, transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.automation.history.models import AutomationWorkflowHistory
from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.tools import workflows as workflows_tools
from baserow.contrib.automation.workflows.actions import (
    UpdateAutomationWorkflowActionType,
)
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.operations import (
    PublishAutomationWorkflowOperationType,
    UpdateAutomationWorkflowOperationType,
)
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
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
    "pause_workflow",
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
def test_an_action_deleted_while_publishing_waits_for_the_publication(data_fixture):
    endpoint, orders, log, workflow = _build_workflow_over_mcp(data_fixture)
    log_node = AutomationNode.objects.get(workflow_id=workflow["id"], label="Log it")
    check = workflows_tools.check_workflow_can_run
    deletion = Thread(target=_delete_node, args=(endpoint.user, log_node.id))
    waited = []

    def check_then_delete(ctx, published):
        warnings = check(ctx, published)
        # Another request deletes the action after the checks ran.
        deletion.start()
        deletion.join(timeout=2)
        waited.append(deletion.is_alive())
        return warnings

    with patch.object(workflows_tools, "check_workflow_can_run", check_then_delete):
        _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))
    deletion.join(timeout=30)

    assert waited == [True]
    assert not AutomationNode.objects.filter(id=log_node.id).exists()
    _create_order(endpoint.user, orders)
    assert _logged(log) == ["Written"]


def _delete_node(user, node_id):
    try:
        with transaction.atomic():
            AutomationNodeService().delete_node(user, node_id)
    finally:
        connection.close()


def _update_node(user, node_id, **values):
    try:
        with transaction.atomic():
            AutomationNodeService().update_node(user, node_id, **values)
    finally:
        connection.close()


def _while_publishing(target, *args, **kwargs):
    """
    Runs `target` from another connection when the publication starts, after
    anything the tool checks on the draft beforehand.
    """

    publish = AutomationWorkflowService.publish
    other = Thread(target=target, args=args, kwargs=kwargs)

    def publish_after_the_other_request(self, *publish_args, **kwargs):
        other.start()
        other.join(timeout=5)
        return publish(self, *publish_args, **kwargs)

    return other, patch.object(
        AutomationWorkflowService, "publish", publish_after_the_other_request
    )


@pytest.mark.django_db(transaction=True)
def test_a_row_id_cleared_while_publishing_is_reported(data_fixture):
    endpoint, orders, log, _ = _build_workflow_over_mcp(data_fixture)
    automation = Automation.objects.filter(workspace=endpoint.workspace).get()
    (workflow,) = _json(
        _call(
            endpoint,
            "create_workflows",
            {
                "automation_id": automation.id,
                "workflows": [
                    {
                        "name": "Change row",
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
                                "type": "update_row",
                                "previous_node_ref": "trigger",
                                "table_id": log["id"],
                                "row_id": "1",
                                "values": [
                                    {
                                        "field_id": log["primary_field"]["id"],
                                        "value": "Changed",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        )
    )["created_workflows"]
    node = AutomationNode.objects.get(workflow_id=workflow["id"], label="Change it")
    # An edit of the node's service only, as the editor sends it.
    other, patched = _while_publishing(
        _update_node, endpoint.user, node.id, service={"row_id": ""}
    )

    with patched:
        result = _json(
            _call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]})
        )
    other.join(timeout=30)

    published = AutomationNode.objects.get(
        workflow__automation__published_from_id=workflow["id"], label="Change it"
    )
    assert published.service.specific.row_id["formula"] == ""
    assert result["published_workflow"]["state"] == "live"
    assert result["warnings"] == [
        f"Node {node.id} (Change it): A row ID is required to update a row. "
        "Every run fails here."
    ]


@pytest.mark.django_db(transaction=True)
def test_a_refused_publication_leaves_the_live_copy_running(data_fixture):
    endpoint, orders, log, workflow = _build_workflow_over_mcp(data_fixture)
    endpoint.allowed_tools = [*TOOLS, "delete_nodes"]
    endpoint.save(update_fields=["allowed_tools"])
    _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))
    (live,) = _published(workflow["id"])
    log_node = AutomationNode.objects.get(workflow_id=workflow["id"], label="Log it")
    other, patched = _while_publishing(_delete_node, endpoint.user, log_node.id)

    with patched:
        result = _call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]})
    other.join(timeout=30)

    assert result.isError is True
    assert "no action after its trigger" in result.content[0].text
    assert not AutomationNode.objects.filter(id=log_node.id).exists()
    assert list(_published(workflow["id"])) == [live]
    live.refresh_from_db()
    assert live.state == WorkflowState.LIVE
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
        f"Node {trigger.id} ({trigger.label}): No table is selected. It never fires.",
        f"Node {action.id} ({action.label}): No table is selected. "
        "Every run fails here.",
    ]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "node_type,warning",
    [
        ("update_row", "A row ID is required to update a row. Every run fails here."),
        # A delete with no row ID deletes nothing, it doesn't fail.
        ("delete_row", "No row ID is set, so every run deletes nothing."),
    ],
)
def test_publish_warns_about_a_row_id_left_empty_by_a_bad_formula(
    data_fixture, node_type, warning
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

    assert result["warnings"] == [f"Node {node.id} (Change it): {warning}"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("empty_row_id", ["", "''"])
def test_publish_warns_about_a_row_id_emptied_by_an_update(data_fixture, empty_row_id):
    endpoint, orders, log, _ = _build_workflow_over_mcp(data_fixture)
    automation = Automation.objects.filter(workspace=endpoint.workspace).get()
    created = _json(
        _call(
            endpoint,
            "create_workflows",
            {
                "automation_id": automation.id,
                "workflows": [
                    {
                        "name": "Emptied row",
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
                                "type": "update_row",
                                "previous_node_ref": "trigger",
                                "table_id": log["id"],
                                "row_id": "1",
                                "values": [
                                    {
                                        "field_id": log["primary_field"]["id"],
                                        "value": "Changed",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        )
    )
    (workflow,) = created["created_workflows"]
    node = AutomationNode.objects.get(workflow_id=workflow["id"], label="Change it")
    _json(
        _call(
            endpoint,
            "update_nodes",
            {
                "workflow_id": workflow["id"],
                "nodes": [{"node_id": node.id, "row_id": empty_row_id}],
            },
        )
    )
    node = AutomationNode.objects.get(id=node.id).specific
    assert node.service.specific.row_id["formula"] == ""

    result = _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))

    assert result["warnings"] == [
        f"Node {node.id} (Change it): A row ID is required to update a row. "
        "Every run fails here."
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
    assert "pause_workflow" in tool.description


@pytest.mark.django_db(transaction=True)
def test_pause_stops_a_live_workflow_until_it_is_published_again(data_fixture):
    endpoint, orders, log, workflow = _build_workflow_over_mcp(data_fixture)
    _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))
    _create_order(endpoint.user, orders)
    assert _logged(log) == ["Written"]
    runs = AutomationWorkflowHistory.objects.filter(original_workflow=workflow["id"])
    assert runs.count() == 1

    result = _json(_call(endpoint, "pause_workflow", {"workflow_id": workflow["id"]}))

    assert result == {
        "paused_workflow": {
            "id": workflow["id"],
            "name": "Log new orders",
            "state": "paused",
        },
        "changed": True,
    }
    assert _listed_state(endpoint, workflow["id"]) == "paused"

    # An event neither starts a run nor writes a row.
    _create_order(endpoint.user, orders)
    assert _logged(log) == ["Written"]
    assert runs.count() == 1

    republished = _json(
        _call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]})
    )
    assert republished["published_workflow"]["state"] == "live"
    assert _listed_state(endpoint, workflow["id"]) == "live"

    _create_order(endpoint.user, orders)
    assert _logged(log) == ["Written", "Written"]


@pytest.mark.django_db(transaction=True)
def test_pause_acts_on_the_latest_published_version(data_fixture):
    endpoint, orders, log, workflow = _build_workflow_over_mcp(data_fixture)
    for _ in range(2):
        _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))

    _json(_call(endpoint, "pause_workflow", {"workflow_id": workflow["id"]}))

    _create_order(endpoint.user, orders)
    assert _logged(log) == []
    assert not _published(workflow["id"]).filter(state=WorkflowState.LIVE).exists()


@pytest.mark.django_db(transaction=True)
def test_pause_of_a_paused_workflow_changes_nothing(data_fixture):
    endpoint, _, _, workflow = _build_workflow_over_mcp(data_fixture)
    _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))
    _json(_call(endpoint, "pause_workflow", {"workflow_id": workflow["id"]}))

    with patch.object(UpdateAutomationWorkflowActionType, "do") as update:
        result = _json(
            _call(endpoint, "pause_workflow", {"workflow_id": workflow["id"]})
        )

    update.assert_not_called()
    assert result["changed"] is False
    assert result["paused_workflow"]["state"] == "paused"


def _pause_survives_cleanup(endpoint, workflow):
    AutomationWorkflowHandler().clear_old_history()

    assert _listed_state(endpoint, workflow["id"]) == "paused"
    with patch.object(UpdateAutomationWorkflowActionType, "do") as update:
        result = _json(
            _call(endpoint, "pause_workflow", {"workflow_id": workflow["id"]})
        )
    update.assert_not_called()
    assert result["changed"] is False


@pytest.mark.django_db(transaction=True)
def test_a_paused_workflow_survives_the_history_cleanup(data_fixture):
    endpoint, _, _, workflow = _build_workflow_over_mcp(data_fixture)
    _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))
    _json(_call(endpoint, "pause_workflow", {"workflow_id": workflow["id"]}))

    _pause_survives_cleanup(endpoint, workflow)


@pytest.mark.django_db(transaction=True)
def test_a_paused_workflow_with_an_older_run_survives_the_history_cleanup(
    data_fixture,
):
    endpoint, orders, log, workflow = _build_workflow_over_mcp(data_fixture)
    _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))
    _create_order(endpoint.user, orders)
    assert _logged(log) == ["Written"]
    _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))
    _json(_call(endpoint, "pause_workflow", {"workflow_id": workflow["id"]}))

    _pause_survives_cleanup(endpoint, workflow)

    # It can be made live again from the update the UI uses.
    AutomationWorkflowHandler().update_workflow(
        AutomationWorkflow.objects.get(id=workflow["id"]), state=WorkflowState.LIVE
    )
    assert _listed_state(endpoint, workflow["id"]) == "live"


@pytest.mark.django_db
def test_pause_refuses_a_workflow_never_published(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["pause_workflow"])
    automation = data_fixture.create_automation_application(
        workspace=endpoint.workspace
    )
    workflow, _ = create_workflow(endpoint.user, automation)

    result = _call(endpoint, "pause_workflow", {"workflow_id": workflow.id})

    assert result.isError is True
    assert result.content[0].text == (
        "This workflow has never been published, so it isn't running and there is "
        "nothing to pause."
    )


@pytest.mark.django_db(transaction=True)
def test_pause_leaves_a_disabled_workflow_disabled(data_fixture):
    endpoint, _, _, workflow = _build_workflow_over_mcp(data_fixture)
    _json(_call(endpoint, "publish_workflow", {"workflow_id": workflow["id"]}))
    _published(workflow["id"]).update(state=WorkflowState.DISABLED)

    result = _call(endpoint, "pause_workflow", {"workflow_id": workflow["id"]})

    assert result.isError is True
    assert result.content[0].text == (
        "This workflow was disabled after too many failed runs, so it isn't running "
        "and stays disabled. Publishing it again makes it live."
    )
    assert _listed_state(endpoint, workflow["id"]) == "disabled"


@pytest.mark.django_db
def test_pause_refuses_a_workflow_of_another_workspace(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["pause_workflow"])
    other = data_fixture.create_automation_application(
        workspace=data_fixture.create_workspace(user=endpoint.user)
    )
    workflow, _ = create_workflow(endpoint.user, other)

    result = _call(endpoint, "pause_workflow", {"workflow_id": workflow.id})

    assert result.isError is True
    assert result.content[0].text == "Not found in this workspace."


@pytest.mark.django_db
def test_automation_read_cannot_pause(data_fixture):
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

    result = _call(endpoint, "pause_workflow", {"workflow_id": workflow.id})

    assert result.isError is True
    assert result.content[0].text == "Tool 'pause_workflow' not found."


@pytest.mark.django_db
def test_pause_needs_the_update_permission(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["pause_workflow"])
    automation = data_fixture.create_automation_application(
        workspace=endpoint.workspace
    )
    workflow, _ = create_workflow(endpoint.user, automation)
    check_permissions = CoreHandler.check_permissions

    def deny_update(self, actor, operation_name, *args, **kwargs):
        if operation_name == UpdateAutomationWorkflowOperationType.type:
            raise PermissionException(actor)
        return check_permissions(self, actor, operation_name, *args, **kwargs)

    with patch.object(CoreHandler, "check_permissions", deny_update):
        result = _call(endpoint, "pause_workflow", {"workflow_id": workflow.id})

    assert result.isError is True
    assert "permission" in result.content[0].text
