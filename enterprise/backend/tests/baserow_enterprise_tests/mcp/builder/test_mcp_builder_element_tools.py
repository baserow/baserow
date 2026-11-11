"""The tools that write elements, over MCP."""

import json

import pytest

from baserow.contrib.builder.elements.handler import ElementHandler
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


def _button_state(button):
    saved = Element.objects.get(id=button.id).specific
    order = [e.id for e in ElementHandler().get_elements(saved.page, use_cache=False)]
    return (saved.value, order, saved.style_padding_top)


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
        assert tools[name].annotations.destructiveHint is (
            name in ("update_element", "update_element_style", "move_elements")
        )
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
    data_fixture.create_builder_heading_element(page=builder_ctx["page"])
    count = Element.objects.count()
    button = builder_ctx["button"]
    before = _button_state(button)
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
    assert _button_state(button) == before


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


@pytest.mark.django_db
def test_a_negative_size_is_an_input_error_over_mcp(data_fixture, builder_ctx):
    endpoint = _endpoint(data_fixture, builder_ctx, WRITE_TOOLS)
    button = builder_ctx["button"]
    padding = button.style_padding_top

    async def callback(client):
        return await client.call_tool(
            "update_element_style",
            {"element_id": button.id, "style": {"padding": -5}},
        )

    result = _session(endpoint, callback)

    assert result.isError is True
    assert "-5" in result.content[0].text
    assert "Internal error" not in result.content[0].text
    assert Element.objects.get(id=button.id).style_padding_top == padding


# Each value is refused by the input model (test_type_bounds); over MCP the call
# is an input error that saves nothing.
@pytest.mark.django_db
@pytest.mark.parametrize(
    "tool, element",
    [
        ("create_display_elements", {"type": "heading", "value": "x", "level": 0}),
        ("setup_page", {"type": "input_text", "rows": 101}),
    ],
)
def test_a_value_the_rest_api_refuses_is_refused_on_create(
    data_fixture, builder_ctx, tool, element
):
    endpoint = _endpoint(data_fixture, builder_ctx, [tool])
    count = Element.objects.count()

    async def callback(client):
        return await client.call_tool(
            tool,
            {"page_id": builder_ctx["page"].id, "elements": [{"ref": "e", **element}]},
        )

    result = _session(endpoint, callback)

    assert result.isError is True
    assert "Invalid arguments" in result.content[0].text
    assert Element.objects.count() == count


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tool,count,limit",
    [
        ("create_display_elements", 51, "50"),
        ("create_layout_elements", 101, "100"),
    ],
)
def test_a_call_over_the_item_limits_saves_nothing(
    data_fixture, builder_ctx, tool, count, limit
):
    endpoint = _endpoint(data_fixture, builder_ctx, WRITE_TOOLS)
    page_id = builder_ctx["page"].id
    if tool == "create_display_elements":
        elements = [
            {"ref": f"h{i}", "type": "heading", "value": "Hi"} for i in range(count)
        ]
    else:
        items = [{"name": f"Link {i}", "page_id": page_id} for i in range(count)]
        elements = [{"ref": "menu", "type": "menu", "menu_items": items}]
    before = Element.objects.count()

    async def callback(client):
        return await client.call_tool(tool, {"page_id": page_id, "elements": elements})

    result = _session(endpoint, callback)

    assert result.isError is True
    assert f"at most {limit} items" in result.content[0].text
    assert Element.objects.count() == before


@pytest.mark.django_db
def test_update_element_over_mcp_deletes_nothing(data_fixture, builder_ctx):
    endpoint = _endpoint(data_fixture, builder_ctx, ["update_element"])

    async def callback(client):
        listed = await client.list_tools()
        result = await client.call_tool(
            "update_element",
            {
                "element_id": builder_ctx["button"].id,
                "element": {"remove_menu_items": ["x"]},
            },
        )
        return listed, result

    listed, result = _session(endpoint, callback)

    schema = json.dumps(listed.tools[0].inputSchema)
    assert "remove_menu_items" not in schema
    assert "remove_table_columns" not in schema
    assert result.isError is True


@pytest.mark.django_db
def test_delete_element_items_deletes_menu_items_over_mcp(data_fixture, builder_ctx):
    endpoint = _endpoint(
        data_fixture,
        builder_ctx,
        ["create_layout_elements", "list_elements", "delete_element_items"],
    )
    page = builder_ctx["page"]

    async def callback(client):
        created = _load(
            await client.call_tool(
                "create_layout_elements",
                {
                    "page_id": page.id,
                    "elements": [
                        {
                            "ref": "menu",
                            "type": "menu",
                            "menu_items": [
                                {"name": "Home", "page_id": page.id},
                                {"name": "Again", "page_id": page.id},
                            ],
                        }
                    ],
                },
            )
        )
        menu_id = created["ref_to_id_map"]["menu"]
        elements = _load(await client.call_tool("list_elements", {"page_id": page.id}))[
            "elements"
        ]
        menu = next(el for el in elements if el["id"] == menu_id)
        uid = next(i["uid"] for i in menu["menu_items"] if i["name"] == "Again")
        listed = await client.list_tools()
        deleted = await client.call_tool(
            "delete_element_items", {"element_id": menu_id, "menu_items": [uid]}
        )
        empty = await client.call_tool("delete_element_items", {"element_id": menu_id})
        return menu_id, listed, deleted, empty

    menu_id, listed, deleted, empty = _session(endpoint, callback)

    tool = next(t for t in listed.tools if t.name == "delete_element_items")
    assert tool.annotations.destructiveHint is True
    assert _load(deleted)["updated_element"]["id"] == menu_id
    menu = Element.objects.get(id=menu_id).specific
    assert [item.name for item in menu.menu_items.all()] == ["Home"]
    assert empty.isError is True
