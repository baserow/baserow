import pytest

from baserow.core.user_sources.utils import remap_user_source_roles


@pytest.mark.parametrize(
    "roles,existing_roles,mapping,expected",
    [
        (["__user_source_1"], ["__user_source_2"], {1: 2}, ["__user_source_2"]),
        # An explicit role matching a default role takes precedence over remapping.
        (
            ["__user_source_1"],
            ["__user_source_1", "__user_source_2"],
            {1: 2},
            ["__user_source_1"],
        ),
        # Mapping and filtering are separate: callers decide which roles to keep.
        (
            ["editor", "__user_source_1", "__user_source_9"],
            [],
            {1: 2},
            ["editor", "__user_source_2", "__user_source_9"],
        ),
        (["__user_source_1"], [], {}, ["__user_source_1"]),
        (["__user_source_custom"], [], {1: 2}, ["__user_source_custom"]),
        ([], ["__user_source_2"], {1: 2}, []),
    ],
)
def test_remap_user_source_roles(roles, existing_roles, mapping, expected):
    assert remap_user_source_roles(roles, existing_roles, mapping) == expected
