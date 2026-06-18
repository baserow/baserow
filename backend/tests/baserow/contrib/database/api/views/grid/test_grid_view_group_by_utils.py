import json
from types import SimpleNamespace

from django.test import override_settings

import pytest

from baserow.contrib.database.api.views.grid.utils import (
    GROUP_BY_DATA_DEFAULT_LIMIT,
    deserialize_group_by_parent_requests,
    deserialize_group_by_path,
    deserialize_group_by_path_object,
    empty_group_by_data_page,
    get_group_by_data_pages,
    get_group_by_data_parent_path,
    group_by_data_page_key,
    group_by_data_page_request_key,
    hashable_group_by_data_value,
    parse_non_negative_int,
    split_group_by_depth_page_by_parent,
)


def _field(db_column):
    return SimpleNamespace(db_column=db_column)


def _page_by_parent(pages, parent):
    for page in pages:
        if page["parent"] == parent:
            return page
    pytest.fail(f"Could not find page for parent {parent}")


def test_parse_non_negative_int_helper():
    assert parse_non_negative_int(None, 7) == 7
    assert parse_non_negative_int("", 7) == 7
    assert parse_non_negative_int("12", 7) == 12
    assert parse_non_negative_int("-1", 7) == 7
    assert parse_non_negative_int("invalid", 7) == 7


@pytest.mark.django_db
def test_deserialize_group_by_path_and_single_parent_request(data_fixture):
    table = data_fixture.create_database_table()
    color = data_fixture.create_text_field(table=table, name="Color")
    parent = {color.db_column: "Blue"}

    assert deserialize_group_by_path_object(parent, [color]) == parent
    assert deserialize_group_by_path_object(["not-a-path"], [color]) is None
    assert deserialize_group_by_path(json.dumps(parent), [color]) == parent
    assert deserialize_group_by_path(None, [color]) == {}

    assert deserialize_group_by_parent_requests(
        {"parent": json.dumps(parent)}, [color], default_offset=3, default_limit=5
    ) == [{"parent": parent, "offset": 3, "limit": 5}]


@pytest.mark.django_db
def test_deserialize_group_by_parent_requests_clamps_and_defaults(data_fixture):
    table = data_fixture.create_database_table()
    color = data_fixture.create_text_field(table=table, name="Color")
    parents = [
        {
            "parent": {color.db_column: "Blue"},
            "offset": "-1",
            "limit": "100",
        },
        {color.db_column: "Green"},
        {
            "path": {color.db_column: None},
            "offset": "2",
            "limit": "",
        },
    ]

    with override_settings(ROW_PAGE_SIZE_LIMIT=20):
        assert deserialize_group_by_parent_requests(
            {"parents": json.dumps(parents)},
            [color],
            default_offset=4,
            default_limit=9,
        ) == [
            {"parent": {color.db_column: "Blue"}, "offset": 4, "limit": 20},
            {"parent": {color.db_column: "Green"}, "offset": 4, "limit": 9},
            {"parent": {color.db_column: None}, "offset": 2, "limit": 9},
        ]


@pytest.mark.django_db
def test_deserialize_group_by_parent_requests_rejects_invalid_input(data_fixture):
    table = data_fixture.create_database_table()
    color = data_fixture.create_text_field(table=table, name="Color")
    size = data_fixture.create_number_field(table=table, name="Size")

    assert (
        deserialize_group_by_parent_requests(
            {"parent": "not-json"}, [color], default_offset=0, default_limit=10
        )
        is None
    )
    assert (
        deserialize_group_by_parent_requests(
            {"parents": json.dumps({"parent": {}})},
            [color],
            default_offset=0,
            default_limit=10,
        )
        is None
    )
    assert (
        deserialize_group_by_parent_requests(
            {"parents": json.dumps([{"parent": {size.db_column: "not-a-number"}}])},
            [size],
            default_offset=0,
            default_limit=10,
        )
        is None
    )


def test_empty_group_by_data_page_uses_default_shape():
    assert empty_group_by_data_page() == {
        "parent": {},
        "groups": [],
        "offset": 0,
        "limit": GROUP_BY_DATA_DEFAULT_LIMIT,
        "group_count": 0,
    }
    assert empty_group_by_data_page({"field_1": "Blue"}, offset=2, limit=3) == {
        "parent": {"field_1": "Blue"},
        "groups": [],
        "offset": 2,
        "limit": 3,
        "group_count": 0,
    }


def test_group_by_data_parent_path_uses_parent_metadata_or_path_depth():
    fields = [_field("field_1"), _field("field_2")]

    assert get_group_by_data_parent_path(
        {"_parent_path": {"field_1": "Blue"}}, fields
    ) == {"field_1": "Blue"}
    assert get_group_by_data_parent_path(
        {
            "path": {"field_1": "Blue", "field_2": "Large"},
            "depth": 1,
        },
        fields,
    ) == {"field_1": "Blue"}


