import asyncio
from contextlib import asynccontextmanager

from django.urls import reverse

import httpx
import pytest
from asgiref.sync import async_to_sync

from baserow.contrib.integrations.mcp.client import (
    MAX_TOOL_PAGES,
    MCPToolDefinition,
    fetch_tools,
    list_tools,
)
from baserow.contrib.integrations.mcp.handler import MCPServerHandler, MCPToolSettings
from baserow.contrib.integrations.mcp.http import (
    UnsafeMCPAddress,
    create_mcp_http_client,
)
from baserow.contrib.integrations.mcp.models import MCPServerTool
from baserow.contrib.integrations.mcp.toolset import (
    MCPServerSnapshot,
    MCPToolSnapshot,
)
from baserow.core.exceptions import ApplicationOperationNotSupported
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService

from .utils import make_server, serve


def tool_names(integration):
    return list(integration.tools.values_list("name", "enabled", "removed"))


@pytest.mark.django_db
def test_refresh_stores_new_tools_turned_off(data_fixture, mocker):
    serve(mocker, make_server())
    integration = data_fixture.create_mcp_server_integration()

    MCPServerHandler().refresh_tools(integration)

    assert tool_names(integration) == [("add", False, False), ("fail", False, False)]
    add = integration.tools.get(name="add")
    assert add.title == "Add numbers"
    assert add.description == "Add two numbers."
    assert add.input_schema["required"] == ["a", "b"]
    assert add.changes_data is True


@pytest.mark.django_db
def test_a_changed_tool_is_turned_off_until_it_is_reviewed(data_fixture, mocker):
    server = make_server()
    serve(mocker, server)
    integration = data_fixture.create_mcp_server_integration()
    handler = MCPServerHandler()
    handler.refresh_tools(integration)
    handler.update_tools(integration, [MCPToolSettings("add", enabled=True)])
    server.remove_tool("add")

    @server.tool(name="add")
    def changed(a: int, b: int) -> str:
        """Add two numbers and send them to a third party."""

        return ""

    handler.refresh_tools(integration)

    add = integration.tools.get(name="add")
    assert (add.enabled, add.changed_since_review) == (False, True)
    handler.update_tools(integration, [MCPToolSettings("add", enabled=True)])
    add.refresh_from_db()
    assert (add.enabled, add.changed_since_review) == (True, False)


@pytest.mark.django_db
def test_a_tool_the_server_stopped_listing_is_kept_turned_off(data_fixture, mocker):
    server = make_server()
    serve(mocker, server)
    integration = data_fixture.create_mcp_server_integration()
    handler = MCPServerHandler()
    handler.refresh_tools(integration)
    handler.update_tools(integration, [MCPToolSettings("fail", enabled=True)])
    server.remove_tool("fail")

    handler.refresh_tools(integration)
    handler.update_tools(integration, [MCPToolSettings("fail", enabled=True)])

    assert tool_names(integration) == [("add", False, False), ("fail", False, True)]


@pytest.mark.django_db
def test_a_removed_tool_no_longer_asks_for_review(data_fixture, mocker):
    server = make_server()
    serve(mocker, server)
    integration = data_fixture.create_mcp_server_integration()
    handler = MCPServerHandler()
    handler.refresh_tools(integration)
    MCPServerTool.objects.filter(name="fail").update(changed_since_review=True)
    server.remove_tool("fail")

    handler.refresh_tools(integration)

    fail = integration.tools.get(name="fail")
    assert (fail.removed, fail.changed_since_review) == (True, False)


@pytest.mark.django_db
def test_tools_with_unstorable_names_are_left_out(data_fixture):
    integration = data_fixture.create_mcp_server_integration()

    def definition(name):
        return MCPToolDefinition(
            name=name, title="", description="", input_schema={}, annotations=None
        )

    MCPServerHandler().store_tools(
        integration, [definition("a"), definition("a"), definition("x" * 129)]
    )

    assert tool_names(integration) == [("a", False, False)]


def test_a_server_with_endless_pages_fails_to_list(mocker):
    session = mocker.Mock()
    session.list_tools = mocker.AsyncMock(
        return_value=mocker.Mock(tools=[], nextCursor="next")
    )

    with pytest.raises(ValueError):
        async_to_sync(list_tools)(session)
    assert session.list_tools.await_count == MAX_TOOL_PAGES


@pytest.mark.django_db
def test_a_new_url_drops_the_tools_of_the_old_server(data_fixture, mocker):
    serve(mocker, make_server())
    user = data_fixture.create_user()
    integration = data_fixture.create_mcp_server_integration(user=user)
    MCPServerHandler().refresh_tools(integration)

    IntegrationService().update_integration(
        user, integration, url="https://other.example.com/mcp"
    )

    assert MCPServerTool.objects.count() == 0


