import pytest
from asgiref.sync import async_to_sync

from baserow.core.mcp.registries import mcp_tool_registry

# name: (read_only, destructive)
EXPECTED = {
    "list_databases": (True, False),
    "list_applications": (True, False),
    "list_tables": (True, False),
    "get_table_schema": (True, False),
    "list_table_rows": (True, False),
    "create_rows": (False, False),
    "update_rows": (False, True),
    "delete_rows": (False, True),
    "list_views": (True, False),
    "create_tables": (False, False),
    "create_fields": (False, False),
    "update_fields": (False, True),
    "delete_fields": (False, True),
    "create_views": (False, False),
    "create_view_filters": (False, False),
    "list_workflows": (True, False),
    "list_nodes": (True, False),
    "create_workflows": (False, False),
    "publish_workflow": (False, True),
    "pause_workflow": (False, True),
    "add_nodes": (False, False),
    "update_nodes": (False, True),
    "delete_nodes": (False, True),
    "list_filterable_data_sources": (True, False),
    "list_service_filters": (True, False),
    "update_service_filters": (False, True),
    "search_workspace": (True, False),
    "list_row_comments": (True, False),
    "create_row_comments": (False, False),
    "set_view_sorts": (False, True),
    "set_field_visibility": (False, False),
    "add_row_colours": (False, False),
    "delete_views": (False, True),
    "delete_view_filters": (False, True),
    "delete_row_colours": (False, True),
    "list_audit_log": (True, False),
    "list_dashboards": (True, False),
    "list_widgets": (True, False),
    "get_widget_data": (True, False),
    "create_dashboard": (False, False),
    "update_dashboard": (False, True),
    "create_database": (False, False),
    "update_database": (False, True),
    "create_automation": (False, False),
    "update_automation": (False, True),
    "create_widgets": (False, False),
    "update_widgets": (False, True),
    "delete_widgets": (False, True),
    "list_builders": (True, False),
    "create_builder": (False, False),
    "update_builder": (False, True),
    "list_pages": (True, False),
    "create_pages": (False, False),
    "update_page": (False, True),
    "setup_page": (False, False),
    "setup_user_source": (False, False),
    "set_theme": (False, True),
    "list_data_sources": (True, False),
    "create_data_sources": (False, False),
    "update_data_source": (False, True),
    "list_elements": (True, False),
    "create_display_elements": (False, False),
    "create_layout_elements": (False, False),
    "create_form_elements": (False, False),
    "create_collection_elements": (False, False),
    "update_element": (False, True),
    "delete_element_items": (False, True),
    "update_element_style": (False, True),
    "move_elements": (False, True),
    "list_element_actions": (True, False),
    "create_element_actions": (False, False),
    "update_element_action": (False, True),
    # Disabled tools, annotated so they are ready when enabled.
    "update_table": (False, True),
    "delete_table": (False, True),
}

# Tools that can reach outside the workspace: a public view link, or workflow nodes
# that send email and Slack messages, call an AI model or expose a webhook.
OPEN_WORLD = {
    "create_views",
    "create_workflows",
    "add_nodes",
    "update_nodes",
    "publish_workflow",
}


@pytest.mark.django_db
def test_enabled_tools_have_annotations(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=list(EXPECTED))
    tools = {
        t.name: t for t in async_to_sync(mcp_tool_registry.list_all_tools)(endpoint)
    }
    for name, (read_only, destructive) in EXPECTED.items():
        if not mcp_tool_registry.get(name).enabled:
            continue
        annotations = tools[name].annotations
        assert annotations.title
        assert annotations.readOnlyHint is read_only
        assert annotations.destructiveHint is destructive
        assert annotations.openWorldHint is (name in OPEN_WORLD)


@pytest.mark.django_db
def test_all_registered_tools_are_annotated(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    assert set(mcp_tool_registry.registry) == set(EXPECTED)
    for name, (read_only, destructive) in EXPECTED.items():
        tool = async_to_sync(mcp_tool_registry.get(name).list)(endpoint)[0]
        assert tool.annotations.title
        assert mcp_tool_registry.get(name).title == tool.annotations.title
        assert tool.annotations.readOnlyHint is read_only
        assert tool.annotations.destructiveHint is destructive
        assert tool.annotations.openWorldHint is (name in OPEN_WORLD)