def test_hashable_values_and_page_keys_support_nested_values():
    fields = [_field("field_1"), _field("field_2")]
    parent = {"field_1": {"b": [2, {"a": 1}], "a": "x"}}

    assert hashable_group_by_data_value(parent["field_1"]) == (
        ("a", "x"),
        ("b", (2, (("a", 1),))),
    )
    assert group_by_data_page_key(parent, fields) == (
        (
            "field_1",
            (("a", "x"), ("b", (2, (("a", 1),)))),
        ),
    )
    assert group_by_data_page_request_key(parent, fields, offset=3, limit=4) == (
        (
            (
                "field_1",
                (("a", "x"), ("b", (2, (("a", 1),)))),
            ),
        ),
        3,
        4,
    )


def test_split_group_by_depth_page_by_parent_groups_siblings():
    fields = [_field("field_1"), _field("field_2")]
    blue_parent = {"field_1": "Blue"}
    green_parent = {"field_1": "Green"}
    groups = [
        {
            "path": {"field_1": "Blue", "field_2": "Large"},
            "depth": 1,
            "sibling_index": 2,
            "_parent_path": blue_parent,
            "_parent_group_count": 4,
        },
        {
            "path": {"field_1": "Blue", "field_2": "Medium"},
            "depth": 1,
            "sibling_index": 3,
            "_parent_path": blue_parent,
            "_parent_group_count": 4,
        },
        {
            "path": {"field_1": "Green", "field_2": "Small"},
            "depth": 1,
            "sibling_index": 0,
            "_parent_path": green_parent,
            "_parent_group_count": 1,
        },
    ]

    pages = split_group_by_depth_page_by_parent({"groups": groups}, fields)

    blue_page = _page_by_parent(pages, blue_parent)
    assert blue_page["groups"] == groups[:2]
    assert blue_page["offset"] == 2
    assert blue_page["limit"] == 2
    assert blue_page["group_count"] == 4

    green_page = _page_by_parent(pages, green_parent)
    assert green_page["groups"] == [groups[2]]
    assert green_page["offset"] == 0
    assert green_page["limit"] == 1
    assert green_page["group_count"] == 1


def test_split_group_by_depth_page_by_parent_returns_empty_page_when_no_groups():
    assert split_group_by_depth_page_by_parent(
        {"groups": [], "offset": 6, "limit": 7}, [_field("field_1")]
    ) == [empty_group_by_data_page(offset=6, limit=7)]


def test_get_group_by_data_pages_deduplicates_and_loads_descendants():
    fields = [_field("field_1"), _field("field_2")]
    handler = _FakeGroupByDataHandler()

    pages, truncated = get_group_by_data_pages(
        handler,
        "base_queryset",
        ["view_group_by"],
        fields,
        [
            {"parent": {}, "offset": 0, "limit": 40},
            {"parent": {}, "offset": 0, "limit": 40},
        ],
        include_descendants=True,
        descendant_limit=5,
        total_group_limit=10,
    )

    assert truncated is False
    assert [page["parent"] for page in pages] == [{}, {"field_1": "Blue"}]
    assert handler.calls == [
        {
            "base_queryset": "base_queryset",
            "view_group_bys": ["view_group_by"],
            "parent_path": {},
            "offset": 0,
            "limit": 40,
            "parent_row_offset": None,
        },
        {
            "base_queryset": "base_queryset",
            "view_group_bys": ["view_group_by"],
            "parent_path": {"field_1": "Blue"},
            "offset": 0,
            "limit": 5,
            "parent_row_offset": 10,
        },
    ]


def test_get_group_by_data_pages_truncates_total_group_count():
    fields = [_field("field_1"), _field("field_2")]
    handler = _FakeGroupByDataHandler()

    pages, truncated = get_group_by_data_pages(
        handler,
        None,
        [],
        fields,
        [{"parent": {}, "offset": 0, "limit": 40}],
        include_descendants=True,
        descendant_limit=5,
        total_group_limit=1,
    )

    assert truncated is True
    assert pages == [
        {
            "parent": {},
            "groups": [
                {
                    "path": {"field_1": "Blue"},
                    "children_count": 1,
                    "row_offset": 10,
                }
            ],
            "offset": 0,
            "limit": 40,
            "group_count": 2,
        }
    ]
    assert len(handler.calls) == 1


class _FakeGroupByDataHandler:
    def __init__(self):
        self.calls = []

    def get_group_by_data(
        self,
        base_queryset,
        view_group_bys,
        parent_path,
        offset,
        limit,
        parent_row_offset=None,
    ):
        self.calls.append(
            {
                "base_queryset": base_queryset,
                "view_group_bys": view_group_bys,
                "parent_path": parent_path,
                "offset": offset,
                "limit": limit,
                "parent_row_offset": parent_row_offset,
            }
        )

        if parent_path == {}:
            return {
                "groups": [
                    {
                        "path": {"field_1": "Blue"},
                        "children_count": 1,
                        "row_offset": 10,
                    },
                    {
                        "path": {"field_1": "Green"},
                        "children_count": 0,
                        "row_offset": 20,
                    },
                ],
                "offset": offset,
                "limit": limit,
                "group_count": 2,
            }

        return {
            "groups": [
                {
                    "path": {**parent_path, "field_2": "Large"},
                    "children_count": 0,
                    "row_offset": 11,
                }
            ],
            "offset": offset,
            "limit": limit,
            "group_count": 1,
        }
