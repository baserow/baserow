from django.urls import reverse

import pytest
from rest_framework.status import HTTP_402_PAYMENT_REQUIRED

from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.registries import agent_tool_type_registry

ROW_COMMENT_TOOLS = {
    "list_row_comments": False,
    "search_row_comments": False,
    "create_row_comments": True,
}


def test_row_comment_tool_names_and_whether_they_change_data_stay_the_same():
    """Agents allow tools by name; change this only with a migration of them."""

    assert {
        tool_type.type: tool_type.changes_data
        for tool_type in agent_tool_type_registry.get_all()
        if type(tool_type).__module__.startswith("baserow_premium.")
    } == ROW_COMMENT_TOOLS


@pytest.mark.django_db
def test_row_comment_tools_are_locked_without_a_workspace_licence(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    agent = premium_data_fixture.create_agent_application(user=user)
    identity = premium_data_fixture.create_identity(workspace=agent.workspace)
    agent.run_as_subject_type, agent.run_as_subject_id = "auth.User", identity.id
    agent.save()
    # Allowed while the workspace had the licence.
    AgentHandler().set_allowed_tools(agent, ["list_tables", "search_row_comments"])
    url = reverse("api:agent:configuration", kwargs={"agent_id": agent.id})
    api_client.credentials(HTTP_AUTHORIZATION=f"JWT {token}")

    configuration = api_client.get(url).json()
    response = api_client.patch(
        url, {"allowed_tools": ["list_tables", "create_row_comments"]}, format="json"
    )

    assert {
        tool["name"] for tool in configuration["available_tools"] if tool["deactivated"]
    } == set(ROW_COMMENT_TOOLS)
    assert configuration["allowed_tools"] == ["list_tables"]
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"
