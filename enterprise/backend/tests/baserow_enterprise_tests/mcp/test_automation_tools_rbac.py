import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.tools.nodes import node_outputs
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


def _call(endpoint, name, arguments):
    async def inner():
        token = current_key.set(endpoint.key)
        try:
            async with client_session(BaserowMCPServer()._mcp_server) as client:
                return await client.call_tool(name, arguments)
        finally:
            current_key.reset(token)

    with transaction.atomic():
        return async_to_sync(inner)()


def _workflow_with_an_action(user, automation):
    workflow = AutomationWorkflowService().create_workflow(user, automation.id, "Flow")
    trigger = AutomationNodeService().create_node(
        user,
        automation_node_type_registry.get("local_baserow_rows_created"),
        workflow,
        service={},
    )
    AutomationNodeService().create_node(
        user,
        automation_node_type_registry.get("local_baserow_create_row"),
        workflow,
        reference_node_id=trigger.id,
        service={},
    )
    return workflow


@pytest.fixture
def team(enterprise_data_fixture, enable_enterprise, synced_roles):
    builder = enterprise_data_fixture.create_user()
    editor = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        custom_permissions=[(builder, "BUILDER"), (editor, "EDITOR")]
    )
    automation = enterprise_data_fixture.create_automation_application(
        workspace=workspace
    )
    return enterprise_data_fixture, workspace, automation, builder, editor


@pytest.mark.django_db(transaction=True)
def test_only_a_builder_can_publish_over_mcp(team):
    fixture, workspace, automation, builder, editor = team
    workflow = _workflow_with_an_action(builder, automation)
    copies = AutomationWorkflow.objects.filter(automation__published_from=workflow)

    endpoint = fixture.create_mcp_endpoint(
        user=editor, workspace=workspace, allowed_tools=["publish_workflow"]
    )
    result = _call(endpoint, "publish_workflow", {"workflow_id": workflow.id})

    assert result.isError is True
    assert "permission" in result.content[0].text
    assert not copies.exists()

    endpoint = fixture.create_mcp_endpoint(
        user=builder, workspace=workspace, allowed_tools=["publish_workflow"]
    )
    result = _call(endpoint, "publish_workflow", {"workflow_id": workflow.id})

    assert result.isError is False, result.content[0].text
    assert json.loads(result.content[0].text)["published_workflow"]["state"] == "live"


@pytest.mark.django_db(transaction=True)
def test_pause_uses_the_role_of_the_update_operation(team):
    fixture, workspace, automation, builder, editor = team
    workflow = _workflow_with_an_action(builder, automation)
    with transaction.atomic():
        AutomationWorkflowHandler().publish(workflow)
    copy = AutomationWorkflow.objects.get(automation__published_from=workflow)

    endpoint = fixture.create_mcp_endpoint(
        user=editor, workspace=workspace, allowed_tools=["pause_workflow"]
    )
    result = _call(endpoint, "pause_workflow", {"workflow_id": workflow.id})

    assert result.isError is True
    assert "permission" in result.content[0].text
    copy.refresh_from_db()
    assert copy.state == WorkflowState.LIVE

    endpoint = fixture.create_mcp_endpoint(
        user=builder, workspace=workspace, allowed_tools=["pause_workflow"]
    )
    result = _call(endpoint, "pause_workflow", {"workflow_id": workflow.id})

    assert result.isError is False, result.content[0].text
    copy.refresh_from_db()
    assert copy.state == WorkflowState.PAUSED


def _automation_builder_without_database_access(fixture, workspace, automation):
    """A user who may build the automation but has no access to anything else."""

    user = fixture.create_user()
    fixture.create_user_workspace(
        user=user, workspace=workspace, permissions="NO_ACCESS"
    )
    RoleAssignmentHandler().assign_role(
        user,
        workspace,
        role=Role.objects.get(uid="BUILDER"),
        scope=automation.application_ptr,
    )
    return user


@pytest.mark.django_db(transaction=True)
def test_list_nodes_hides_the_fields_of_a_table_the_user_cannot_see(team):
    fixture, workspace, automation, builder, _ = team
    table = fixture.create_database_table(
        database=fixture.create_database_application(workspace=workspace)
    )
    salary = fixture.create_text_field(table=table, name="Salary")
    workflow = AutomationWorkflowService().create_workflow(
        builder, automation.id, "Flow"
    )
    trigger = AutomationNodeService().create_node(
        builder,
        automation_node_type_registry.get("local_baserow_rows_created"),
        workflow,
        service={"table_id": table.id},
    )
    restricted = _automation_builder_without_database_access(
        fixture, workspace, automation
    )

    def list_nodes_as(user):
        endpoint = fixture.create_mcp_endpoint(
            user=user, workspace=workspace, allowed_tools=["list_nodes"]
        )
        result = _call(endpoint, "list_nodes", {"workflow_id": workflow.id})
        assert result.isError is False, result.content[0].text
        return result.content[0].text

    (node,) = json.loads(list_nodes_as(builder))["nodes"]
    assert node["output_schema"]["properties"][f"field_{salary.id}"] == {
        "title": "Salary",
        "type": "string",
    }

    text = list_nodes_as(restricted)
    (node,) = json.loads(text)["nodes"]
    assert node["id"] == trigger.id
    assert node["output_schema"] == {
        "formula_path": f"previous_node.{trigger.id}.0",
        "properties": {},
    }
    assert "Salary" not in text
    assert f"field_{salary.id}" not in text

    # The outputs formulas are checked against, which formula errors list.
    assert node_outputs(restricted, workflow)(trigger.id)["properties"] == {}
    assert node_outputs(builder, workflow)(trigger.id)["properties"]
