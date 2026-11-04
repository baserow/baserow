"""The tools that write builders and pages, over MCP."""

import json

import pytest

from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.models import Page

from .test_mcp_builder_read_tools import READ_TOOLS, _endpoint, _session

WRITE_TOOLS = ["create_builder", "update_builder", "create_pages", "update_page"]


def _load(result):
    assert result.isError is False, result.content[0].text
    return json.loads(result.content[0].text)


def _calls(builder_ctx):
    return {
        "create_builder": {"name": "Portal", "theme": "eclipse"},
        "update_builder": {"builder_id": builder_ctx["builder"].id, "name": "Renamed"},
        "create_pages": {
            "builder_id": builder_ctx["builder"].id,
            "pages": [{"name": "New", "path": "/new"}],
        },
        "update_page": {
            "page_id": builder_ctx["page"].id,
            "page": {"path": "/home/:id"},
        },
    }


@pytest.mark.django_db
def test_write_tools_with_builder_edit_turned_on(data_fixture, builder_ctx):
    endpoint = _endpoint(data_fixture, builder_ctx, [*READ_TOOLS, *WRITE_TOOLS])
    calls = _calls(builder_ctx)

    async def callback(client):
        listed = await client.list_tools()
        results = {
            name: await client.call_tool(name, arguments)
            for name, arguments in calls.items()
        }
        return listed, results

    listed, results = _session(endpoint, callback)

    tools = {tool.name: tool for tool in listed.tools}
    for name in WRITE_TOOLS:
        assert tools[name].annotations.readOnlyHint is False
        assert tools[name].annotations.destructiveHint is (
            name in ("update_builder", "update_page")
        )
    assert set(tools["update_page"].inputSchema["properties"]) == {"page_id", "page"}

    created_builder = _load(results["create_builder"])["created_builder"]
    assert Builder.objects.filter(id=created_builder["id"]).exists()
    assert _load(results["update_builder"])["updated_builder"]["name"] == "Renamed"
    assert _load(results["create_pages"])["created_pages"][0]["path"] == "/new"
    assert _load(results["update_page"])["updated_page"]["path_params"] == [
        {"name": "id", "type": "text"}
    ]


@pytest.mark.django_db
def test_write_tools_with_only_builder_read_turned_on_are_refused(
    data_fixture, builder_ctx
):
    endpoint = _endpoint(data_fixture, builder_ctx, READ_TOOLS)
    builders = Builder.objects.count()
    pages = Page.objects.count()
    calls = _calls(builder_ctx)

    async def callback(client):
        return {
            name: await client.call_tool(name, arguments)
            for name, arguments in calls.items()
        }

    results = _session(endpoint, callback)

    assert set(results) == set(WRITE_TOOLS)
    for result in results.values():
        assert result.isError is True
    assert Builder.objects.count() == builders
    assert Page.objects.count() == pages


@pytest.mark.django_db
def test_create_builder_over_mcp_has_no_type_and_ignores_other_applications(
    data_fixture, builder_ctx
):
    endpoint = _endpoint(data_fixture, builder_ctx, WRITE_TOOLS)
    database = data_fixture.create_database_application(
        workspace=builder_ctx["workspace"]
    )

    async def callback(client):
        return (
            await client.call_tool("create_builder", {"name": "X", "type": "database"}),
            await client.call_tool(
                "update_builder", {"builder_id": database.id, "name": "Renamed"}
            ),
        )

    with_type, other_type = _session(endpoint, callback)

    assert with_type.isError is True
    assert "type" in with_type.content[0].text
    assert other_type.isError is True
    assert other_type.content[0].text == "Not found in this workspace."
