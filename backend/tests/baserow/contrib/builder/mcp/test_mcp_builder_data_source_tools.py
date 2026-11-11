"""The tools that write data sources, over MCP."""

import json

import pytest

from baserow.contrib.builder.data_sources.models import DataSource

from .test_mcp_builder_read_tools import READ_TOOLS, _endpoint, _session

WRITE_TOOLS = ["create_data_sources", "update_data_source"]


def _load(result):
    assert result.isError is False, result.content[0].text
    return json.loads(result.content[0].text)


def _table_id(builder_ctx):
    return builder_ctx["data_source"].service.specific.table_id


def _calls(builder_ctx):
    return {
        "create_data_sources": {
            "page_id": builder_ctx["page"].id,
            "data_sources": [
                {
                    "ref": "ds",
                    "name": "Search",
                    "type": "list_rows",
                    "table_id": _table_id(builder_ctx),
                    "search_query": "$formula: the text of the search box",
                }
            ],
        },
        "update_data_source": {
            "data_source_id": builder_ctx["data_source"].id,
            "data_source": {"name": "Renamed"},
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
        assert tools[name].annotations.destructiveHint is (name == "update_data_source")
    assert set(tools["update_data_source"].inputSchema["properties"]) == {
        "data_source_id",
        "data_source",
    }

    created = _load(results["create_data_sources"])
    assert created["formula_errors"][0]["field"] == "search_query"
    assert (
        created["formula_errors"][0]["data_source_id"]
        == (created["ref_to_id_map"]["ds"])
    )
    updated = _load(results["update_data_source"])
    assert updated["updated_data_source"]["name"] == "Renamed"


@pytest.mark.django_db
def test_write_tools_with_only_builder_read_turned_on_are_refused(
    data_fixture, builder_ctx
):
    endpoint = _endpoint(data_fixture, builder_ctx, READ_TOOLS)
    sources = DataSource.objects.count()
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
    assert DataSource.objects.count() == sources
