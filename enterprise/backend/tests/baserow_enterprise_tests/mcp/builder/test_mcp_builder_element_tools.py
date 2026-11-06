"""The tools that write elements, over MCP."""

import json

import pytest

from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element, LinkElement

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
            name in ("update_element", "update_element_style")
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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "style",
    [
        {"border_radius": 32768},
        {"border_radius": -5},
        {"background_radius": 32768},
        {"background_radius": -5},
        {"background_color": "x" * 256},
        {"border_color": "x" * 256},
        {"border_color": {"left": "x" * 256}},
        {"padding": 2147483648},
        {"margin": {"top": 2147483648}},
        {"border_size": 2147483648},
    ],
)
def test_a_style_the_rest_api_refuses_is_an_input_error(
    data_fixture, builder_ctx, style
):
    endpoint = _endpoint(data_fixture, builder_ctx, ["update_element_style"])
    button = builder_ctx["button"]

    async def callback(client):
        return await client.call_tool(
            "update_element_style", {"element_id": button.id, "style": style}
        )

    result = _session(endpoint, callback)

    assert result.isError is True
    assert "Invalid arguments" in result.content[0].text
    saved = Element.objects.get(id=button.id)
    assert saved.style_border_radius == button.style_border_radius
    assert saved.style_background_radius == button.style_background_radius


@pytest.mark.django_db
def test_the_highest_style_values_are_stored(data_fixture, builder_ctx):
    endpoint = _endpoint(data_fixture, builder_ctx, ["update_element_style"])
    button = builder_ctx["button"]

    async def callback(client):
        return await client.call_tool(
            "update_element_style",
            {
                "element_id": button.id,
                "style": {
                    "border_radius": 32767,
                    "background_radius": 0,
                    "background_color": "x" * 255,
                    "border_color": "y" * 255,
                    "padding": 2147483647,
                },
            },
        )

    _load(_session(endpoint, callback))

    saved = Element.objects.get(id=button.id)
    assert saved.style_border_radius == 32767
    assert saved.style_background_radius == 0
    assert saved.style_background_color == "x" * 255
    assert saved.style_border_left_color == "y" * 255
    assert saved.style_padding_top == 2147483647


@pytest.mark.django_db
def test_children_keep_their_order_over_mcp(data_fixture, builder_ctx):
    endpoint = _endpoint(data_fixture, builder_ctx, [*READ_TOOLS, *WRITE_TOOLS])
    page_id = builder_ctx["page"].id

    async def callback(client):
        layout = _load(
            await client.call_tool(
                "create_layout_elements",
                {
                    "page_id": page_id,
                    "elements": [
                        {"ref": "box", "type": "simple_container"},
                        {"ref": "top", "type": "header"},
                    ],
                },
            )
        )["ref_to_id_map"]
        _load(
            await client.call_tool(
                "create_display_elements",
                {
                    "page_id": page_id,
                    "elements": [
                        {
                            "ref": ref,
                            "type": element_type,
                            "value": ref,
                            "parent_element": layout[parent],
                        }
                        for ref, element_type, parent in (
                            ("First", "heading", "box"),
                            ("Second", "heading", "box"),
                            ("One", "button", "top"),
                            ("Two", "button", "top"),
                        )
                    ],
                },
            )
        )
        return layout

    layout = _session(endpoint, callback)

    def children(element_id):
        container = Element.objects.get(id=element_id)
        container.page.reload_graph()
        return [
            child.specific.value["formula"]
            for child in container.page.get_graph().get_children(element_id)
        ]

    assert children(layout["box"]) == ["'First'", "'Second'"]
    assert children(layout["top"]) == ["'One'", "'Two'"]


