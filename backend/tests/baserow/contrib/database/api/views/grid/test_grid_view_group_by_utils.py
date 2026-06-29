import json
from types import SimpleNamespace

from django.test import RequestFactory, override_settings

import pytest

from baserow.contrib.database.api.views.grid.utils import (
    GROUP_BY_DATA_DEFAULT_LIMIT,
    GROUP_BY_DATA_DESCENDANT_MAX_GROUPS,
    build_group_by_data_response,
    deserialize_group_by_parent_requests,
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


def _group(path, children_count, row_offset, row_count):
    return {
        "path": path,
        "children_count": children_count,
        "row_offset": row_offset,
        "row_count": row_count,
    }


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
def test_deserialize_group_by_path_object_and_default_parent_request(data_fixture):
    table = data_fixture.create_database_table()
    color = data_fixture.create_text_field(table=table, name="Color")
    parent = {color.db_column: "Blue"}

    assert deserialize_group_by_path_object(parent, [color]) == parent
    assert deserialize_group_by_path_object(["not-a-path"], [color]) is None

    assert deserialize_group_by_parent_requests(
        {}, [color], default_offset=3, default_limit=5
    ) == [{"parent": {}, "offset": 3, "limit": 5}]


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
            {"parents": "not-json"}, [color], default_offset=0, default_limit=10
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


def _three_level_tree():
    return {
        (): [
            _group({"field_1": "A"}, children_count=1, row_offset=0, row_count=2),
            _group({"field_1": "B"}, children_count=1, row_offset=2, row_count=2),
        ],
        (("field_1", "A"),): [
            _group(
                {"field_1": "A", "field_2": "A1"},
                children_count=1,
                row_offset=0,
                row_count=2,
            ),
        ],
        (("field_1", "B"),): [
            _group(
                {"field_1": "B", "field_2": "B1"},
                children_count=1,
                row_offset=0,
                row_count=2,
            ),
        ],
        (("field_1", "A"), ("field_2", "A1")): [
            _group(
                {"field_1": "A", "field_2": "A1", "field_3": "A1a"},
                children_count=0,
                row_offset=0,
                row_count=2,
            ),
        ],
        (("field_1", "B"), ("field_2", "B1")): [
            _group(
                {"field_1": "B", "field_2": "B1", "field_3": "B1a"},
                children_count=0,
                row_offset=0,
                row_count=2,
            ),
        ],
    }


def test_get_group_by_data_pages_batches_each_level_in_one_query():
    fields = [_field("field_1"), _field("field_2"), _field("field_3")]
    handler = _LevelGroupByDataHandler(_three_level_tree())

    pages, truncated = get_group_by_data_pages(
        handler,
        "base_queryset",
        ["view_group_by"],
        fields,
        # A duplicated root request must be de-duplicated into one query.
        [
            {"parent": {}, "offset": 0, "limit": 40},
            {"parent": {}, "offset": 0, "limit": 40},
        ],
        include_descendants=True,
        descendant_limit=40,
        row_budget=100,
    )

    assert truncated is False
    # One batched query per level, each covering every parent at that level.
    assert [depth for depth, _ in handler.level_calls] == [0, 1, 2]
    assert handler.level_calls[1][1] == [{"field_1": "A"}, {"field_1": "B"}]
    # Breadth-first by level: every parent of a level before the next level.
    assert [page["parent"] for page in pages] == [
        {},
        {"field_1": "A"},
        {"field_1": "B"},
        {"field_1": "A", "field_2": "A1"},
        {"field_1": "B", "field_2": "B1"},
    ]


def test_get_group_by_data_pages_window_prunes_offscreen_branches():
    fields = [_field("field_1"), _field("field_2"), _field("field_3")]
    handler = _LevelGroupByDataHandler(_three_level_tree())

    pages, truncated = get_group_by_data_pages(
        handler,
        "base_queryset",
        ["view_group_by"],
        fields,
        [{"parent": {}, "offset": 0, "limit": 40}],
        include_descendants=True,
        descendant_limit=40,
        # Window [0, 2): A starts at row 0 and is descended; B starts at row 2 and is
        # pruned (rendered as a placeholder, lazy-loaded on scroll).
        row_budget=2,
    )

    assert truncated is True
    assert [page["parent"] for page in pages] == [
        {},
        {"field_1": "A"},
        {"field_1": "A", "field_2": "A1"},
    ]
    # B is never expanded, so no level only fetches B's subtree.
    assert all(parents != [{"field_1": "B"}] for _, parents in handler.level_calls)


def test_get_group_by_data_pages_window_anchors_on_scrolled_slice():
    fields = [_field("field_1"), _field("field_2"), _field("field_3")]
    handler = _LevelGroupByDataHandler(_three_level_tree())

    pages, truncated = get_group_by_data_pages(
        handler,
        "base_queryset",
        ["view_group_by"],
        fields,
        # A root slice scrolled to sibling 1 (B, at row 2). The window must anchor on the
        # fetched slice, not the tree top, so B's subtree expands in this one descent
        # instead of being pruned because its rows fall past a top-anchored window.
        [{"parent": {}, "offset": 1, "limit": 40}],
        include_descendants=True,
        descendant_limit=40,
        row_budget=2,
    )

    assert truncated is False
    assert [page["parent"] for page in pages] == [
        {},
        {"field_1": "B"},
        {"field_1": "B", "field_2": "B1"},
    ]


class _LevelGroupByDataHandler:
    """
    Drives the batched per-level descent from a nested tree keyed by sorted path items.

    Each tree entry lists a parent's children with a parent-relative ``row_offset``; the
    descent makes them absolute. ``level_calls`` records ``(depth, [parent paths])`` for
    every batched query so tests can assert one query per level.
    """

    def __init__(self, tree, offsets=None):
        self._tree = tree
        self._offsets = offsets or {}
        self.level_calls = []

    def get_group_by_path_row_offset(self, base_queryset, view_group_bys, path):
        return self._offsets.get(tuple(sorted(path.items())), 0)

    def get_group_by_data_for_parents(
        self,
        base_queryset,
        view_group_bys,
        parents,
        depth,
        offset=0,
        per_parent_limit=40,
    ):
        self.level_calls.append((depth, [dict(parent) for parent in parents]))
        groups = []
        for parent in parents:
            children = self._tree.get(tuple(sorted(parent.items())), [])
            for index, child in enumerate(children[offset : offset + per_parent_limit]):
                group = {
                    "path": child["path"],
                    "depth": depth,
                    "row_count": child["row_count"],
                    "sibling_index": offset + index,
                    "row_offset": child["row_offset"],
                    "_parent_path": dict(parent),
                    "_parent_group_count": len(children),
                }
                if "children_count" in child:
                    group["children_count"] = child["children_count"]
                groups.append(group)
        return groups


def _captured_descendant_row_budget(monkeypatch, query):
    captured = {}

    def fake_get_group_by_data_pages(*args, **kwargs):
        captured["row_budget"] = kwargs["row_budget"]
        return [], False

    monkeypatch.setattr(
        "baserow.contrib.database.api.views.grid.utils.get_group_by_data_pages",
        fake_get_group_by_data_pages,
    )
    monkeypatch.setattr(
        "baserow.contrib.database.api.views.grid.utils.serialize_group_by_data_pages",
        lambda *args, **kwargs: {},
    )
    fields = [_field("field_1"), _field("field_2"), _field("field_3")]
    request = RequestFactory().get("/", query)
    build_group_by_data_response(
        None, request, "base_queryset", ["view_group_by"], fields
    )
    return captured["row_budget"]


def test_build_group_by_data_response_prefers_client_row_budget(monkeypatch):
    # The client budget is used as sent and does not depend on descendant_limit.
    row_budget = _captured_descendant_row_budget(
        monkeypatch,
        {
            "include_descendants": "true",
            "limit": "40",
            "descendant_limit": "5",
            "descendant_row_budget": "56",
        },
    )
    assert row_budget == 56


def test_build_group_by_data_response_defaults_to_limit_when_budget_absent(monkeypatch):
    # Without a client budget the descent window defaults to the page limit.
    row_budget = _captured_descendant_row_budget(
        monkeypatch,
        {"include_descendants": "true", "limit": "40"},
    )
    assert row_budget == 40


def test_build_group_by_data_response_clamps_client_row_budget_to_group_cap(
    monkeypatch,
):
    row_budget = _captured_descendant_row_budget(
        monkeypatch,
        {
            "include_descendants": "true",
            "limit": "40",
            "descendant_row_budget": str(GROUP_BY_DATA_DESCENDANT_MAX_GROUPS + 1000),
        },
    )
    assert row_budget == GROUP_BY_DATA_DESCENDANT_MAX_GROUPS
