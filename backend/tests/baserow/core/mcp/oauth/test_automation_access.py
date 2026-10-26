"""The acceptance path of automation over MCP: connect read-only, then turn the
automation tools on in Settings."""

from django.shortcuts import reverse

import pytest

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from tests.baserow.contrib.automation.mcp.test_mcp_automation_tools import (
    EDIT_TOOLS,
    READ_TOOLS,
    _workflow,
)
from tests.baserow.core.mcp.oauth.helpers import obtain_tokens
from tests.baserow.core.mcp.test_mcp_streamable_http import _call as _rpc_call
from tests.baserow.core.mcp.test_mcp_streamable_http import _post


@pytest.mark.django_db(transaction=True)
def test_automation_can_be_turned_on_for_a_read_only_connection(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    tokens = obtain_tokens(client, api_client, token, workspace, READ_TOOLS)
    arguments = {"automation_id": automation.id, "workflows": [_workflow(table)]}

    refused = _post(_rpc_call("create_workflows", arguments), tokens["access_token"])
    assert refused.json()["result"]["isError"] is True
    assert not AutomationWorkflow.objects.filter(automation=automation).exists()

    response = api_client.patch(
        reverse(
            "api:mcp:oauth_connection",
            kwargs={"connection_id": tokens["endpoint_id"]},
        ),
        {"allowed_tools": [*READ_TOOLS, *EDIT_TOOLS]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.content

    created = _post(_rpc_call("create_workflows", arguments), tokens["access_token"])
    result = created.json()["result"]
    assert result["isError"] is False, result
    workflow = AutomationWorkflow.objects.get(automation=automation)
    assert workflow.name == "Orders"
    assert AutomationNode.objects.filter(workflow=workflow).count() == 2
