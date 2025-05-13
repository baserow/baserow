from unittest.mock import MagicMock

from baserow.contrib.automation.data_sources.dispatch_context import (
    AutomationNodeDispatchContext,
)
from baserow.core.services.utils import ServiceAdhocRefinements


def test_from_context():
    context = AutomationNodeDispatchContext(0, 0)

    new_context = AutomationNodeDispatchContext.from_context(
        context, count=10, offset=20
    )

    assert new_context.count == 10
    assert new_context.offset == 20


def test_is_publicly_searchable():
    assert AutomationNodeDispatchContext(0, 0).is_publicly_searchable is False


def test_is_publicly_filterable():
    assert AutomationNodeDispatchContext(0, 0).is_publicly_filterable is False


def test_public_allowed_properties():
    assert AutomationNodeDispatchContext(0, 0).public_allowed_properties is None


def test_is_publicly_sortable():
    assert AutomationNodeDispatchContext(0, 0).is_publicly_sortable is False


def test_range():
    service = MagicMock()
    assert AutomationNodeDispatchContext(0, 0).range(service) == []


def test_search_query():
    assert AutomationNodeDispatchContext(0, 0).search_query() is None


def test_searchable_fields():
    assert AutomationNodeDispatchContext(0, 0).searchable_fields() == []


def test_filters():
    assert AutomationNodeDispatchContext(0, 0).filters() is None


def test_sortings():
    assert AutomationNodeDispatchContext(0, 0).sortings() is None


def test_validate_filter_search_sort_fields():
    assert (
        AutomationNodeDispatchContext(0, 0).validate_filter_search_sort_fields(
            [], ServiceAdhocRefinements.FILTER
        )
        is None
    )
