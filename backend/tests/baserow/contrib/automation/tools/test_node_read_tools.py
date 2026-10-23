"""Tests for the node read tools shared by MCP and Kuma."""

from uuid import uuid4

import pytest

from baserow.contrib.automation.nodes.exceptions import AutomationNodeDoesNotExist
from baserow.contrib.automation.tools.nodes import get_node_in_workspace, list_nodes
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowDoesNotExist,
)

from .conftest import create_node, create_workflow


@pytest.mark.django_db
def test_list_nodes_in_execution_order_with_branches_and_output(automation_ctx):
    ctx, automation, table, name = automation_ctx
    workflow, trigger = create_workflow(ctx.user, automation, "Flow", table)
    big = str(uuid4())
    router = create_node(
        ctx.user,
        workflow,
        "router",
        label="Route",
        reference_node_id=trigger.id,
        service={"edges": [{"uid": big, "label": "Big"}]},
    )
    fallback = create_node(
        ctx.user,
        workflow,
        "local_baserow_create_row",
        label="Store",
        reference_node_id=router.id,
        service={"table_id": table.id},
    )
    email = create_node(
        ctx.user,
        workflow,
        "smtp_email",
        label="Mail",
        reference_node_id=router.id,
        output=big,
    )

    nodes = list_nodes(ctx, workflow.id)["nodes"]

    assert [node["id"] for node in nodes] == [
        trigger.id,
        router.id,
        email.id,
        fallback.id,
    ]
    assert nodes[0] == {
        "id": trigger.id,
        "label": trigger.label,
        "type": "local_baserow_rows_created",
        "output_schema": {
            "formula_path": f"previous_node.{trigger.id}.0",
            "properties": {
                "id": {"title": "Id", "type": "number"},
                f"field_{name.id}": {"title": "Name", "type": "string"},
            },
        },
    }
    assert nodes[1]["previous_node_ref"] == str(trigger.id)
    assert nodes[1]["edges"] == [{"label": "Big", "uid": big}]
    assert nodes[2]["previous_node_ref"] == str(router.id)
    assert nodes[2]["router_edge_label"] == "Big"
    assert nodes[2]["output_schema"] == {
        "formula_path": f"previous_node.{email.id}",
        "properties": {"success": {"title": "Success", "type": "boolean"}},
    }
    assert nodes[3]["previous_node_ref"] == str(router.id)
    assert "router_edge_label" not in nodes[3]
    assert nodes[3]["output_schema"]["formula_path"] == f"previous_node.{fallback.id}"


@pytest.mark.django_db
def test_list_nodes_of_a_workflow_elsewhere_is_not_found(data_fixture, automation_ctx):
    ctx, *_ = automation_ctx
    member_of = data_fixture.create_automation_application(
        workspace=data_fixture.create_workspace(user=ctx.user)
    )
    member_flow, _ = create_workflow(ctx.user, member_of)

    for workflow_id in (member_flow.id, 999999):
        with pytest.raises(AutomationWorkflowDoesNotExist):
            list_nodes(ctx, workflow_id)


@pytest.mark.django_db
def test_get_node_in_workspace_hides_other_workspaces(data_fixture, automation_ctx):
    ctx, automation, table, _ = automation_ctx
    _, trigger = create_workflow(ctx.user, automation, "Flow", table)
    member_of = data_fixture.create_automation_application(
        workspace=data_fixture.create_workspace(user=ctx.user)
    )
    _, member_trigger = create_workflow(ctx.user, member_of)
    stranger = data_fixture.create_user()
    _, stranger_trigger = create_workflow(
        stranger, data_fixture.create_automation_application(user=stranger)
    )

    assert get_node_in_workspace(ctx, trigger.id).id == trigger.id
    for node_id in (member_trigger.id, stranger_trigger.id, 999999):
        with pytest.raises(AutomationNodeDoesNotExist):
            get_node_in_workspace(ctx, node_id)
