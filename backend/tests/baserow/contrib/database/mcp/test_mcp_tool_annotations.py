import pytest
from asgiref.sync import async_to_sync

from baserow.core.mcp.registries import mcp_tool_registry

# name: (read_only, destructive)
EXPECTED = {
    "list_databases": (True, False),
    "list_tables": (True, False),
    "get_table_schema": (True, False),
    "list_table_rows": (True, False),
    "create_rows": (False, False),
    "update_rows": (False, True),
    "delete_rows": (False, True),
    # Disabled tools, annotated so they are ready when enabled.
    "create_database": (False, False),
    "create_table": (False, False),
    "create_fields": (False, False),
    "update_table": (False, True),
    "update_fields": (False, True),
    "delete_table": (False, True),
    "delete_fields": (False, True),
}


@pytest.mark.django_db
def test_enabled_tools_have_annotations(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
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


@pytest.mark.django_db
def test_all_registered_tools_are_annotated(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint()
    assert set(mcp_tool_registry.registry.keys()) == set(EXPECTED)
    for name, (read_only, destructive) in EXPECTED.items():
        tool = async_to_sync(mcp_tool_registry.get(name).list)(endpoint)[0]
        assert tool.annotations.title
        assert mcp_tool_registry.get(name).title == tool.annotations.title
        assert tool.annotations.readOnlyHint is read_only
        assert tool.annotations.destructiveHint is destructive
