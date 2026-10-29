import re
from datetime import timedelta
from functools import cached_property
from typing import Optional, Protocol

from django.core.paginator import Paginator as DjangoPaginator

from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework.pagination import (
    LimitOffsetPagination as RestFrameworkLimitOffsetPagination,
)
from rest_framework.pagination import (
    PageNumberPagination as RestFrameworkPageNumberPagination,
)
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST

from baserow.core.db import get_approximate_row_count
from baserow.core.pagination import (
    KEYSET_CURSOR_EPOCH,
    KeysetCursor,
    RankedKeysetCursor,
)

_KEYSET_CURSOR_RE = re.compile(r"(\d+)_(\d+)")
_RANKED_KEYSET_CURSOR_RE = re.compile(r"(\d+)_(.*)")


def encode_keyset_cursor(cursor: Optional[KeysetCursor]) -> Optional[str]:
    """
    The moment is counted in whole microseconds, the precision it is stored with,
    so the next page continues from exactly the same position.

    :param cursor: The cursor of the next page.
    :return: The opaque string for the API, `None` when there is no next page.
    """

    if cursor is None:
        return None
    microseconds = (cursor.value - KEYSET_CURSOR_EPOCH) // timedelta(microseconds=1)
    return f"{microseconds}_{cursor.id}"


class KeysetCursorField(serializers.CharField):
    """
    Accepts what `encode_keyset_cursor` produced and returns the `KeysetCursor`.
    """

    def to_internal_value(self, data) -> KeysetCursor:
        match = _KEYSET_CURSOR_RE.fullmatch(super().to_internal_value(data))
        if match is None:
            raise serializers.ValidationError("Invalid cursor.")
        microseconds, id = match.groups()
        try:
            value = KEYSET_CURSOR_EPOCH + timedelta(microseconds=int(microseconds))
        except OverflowError:
            raise serializers.ValidationError("Invalid cursor.")
        return KeysetCursor(value=value, id=int(id))


def encode_ranked_keyset_cursor(
    cursor: Optional[RankedKeysetCursor],
) -> Optional[str]:
    """
    :param cursor: The cursor of the next page.
    :return: The opaque string for the API, the rank before what
        `encode_keyset_cursor` produces, `None` when there is no next page.
    """

    if cursor is None:
        return None
    position = encode_keyset_cursor(KeysetCursor(value=cursor.value, id=cursor.id))
    return f"{cursor.rank}_{position}"


class RankedKeysetCursorField(KeysetCursorField):
    """
    Accepts what `encode_ranked_keyset_cursor` produced and returns the
    `RankedKeysetCursor`.
    """

    def to_internal_value(self, data) -> RankedKeysetCursor:
        match = _RANKED_KEYSET_CURSOR_RE.fullmatch(str(data))
        if match is None:
            raise serializers.ValidationError("Invalid cursor.")
        rank, position = match.groups()
        cursor = super().to_internal_value(position)
        return RankedKeysetCursor(rank=int(rank), value=cursor.value, id=cursor.id)


class Pageable(Protocol):
    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate a queryset returning a list of objects for the requested page.
        """

    def get_paginated_response(self, data):
        """
        Return a response object that contains the paginated data.
        """

    def get_paginated_response_schema(self, schema):
        """
        Return the schema for the paginated response.
        """


class Paginator(DjangoPaginator):
    """
    A paginator that behaves like the Django paginator but does not validate if the
    requested page is out of range. This is useful for large datasets where counting the
    total number of results is slow.
    """

    def validate_number(self, number):
        """
        Validates the 1-based page number, without raising exceptions. Returns 1 (the
        first page) for invalid values so it's consistent with other pagination methods
        (i.e. offset=-1 when using limit/offset pagination) and skips range checks to
        avoid the need of counting the results, ensuring faster queries.
        """

        try:
            if isinstance(number, float) and not number.is_integer():
                raise ValueError
            number = int(number)
        except (TypeError, ValueError):
            number = 1
        return max(number, 1)


def raise_page_size_limit_exceeded(limit_page_size: int):
    exception = APIException(
        {
            "error": "ERROR_PAGE_SIZE_LIMIT",
            "detail": f"The page size is limited to {limit_page_size}.",
        }
    )
    exception.status_code = HTTP_400_BAD_REQUEST
    raise exception


class PageNumberPagination(RestFrameworkPageNumberPagination):
    # Please keep the default page size in sync with the default prop pageSize in
    # web-frontend/modules/core/components/helpers/InfiniteScroll.vue
    page_size = 100
    page_size_query_param = "size"
    django_paginator_class = Paginator

    def __init__(self, limit_page_size=None, *args, **kwargs):
        self.limit_page_size = limit_page_size
        if limit_page_size:
            self.page_size = min(self.page_size, limit_page_size)
        super().__init__(*args, **kwargs)

    def get_page_size(self, request):
        page_size = super().get_page_size(request)

        if self.limit_page_size and page_size > self.limit_page_size:
            raise_page_size_limit_exceeded(self.limit_page_size)

        return page_size


class PageNumberPaginationWithoutCount(PageNumberPagination):
    def get_page_number(self, request, paginator):
        raw_page_nr = super().get_page_number(request, paginator)
        return paginator.validate_number(raw_page_nr)

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        page_size = self.get_page_size(request)
        if not page_size:
            return None

        paginator = self.django_paginator_class(queryset, page_size)
        page_nr = self.get_page_number(request, paginator)

        start = (page_nr - 1) * page_size  # 1-based page number
        end = start + page_size

        return list(queryset[start:end])

    def get_paginated_response(self, data):
        return Response(
            {
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "required": ["results"],
            "properties": {
                "results": schema,
            },
        }


class LimitOffsetPagination(RestFrameworkLimitOffsetPagination):
    default_limit = 100

    def __init__(self, limit_page_size=None, *args, **kwargs):
        self.limit_page_size = limit_page_size
        if limit_page_size:
            self.default_limit = min(self.default_limit, limit_page_size)
        super().__init__(*args, **kwargs)

    def get_limit(self, request):
        limit = super().get_limit(request)

        if self.limit_page_size and limit and limit > self.limit_page_size:
            raise_page_size_limit_exceeded(self.limit_page_size)

        return limit

    def paginate_queryset(self, queryset, request, view=None):
        return super().paginate_queryset(queryset, request, view)


class LimitOffsetPaginationWithoutCount(LimitOffsetPagination):
    """
    Limit/offset pagination without count, previous, or next links. Optimized for large
    datasets to avoid slow the results by counting all the items in the queryset.
    """

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        self.limit = self.get_limit(request)
        if self.limit is None:
            return None

        self.offset = self.get_offset(request)
        return list(queryset[self.offset : self.offset + self.limit])

    def get_paginated_response(self, data):
        return Response({"results": data})

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "required": ["results"],
            "properties": {
                "results": schema,
            },
        }


class ApproximateCountPaginator(Paginator):
    """
    A paginator that uses Postgres EXPLAIN to estimate the total row count
    instead of running an expensive COUNT(*) query.
    """

    @cached_property
    def count(self):
        return get_approximate_row_count(self.object_list)


class PageNumberPaginationWithApproximateCount(PageNumberPagination):
    """
    Page number pagination that uses an approximate count from Postgres EXPLAIN
    instead of COUNT(*). Suitable for large tables like audit logs where an
    exact count is not required.
    """

    django_paginator_class = ApproximateCountPaginator
