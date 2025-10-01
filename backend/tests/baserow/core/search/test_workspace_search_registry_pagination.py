from unittest.mock import Mock

import pytest

from baserow.core.search.data_types import SearchContext, SearchResult
from baserow.core.search.registries import WorkspaceSearchRegistry


class MockSearchType:
    def __init__(self, type_name, priority, total_count):
        self.type = type_name
        self.priority = priority
        self.total_count = total_count
        self.call_count = 0
        self.last_context = None

    def get_union_values_queryset(self, user, workspace, context):
        self.call_count += 1
        self.last_context = context

        mock_data = []
        for i in range(self.total_count):
            mock_data.append(
                {
                    "search_type": self.type,
                    "object_id": f"{self.type}_{i}",
                    "sort_key": i,
                    "rank": None,
                    "priority": self.priority,
                    "title": f"{self.type} Item {i}",
                    "subtitle": self.type,
                    "payload": {},
                }
            )

        mock_qs = Mock()
        mock_qs.__iter__ = lambda self: iter(mock_data)
        mock_qs.__getitem__ = lambda self, key: mock_data[key]
        mock_qs.order_by = lambda *args: mock_qs
        mock_qs.union = lambda other, all=True: self._create_union_mock(
            mock_data, other
        )

        return mock_qs

    def _create_union_mock(self, self_data, other_qs):
        other_data = list(other_qs) if hasattr(other_qs, "__iter__") else []
        combined_data = self_data + other_data

        mock_qs = Mock()
        mock_qs.__iter__ = lambda self: iter(combined_data)
        mock_qs.__getitem__ = lambda self, key: combined_data[key]
        mock_qs.order_by = lambda *args: mock_qs
        mock_qs.union = lambda other, all=True: self._create_union_mock(
            combined_data, other
        )

        return mock_qs

    def postprocess(self, rows):
        return [
            SearchResult(
                type=row["search_type"],
                id=row["object_id"],
                title=row["title"],
                subtitle=row["subtitle"],
                created_on=None,
                updated_on=None,
                metadata=row["payload"],
            )
            for row in rows
        ]


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_all_types_pagination_within_single_type():
    registry = WorkspaceSearchRegistry()

    type1 = MockSearchType("type1", priority=1, total_count=50)

    registry.registry = {"type1": type1}

    context = SearchContext(query="test", limit=10, offset=5)

    user = Mock()
    workspace = Mock()

    results = registry.search_all_types(user, workspace, context)

    assert type1.call_count == 1
    assert type1.last_context.offset == 5
    assert type1.last_context.limit == 10

    assert len(results) == 10
    assert all(result.type == "type1" for result in results)
    assert results[0].id == "type1_5"
    assert results[9].id == "type1_14"


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_all_types_pagination_skip_entire_type():
    registry = WorkspaceSearchRegistry()

    type1 = MockSearchType("type1", priority=1, total_count=5)
    type2 = MockSearchType("type2", priority=2, total_count=3)
    type3 = MockSearchType("type3", priority=3, total_count=10)

    registry.registry = {"type1": type1, "type2": type2, "type3": type3}

    # Should skip type1 (5) + type2 (3) = 8, then start at offset 2 in type3
    context = SearchContext(query="test", limit=5, offset=10)

    user = Mock()
    workspace = Mock()

    results = registry.search_all_types(user, workspace, context)

    assert type1.call_count == 1
    assert type1.last_context.offset == 10  # Original offset

    assert type2.call_count == 1
    assert type2.last_context.offset == 10  # Original offset

    assert type3.call_count == 1
    assert type3.last_context.offset == 10  # Original offset

    assert len(results) == 5
    assert all(result.type == "type3" for result in results)
    assert results[0].id == "type3_2"
    assert results[4].id == "type3_6"


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_all_types_pagination_no_results():
    registry = WorkspaceSearchRegistry()

    type1 = MockSearchType("type1", priority=1, total_count=3)
    type2 = MockSearchType("type2", priority=2, total_count=2)

    registry.registry = {"type1": type1, "type2": type2}

    context = SearchContext(query="test", limit=5, offset=10)

    user = Mock()
    workspace = Mock()

    results = registry.search_all_types(user, workspace, context)

    assert type1.call_count == 1
    assert type1.last_context.offset == 10
    assert type2.call_count == 1
    assert type2.last_context.offset == 10

    assert len(results) == 0


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_search_all_types_pagination_limit_reached():
    registry = WorkspaceSearchRegistry()

    type1 = MockSearchType("type1", priority=1, total_count=5)
    type2 = MockSearchType("type2", priority=2, total_count=10)
    type3 = MockSearchType("type3", priority=3, total_count=10)

    registry.registry = {"type1": type1, "type2": type2, "type3": type3}

    context = SearchContext(query="test", limit=8, offset=0)

    user = Mock()
    workspace = Mock()

    results = registry.search_all_types(user, workspace, context)

    assert type1.call_count == 1
    assert type1.last_context.offset == 0
    assert type1.last_context.limit == 8

    assert type2.call_count == 1
    assert type2.last_context.offset == 0
    assert type2.last_context.limit == 8

    assert type3.call_count == 1
    assert type3.last_context.offset == 0
    assert type3.last_context.limit == 8

    assert len(results) == 8
    assert len([r for r in results if r.type == "type1"]) == 5
    assert len([r for r in results if r.type == "type2"]) == 3
