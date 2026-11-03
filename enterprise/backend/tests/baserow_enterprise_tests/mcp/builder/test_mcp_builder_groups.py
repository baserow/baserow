from baserow.core.mcp.groups import (
    AREA_BUILDER,
    GROUP_BUILDER_EDIT,
    GROUP_BUILDER_READ,
    mcp_tool_group_registry,
)


def test_builder_read_group_is_in_the_read_only_preset():
    group = mcp_tool_group_registry.get(GROUP_BUILDER_READ)

    assert group.title == "Read application builders"
    assert group.area == AREA_BUILDER
    assert group.read_only_preset is True
    assert group.order == 110


def test_builder_edit_group_is_not_in_the_read_only_preset():
    group = mcp_tool_group_registry.get(GROUP_BUILDER_EDIT)

    assert group.title == "Edit application builders"
    assert group.area == AREA_BUILDER
    assert group.read_only_preset is False
    assert group.order == 120


def test_there_is_no_builder_delete_group():
    assert "builder_delete" not in [
        group.type for group in mcp_tool_group_registry.get_all()
    ]
