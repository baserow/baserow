import pytest

from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.utils import ServiceAdhocRefinements


class MinimalDispatchContext(DispatchContext):
    """A context that implements nothing but what the base class requires."""


def test_the_default_range_is_unpaginated():
    assert MinimalDispatchContext().range(None) == (0, None)


def test_nothing_is_public_by_default():
    dispatch_context = MinimalDispatchContext()

    assert dispatch_context.is_publicly_searchable is False
    assert dispatch_context.is_publicly_filterable is False
    assert dispatch_context.is_publicly_sortable is False
    assert dispatch_context.search_query() is None
    assert dispatch_context.searchable_fields() == []
    assert dispatch_context.filters() is None
    assert dispatch_context.sortings() is None
    assert dispatch_context.public_allowed_properties is None


def test_validating_refinements_is_not_silently_allowed():
    # A context that opts into adhoc refinements has to say which fields they
    # may point at, rather than inheriting a no-op that accepts every field.
    with pytest.raises(NotImplementedError):
        MinimalDispatchContext().validate_filter_search_sort_fields(
            ["field_1"], ServiceAdhocRefinements.FILTER
        )
