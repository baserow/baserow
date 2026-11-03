import pytest

from baserow.core.mcp.groups import (
    AREA_BUILDER,
    GROUP_BUILDER_EDIT,
    GROUP_BUILDER_READ,
    mcp_tool_group_registry,
)


@pytest.mark.parametrize(
    "group_type,read_only_preset",
    [(GROUP_BUILDER_READ, True), (GROUP_BUILDER_EDIT, False)],
)
def test_only_the_builder_read_group_is_in_the_read_only_preset(
    group_type, read_only_preset
):
    group = mcp_tool_group_registry.get(group_type)

    assert group.area == AREA_BUILDER
    assert group.read_only_preset is read_only_preset


def test_there_is_no_builder_delete_group():
    assert "builder_delete" not in [
        group.type for group in mcp_tool_group_registry.get_all()
    ]
