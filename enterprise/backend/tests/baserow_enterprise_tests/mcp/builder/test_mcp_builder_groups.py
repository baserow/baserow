import pytest

from baserow.core.mcp.groups import (
    AREA_BUILDER,
    GROUP_BUILDER_DELETE,
    GROUP_BUILDER_EDIT,
    GROUP_BUILDER_READ,
    mcp_tool_group_registry,
)
from baserow.core.mcp.registries import mcp_tool_registry


@pytest.mark.parametrize(
    "group_type,read_only_preset",
    [
        (GROUP_BUILDER_READ, True),
        (GROUP_BUILDER_EDIT, False),
        (GROUP_BUILDER_DELETE, False),
    ],
)
def test_only_the_builder_read_group_is_in_the_read_only_preset(
    group_type, read_only_preset
):
    group = mcp_tool_group_registry.get(group_type)

    assert group.area == AREA_BUILDER
    assert group.read_only_preset is read_only_preset


def test_the_builder_delete_group_holds_only_the_tool_that_deletes_items():
    assert [
        tool.type
        for tool in mcp_tool_registry.get_all()
        if tool.group == GROUP_BUILDER_DELETE
    ] == ["delete_element_items"]
