"""The application builder read tools over MCP."""

import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.core.mcp import BaserowMCPServer, current_key

READ_TOOLS = [
    "list_builders",
    "list_pages",
    "list_data_sources",
    "list_elements",
    "list_actions",
]
KUMA_ONLY = ("ask_user", "navigate", "thought", "load_")


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


def _endpoint(data_fixture, builder_ctx, allowed_tools):
    return data_fixture.create_mcp_endpoint(
        user=builder_ctx["user"],
        workspace=builder_ctx["workspace"],
        allowed_tools=allowed_tools,
    )


@pytest.mark.django_db
def test_builder_read_tools_over_mcp(data_fixture, builder_ctx):
    endpoint = _endpoint(data_fixture, builder_ctx, READ_TOOLS)
    builder = builder_ctx["builder"]
    page = builder_ctx["page"]

    async def callback(client):
        return (
            await client.list_tools(),
            await client.call_tool("list_builders", {}),
            await client.call_tool("list_pages", {"builder_id": builder.id}),
            await client.call_tool("list_data_sources", {"page_id": page.id}),
            await client.call_tool("list_elements", {"page_id": page.id}),
            await client.call_tool("list_actions", {"page_id": page.id}),
        )

    listed, builders, pages, data_sources, elements, actions = _session(
        endpoint, callback
    )

    tools = {tool.name: tool for tool in listed.tools}
    assert set(tools) == set(READ_TOOLS)
    for tool in tools.values():
        assert tool.annotations.readOnlyHint is True
        for kuma_only in KUMA_ONLY:
            assert kuma_only not in tool.description
    load = lambda result: json.loads(result.content[0].text)  # noqa: E731
    assert load(builders)["applications"][0]["id"] == builder.id
    assert [p["name"] for p in load(pages)["pages"]] == ["Home", "About"]
    assert load(data_sources)["data_sources"][0]["name"] == "Products"
    element_ids = [e["id"] for e in load(elements)["elements"]]
    assert builder_ctx["footer"].id in element_ids
    assert load(actions)["workflow_actions"][0]["id"] == builder_ctx["action"].id


@pytest.mark.django_db
def test_builder_read_tools_over_mcp_hide_other_workspaces(data_fixture, builder_ctx):
    user = builder_ctx["user"]
    endpoint = data_fixture.create_mcp_endpoint(
        user=user,
        workspace=data_fixture.create_workspace(user=user),
        allowed_tools=READ_TOOLS,
    )

    async def callback(client):
        return [
            await client.call_tool(
                "list_pages", {"builder_id": builder_ctx["builder"].id}
            ),
            *[
                await client.call_tool(name, {"page_id": builder_ctx["page"].id})
                for name in ("list_data_sources", "list_elements", "list_actions")
            ],
        ]

    for result in _session(endpoint, callback):
        assert result.isError is True
        assert result.content[0].text == "Not found in this workspace."


@pytest.mark.django_db
def test_builder_read_tools_over_mcp_reject_unknown_arguments(
    data_fixture, builder_ctx
):
    endpoint = _endpoint(data_fixture, builder_ctx, READ_TOOLS)

    async def callback(client):
        return await client.call_tool("list_builders", {"thought": "why"})

    result = _session(endpoint, callback)

    assert result.isError is True
    assert "thought" in result.content[0].text
