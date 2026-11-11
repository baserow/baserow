"""A connection made with the "Read only" preset over the builder tools."""

import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.builder.pages.models import Page
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.mcp.groups import mcp_tool_group_registry
from baserow.core.mcp.registries import mcp_tool_registry


def _read_only_preset_tools():
    """The tools the consent page selects for the "Read only" preset."""

    groups = {g.type for g in mcp_tool_group_registry.get_all() if g.read_only_preset}
    return [tool.name for tool in mcp_tool_registry.get_all() if tool.group in groups]


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


@pytest.mark.django_db
def test_read_only_preset_reads_builders_and_refuses_to_write(
    data_fixture, builder_ctx
):
    endpoint = data_fixture.create_mcp_endpoint(
        user=builder_ctx["user"],
        workspace=builder_ctx["workspace"],
        allowed_tools=_read_only_preset_tools(),
    )
    builder = builder_ctx["builder"]
    page = builder_ctx["page"]

    async def callback(client):
        return (
            await client.list_tools(),
            await client.call_tool("list_builders", {}),
            await client.call_tool("list_pages", {"builder_id": builder.id}),
            await client.call_tool("list_elements", {"page_id": page.id}),
            await client.call_tool(
                "create_pages",
                {"builder_id": builder.id, "pages": [{"name": "Nope", "path": "/n"}]},
            ),
        )

    listed, builders, pages, elements, created = _session(endpoint, callback)

    tools = {tool.name: tool for tool in listed.tools}
    assert {"list_builders", "list_pages", "list_elements"} <= set(tools)
    assert all(tool.annotations.readOnlyHint for tool in tools.values())
    assert "create_pages" not in tools
    assert json.loads(builders.content[0].text)["applications"][0]["id"] == builder.id
    assert [p["name"] for p in json.loads(pages.content[0].text)["pages"]] == [
        "Home",
        "About",
    ]
    assert json.loads(elements.content[0].text)["elements"]
    assert created.isError is True
    assert not Page.objects.filter(builder=builder, name="Nope").exists()