@pytest.mark.django_db
def test_a_new_target_that_does_not_fit_a_link_is_refused_over_mcp(
    data_fixture, builder_ctx
):
    endpoint = _endpoint(data_fixture, builder_ctx, WRITE_TOOLS)
    builder = builder_ctx["builder"]
    start = data_fixture.create_builder_page(
        builder=builder,
        name="Product",
        path="/products/:id",
        path_params=[{"name": "id", "type": "text"}],
    )
    target = data_fixture.create_builder_page(
        builder=builder,
        name="Post",
        path="/posts/:slug",
        path_params=[{"name": "slug", "type": "text"}],
    )
    link = data_fixture.create_builder_link_element(
        page=builder_ctx["page"],
        navigation_type="page",
        navigate_to_page_id=start.id,
        page_parameters=[{"name": "id", "value": "'1'"}],
    )

    async def call(client):
        return await client.call_tool(
            "update_element",
            {"element_id": link.id, "element": {"navigate_to_page_id": target.id}},
        )

    result = _session(endpoint, call)

    assert result.isError
    assert "stays on the page" in result.content[0].text
    assert Element.objects.get(id=link.id).specific.navigate_to_page_id == start.id


@pytest.mark.django_db
def test_a_new_link_without_the_parameters_of_its_page_is_refused_over_mcp(
    data_fixture, builder_ctx
):
    endpoint = _endpoint(data_fixture, builder_ctx, WRITE_TOOLS)
    target = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        name="Product",
        path="/products/:id",
        path_params=[{"name": "id", "type": "text"}],
    )

    async def call(client):
        return await client.call_tool(
            "create_display_elements",
            {
                "page_id": builder_ctx["page"].id,
                "elements": [
                    {
                        "ref": "go",
                        "type": "link",
                        "value": "Go",
                        "navigate_to_page_id": target.id,
                    }
                ],
            },
        )

    result = _session(endpoint, call)

    assert "missing: id" in result.content[0].text
    assert not LinkElement.objects.filter(page=builder_ctx["page"]).exists()


BAD_CREATES = [
    ("create_display_elements", {"type": "heading", "value": "x", "level": 0}),
    ("create_display_elements", {"type": "heading", "value": "x", "level": 99}),
    ("create_display_elements", {"type": "text", "value": "x", "format": "html"}),
    ("create_layout_elements", {"type": "column", "column_amount": 500}),
    ("create_layout_elements", {"type": "column", "column_amount": 0}),
    ("setup_page", {"type": "column", "column_gap": -1}),
    ("setup_page", {"type": "column", "column_gap": 2001}),
    ("setup_page", {"type": "input_text", "rows": 0}),
    ("setup_page", {"type": "input_text", "rows": 101}),
    ("setup_page", {"type": "repeat", "items_per_page": -1}),
    ("setup_page", {"type": "repeat", "items_per_page": 0}),
]


@pytest.mark.django_db
@pytest.mark.parametrize("tool, element", BAD_CREATES)
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
    "changes",
    [
        {"level": 7},
        {"format": "html"},
        {"column_amount": 7},
        {"column_gap": -1},
        {"rows": 101},
        {"items_per_page": -1},
        {"items_per_page": 0},
    ],
)
def test_a_value_the_rest_api_refuses_is_refused_on_update(
    data_fixture, builder_ctx, changes
):
    endpoint = _endpoint(data_fixture, builder_ctx, ["update_element"])

    async def callback(client):
        return await client.call_tool(
            "update_element",
            {"element_id": builder_ctx["button"].id, "element": changes},
        )

    result = _session(endpoint, callback)

    assert result.isError is True
    assert "Invalid arguments" in result.content[0].text


@pytest.mark.django_db
def test_the_highest_values_the_rest_api_takes_are_stored(data_fixture, builder_ctx):
    endpoint = _endpoint(data_fixture, builder_ctx, ["setup_page"])

    async def callback(client):
        return await client.call_tool(
            "setup_page",
            {
                "page_id": builder_ctx["page"].id,
                "elements": [
                    {"ref": "h", "type": "heading", "value": "x", "level": 6},
                    {
                        "ref": "c",
                        "type": "column",
                        "column_amount": 6,
                        "column_gap": 2000,
                    },
                    {"ref": "i", "type": "input_text", "rows": 100},
                ],
            },
        )

    result = _load(_session(endpoint, callback))

    assert not result.get("errors")
    assert len(result["created_elements"]) == 3


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
