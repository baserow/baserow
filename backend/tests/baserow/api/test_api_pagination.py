from unittest.mock import patch

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from baserow.api.pagination import (
    ApproximateCountPaginator,
    PageNumberPaginationWithApproximateCount,
)


@pytest.fixture
def estimate():
    with patch("baserow.api.pagination.get_approximate_row_count") as mock:
        yield mock


def test_approximate_count_keeps_pages_reachable_when_underestimated(estimate):
    estimate.return_value = 0
    rows = list(range(201))

    pages = [ApproximateCountPaginator(rows, 100).page(n) for n in (1, 2, 3)]

    assert [page.paginator.count for page in pages] == [101, 201, 201]
    assert [page.has_next() for page in pages] == [True, True, False]
    assert list(pages[2]) == [200]


def test_approximate_count_is_exact_on_a_partial_page(estimate):
    estimate.return_value = 10_000

    page = ApproximateCountPaginator([1, 2], 100).page(1)

    assert page.paginator.count == 2
    assert not page.has_next()
    estimate.assert_not_called()


def test_approximate_count_caps_the_estimate_on_an_empty_page_past_the_end(estimate):
    estimate.return_value = 42

    page = ApproximateCountPaginator([1], 100).page(2)

    assert page.paginator.count == 42
    assert not page.has_next()
    assert list(page) == []


def test_approximate_count_pagination_uses_the_corrected_count(estimate):
    estimate.return_value = 0
    pagination = PageNumberPaginationWithApproximateCount()
    request = Request(APIRequestFactory().get("/", {"page": "last"}))

    results = pagination.paginate_queryset(list(range(101)), request)

    assert results == list(range(100))
    assert pagination.page.paginator.count == 101
    assert pagination.get_next_link() is not None