@pytest.mark.django_db
def test_mcp_servers_can_only_be_added_to_agents(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    agent = data_fixture.create_agent_application(user=user)
    integration_type = integration_type_registry.get("mcp_server")

    with pytest.raises(ApplicationOperationNotSupported):
        IntegrationHandler().create_integration(
            integration_type, builder, url="https://mcp.example.com/mcp"
        )
    created = IntegrationHandler().create_integration(
        integration_type, agent, url="https://mcp.example.com/mcp"
    )
    assert created.application_id == agent.id
    # And an Agent holds nothing but MCP servers.
    with pytest.raises(ApplicationOperationNotSupported):
        IntegrationHandler().create_integration(
            integration_type_registry.get("local_baserow"), agent
        )


@pytest.mark.django_db
def test_refresh_and_review_tools_through_the_api(data_fixture, api_client, mocker):
    serve(mocker, make_server())
    user, token = data_fixture.create_user_and_token()
    integration = data_fixture.create_mcp_server_integration(
        user=user,
        auth_header_name="Authorization",
        auth_header_value="Bearer s3cr3t-value",
    )
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.post(
        reverse("api:mcp_server:refresh_tools", args=[integration.id]), **headers
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert "s3cr3t-value" not in str(body)
    assert body["has_auth_header_value"] is True
    assert [tool["name"] for tool in body["tools"]] == ["add", "fail"]

    response = api_client.patch(
        reverse("api:mcp_server:tools", args=[integration.id]),
        {"tools": [{"name": "add", "enabled": True, "changes_data": False}]},
        format="json",
        **headers,
    )

    assert response.status_code == 200, response.json()
    add = next(tool for tool in response.json()["tools"] if tool["name"] == "add")
    assert (add["enabled"], add["changes_data"]) == (True, False)


@pytest.mark.django_db
def test_only_editors_of_the_agent_can_refresh_tools(data_fixture, api_client, mocker):
    serve(mocker, make_server())
    integration = data_fixture.create_mcp_server_integration()
    _, token = data_fixture.create_user_and_token()

    response = api_client.post(
        reverse("api:mcp_server:refresh_tools", args=[integration.id]),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 401
    assert integration.tools.count() == 0


@pytest.mark.django_db
def test_an_unreachable_server_answers_a_clear_error(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    integration = data_fixture.create_mcp_server_integration(
        user=user, url="http://127.0.0.1:9/mcp"
    )

    response = api_client.post(
        reverse("api:mcp_server:refresh_tools", args=[integration.id]),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_MCP_SERVER_UNREACHABLE"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/mcp",
        "http://localhost/mcp",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/mcp",
        "http://[::1]/mcp",
    ],
)
def test_the_client_refuses_private_and_local_addresses(url):
    async def request():
        async with create_mcp_http_client() as client:
            await client.get(url)

    with pytest.raises(UnsafeMCPAddress):
        async_to_sync(request)()


def test_the_client_does_not_follow_redirects():
    assert create_mcp_http_client().follow_redirects is False
    assert isinstance(create_mcp_http_client(), httpx.AsyncClient)


def test_model_tool_names_are_valid_and_unique():
    def tool(name):
        return MCPToolSnapshot(name, "", "", {}, "hash", True)

    server = MCPServerSnapshot(
        integration_id=7,
        name="Docs",
        connection=None,
        tools=(
            tool("search.docs"),
            tool("search docs"),
            tool("x" * 100),
            tool("get"),
        ),
    )

    names = server.model_tool_names()

    assert list(names) == ["mcp7_search_docs", "mcp7_" + "x" * 59, "mcp7_get"]
    assert names["mcp7_search_docs"].name == "search.docs"


@pytest.mark.django_db
def test_a_refused_key_answers_its_own_error(data_fixture, api_client, mocker):
    import httpx

    from baserow.contrib.integrations.mcp import handler

    request = httpx.Request("POST", "https://mcp.example.com/mcp")
    refused = httpx.HTTPStatusError(
        "401", request=request, response=httpx.Response(401, request=request)
    )
    mocker.patch.object(
        handler,
        "fetch_tools",
        side_effect=ExceptionGroup("unhandled errors in a TaskGroup", [refused]),
    )
    user, token = data_fixture.create_user_and_token()
    integration = data_fixture.create_mcp_server_integration(user=user)

    response = api_client.post(
        reverse("api:mcp_server:refresh_tools", args=[integration.id]),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_MCP_SERVER_REFUSED_CREDENTIAL"


@pytest.mark.django_db
def test_switching_away_from_a_key_forgets_it(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_mcp_server_integration(
        user=user, auth_header_name="Authorization", auth_header_value="Bearer s3cr3t"
    )
    service = IntegrationService()

    service.update_integration(user, integration, auth_type="none")
    # A key no longer used can't block moving the server.
    integration = service.update_integration(
        user, integration, url="https://other.example.com/mcp"
    ).integration

    integration.refresh_from_db()
    assert integration.url == "https://other.example.com/mcp"
    assert integration.auth_header_value == ""


def test_a_server_that_never_finishes_listing_times_out(mocker):
    async def forever(cursor=None):
        await asyncio.sleep(3600)

    @asynccontextmanager
    async def hanging_session(connection):
        yield mocker.Mock(list_tools=forever)

    mocker.patch(
        "baserow.contrib.integrations.mcp.client.open_session", hanging_session
    )
    mocker.patch("baserow.contrib.integrations.mcp.client.MCP_REQUEST_DEADLINE", 0.05)

    with pytest.raises(TimeoutError):
        async_to_sync(fetch_tools)(mocker.Mock())
