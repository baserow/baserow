"""The tools that write elements, over MCP."""

import json

import pytest

from baserow.contrib.builder.elements.models import Element

from .test_mcp_builder_read_tools import READ_TOOLS, _endpoint, _session

WRITE_TOOLS = [
    "create_display_elements",
    "create_layout_elements",
    "create_form_elements",
    "create_collection_elements",
    "update_element",
    "update_element_style",
    "move_elements",
]


def _load(result):
    assert result.isError is False, result.content[0].text
    return json.loads(result.content[0].text)


def _calls(builder_ctx):
    page_id = builder_ctx["page"].id
    return {
        "create_display_elements": {
            "page_id": page_id,
            "elements": [
                {
                    "ref": "title",
                    "type": "heading",
                    "value": "$formula: the title of the page",
                }
            ],
        },
        "create_layout_elements": {
            "page_id": page_id,
            "elements": [{"ref": "top", "type": "header"}],
        },
        "create_form_elements": {
            "page_id": page_id,
            "elements": [{"ref": "form", "type": "form_container"}],
        },
        "create_collection_elements": {
            "page_id": page_id,
            "elements": [
                {
                    "ref": "list",
                    "type": "table",
                    "data_source": builder_ctx["data_source"].id,
                    "fields": [{"name": "Name"}],
                }
            ],
        },
        "update_element": {
            "element_id": builder_ctx["button"].id,
            "element": {"value": "Press"},
        },
        "update_element_style": {
            "element_id": builder_ctx["button"].id,
            "style": {"padding": 4},
        },
        "move_elements": {"moves": [{"element_id": builder_ctx["button"].id}]},
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
        assert tools[name].annotations.destructiveHint is False
    assert set(tools["create_display_elements"].inputSchema["properties"]) == {
        "page_id",
        "elements",
        "before_element_id",
    }
    assert set(tools["update_element"].inputSchema["properties"]) == {
        "element_id",
        "element",
    }
    assert set(tools["update_element_style"].inputSchema["properties"]) == {
        "element_id",
        "style",
    }
    assert set(tools["move_elements"].inputSchema["properties"]) == {"moves"}

    created = _load(results["create_display_elements"])
    assert created["formula_errors"][0]["field"] == "value"
    assert (
        created["formula_errors"][0]["element_id"]
        == (created["ref_to_id_map"]["title"])
    )
    layout = _load(results["create_layout_elements"])
    assert layout["empty_containers"][0]["ref"] == "top"
    assert "next_steps" not in layout
    assert _load(results["create_form_elements"])["created_elements"]
    assert _load(results["create_collection_elements"])["created_elements"]
    assert _load(results["update_element"])["updated_element"]["label"] == "'Press'"
    assert _load(results["update_element_style"])["updated_fields"]
    assert _load(results["move_elements"])["moved_elements"]


@pytest.mark.django_db
def test_write_tools_with_only_builder_read_turned_on_are_refused(
    data_fixture, builder_ctx
):
    endpoint = _endpoint(data_fixture, builder_ctx, READ_TOOLS)
    count = Element.objects.count()
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
    assert Element.objects.count() == count


@pytest.mark.django_db
def test_a_ref_from_an_earlier_call_fails_the_item_over_mcp(data_fixture, builder_ctx):
    endpoint = _endpoint(data_fixture, builder_ctx, WRITE_TOOLS)
    page_id = builder_ctx["page"].id

    async def callback(client):
        await client.call_tool(
            "create_layout_elements",
            {
                "page_id": page_id,
                "elements": [{"ref": "box", "type": "simple_container"}],
            },
        )
        return await client.call_tool(
            "create_display_elements",
            {
                "page_id": page_id,
                "elements": [
                    {
                        "ref": "h",
                        "type": "heading",
                        "value": "Hi",
                        "parent_element": "box",
                    }
                ],
            },
        )

    result = _load(_session(endpoint, callback))

    assert result["errors"] == [
        "h: Unknown ref 'box'. Refs only work inside one call; use the element ID."
    ]


@pytest.mark.django_db
def test_an_element_of_another_workspace_is_not_found_over_mcp(
    data_fixture, builder_ctx
):
    endpoint = _endpoint(data_fixture, builder_ctx, WRITE_TOOLS)
    other = data_fixture.create_builder_heading_element(
        page=data_fixture.create_builder_page(
            builder=data_fixture.create_builder_application(
                workspace=data_fixture.create_workspace(user=builder_ctx["user"])
            )
        )
    )

    async def callback(client):
        return await client.call_tool(
            "update_element", {"element_id": other.id, "element": {"value": "Stolen"}}
        )

    result = _session(endpoint, callback)

    assert result.isError is True
    assert "Not found in this workspace." in result.content[0].text
