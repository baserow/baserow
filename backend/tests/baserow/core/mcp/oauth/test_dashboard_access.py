"""Dashboards over MCP: a read-only connection reads them, and editing is turned on
in Settings."""

from django.shortcuts import reverse

import pytest

from baserow.contrib.dashboard.widgets.models import Widget
from baserow.core.mcp.groups import mcp_tool_group_registry
from baserow.core.mcp.registries import mcp_tool_registry
from tests.baserow.core.mcp.oauth.helpers import obtain_tokens
from tests.baserow.core.mcp.test_mcp_streamable_http import _call as _rpc_call
from tests.baserow.core.mcp.test_mcp_streamable_http import _post

EDIT_TOOLS = ["create_dashboards", "create_widgets", "update_widgets"]


def _read_only_preset():
    groups = {g.type for g in mcp_tool_group_registry.get_all() if g.read_only_preset}
    return [
        tool.name
        for tool in mcp_tool_registry.get_enabled_tools()
        if tool.group in groups
    ]


@pytest.mark.django_db(transaction=True)
def test_read_only_connection_reads_dashboards_and_edit_is_turned_on_later(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    data_fixture.create_summary_widget(dashboard=dashboard, title="Total")
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    amount = data_fixture.create_number_field(table=table)
    read_only = _read_only_preset()
    assert {"list_dashboards", "list_widgets", "get_widget_data"} <= set(read_only)
    tokens = obtain_tokens(client, api_client, token, workspace, read_only)
    arguments = {
        "dashboard_id": dashboard.id,
        "widgets": [
            {
                "type": "summary",
                "title": "Sum",
                "table_id": table.id,
                "field_id": amount.id,
                "aggregation_type": "sum",
            }
        ],
    }

    listed = _post(
        _rpc_call("list_widgets", {"dashboard_id": dashboard.id}),
        tokens["access_token"],
    )
    assert listed.json()["result"]["isError"] is False
    refused = _post(_rpc_call("create_widgets", arguments), tokens["access_token"])
    assert refused.json()["result"]["isError"] is True
    assert Widget.objects.filter(dashboard=dashboard).count() == 1

    response = api_client.patch(
        reverse(
            "api:mcp:oauth_connection",
            kwargs={"connection_id": tokens["endpoint_id"]},
        ),
        {"allowed_tools": [*read_only, *EDIT_TOOLS]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.content

    created = _post(_rpc_call("create_widgets", arguments), tokens["access_token"])
    result = created.json()["result"]
    assert result["isError"] is False, result
    assert Widget.objects.filter(dashboard=dashboard).count() == 2
