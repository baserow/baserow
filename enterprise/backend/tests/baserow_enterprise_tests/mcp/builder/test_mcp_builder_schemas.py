"""What the builder tools accept over MCP: no Kuma-only parameters."""

from baserow.core.mcp.groups import GROUP_BUILDER_EDIT, GROUP_BUILDER_READ
from baserow.core.mcp.registries import mcp_tool_registry

KUMA_ONLY_PARAMETERS = {
    "known_refs",
    "known_data_source_refs",
    "defer_required_formulas",
    "options",
}

BUILDER_TOOLS = {
    "list_builders",
    "list_pages",
    "list_data_sources",
    "list_elements",
    "list_actions",
    "create_builder",
    "update_builder",
    "create_pages",
    "update_page",
    "create_data_sources",
    "update_data_source",
    "create_display_elements",
    "create_layout_elements",
    "create_form_elements",
    "create_collection_elements",
    "update_element",
    "update_element_style",
    "move_elements",
    "create_actions",
    "add_action_field_mapping",
    "update_action",
    "setup_page",
    "setup_user_source",
    "set_theme",
}


def _keys(node):
    """Every key used anywhere in a JSON schema."""

    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from _keys(value)


def _builder_tools():
    return [
        tool
        for tool in mcp_tool_registry.get_all()
        if tool.group in (GROUP_BUILDER_READ, GROUP_BUILDER_EDIT)
    ]


def test_builder_tools_are_registered():
    names = {tool.name for tool in _builder_tools()}

    assert names == BUILDER_TOOLS


def test_no_builder_tool_offers_a_kuma_only_parameter():
    for tool in _builder_tools():
        schema = tool.input_schema.model_json_schema()
        leaked = KUMA_ONLY_PARAMETERS & set(_keys(schema))
        assert not leaked, f"{tool.name} offers {sorted(leaked)}"
