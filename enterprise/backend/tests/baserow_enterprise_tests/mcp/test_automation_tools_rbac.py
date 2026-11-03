import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.mcp import BaserowMCPServer, current_key


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
