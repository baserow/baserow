from typing import Dict, List, Union

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS
from django.db.models import Q, QuerySet, Value
from django.http import QueryDict

from baserow.api.exceptions import (
    InvalidSortAttributeException,
    InvalidSortDirectionException,
    UnknownFieldProvided,
)
from baserow.config.db_routers import set_db_alias


class RealtimeRecoveryPrimaryReadMixin:
    """
    Pins authenticated realtime recovery reads to the primary database.

    Realtime refresh markers are emitted after a primary-database snapshot. Reading
    their replacement data from a lagging replica could otherwise restore stale state
    in the client. Authentication is deliberately completed before honoring the header
    so anonymous callers cannot opt arbitrary public reads into primary traffic.
    """

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if (
            request.method == "GET"
            and request.headers.get(settings.REALTIME_RECOVERY_HEADER) == "true"
            and request.user.is_authenticated
        ):
            set_db_alias(DEFAULT_DB_ALIAS)


class UnknownFieldRaisesExceptionSerializerMixin:
    """
    Mixin to a DRF serializer class to raise an exception if data with unknown fields
    is provided to the serializer.
    """

    def __init__(self, *args, **kwargs):
        self._baserow_internal_initial_data = None
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        self._baserow_internal_initial_data = data
        return super().to_internal_value(data)

    @property
    def safe_initial_data(self):
        """
        Returns the initial data provided by the user to this serializer. Works for
        both top level serializers and model serializers and also nested serializers.

        For the highest serializer in the DRF Class hierarchy initial_data will
        be populated with the raw initial data provided by the user and so this property
        uses that when available.

        However, for nested serializers initial_data is not populated by DRF. The only
        way we can get access to the raw data provided by the user (so we can check
        what keys they provided by DRF ignores them by default) is by overriding
        `to_internal_value` above and keeping track of the data parameter.
        """

        if hasattr(self, "initial_data"):
            return self.initial_data
        else:
            return self._baserow_internal_initial_data

    def validate(self, data):
        safe_initial_data = self.safe_initial_data
        if safe_initial_data is not None:
            unknown_field_names = set(safe_initial_data.keys()) - set(
                self.fields.keys()
            )
            if unknown_field_names:
                unknown_field_names_csv = ", ".join(unknown_field_names)
                raise UnknownFieldProvided(
                    detail=f"Your request body had the following unknown attributes:"
                    f" {unknown_field_names_csv}. Please check the api documentation "
                    f"and only "
                    f"provide valid fields.",
                )

        return data


class SearchableViewMixin:
    """
    This mixin can be used to add search functionality to a view. The view must
    define `search_fields`.
    """

    # The fields that can be searched on.
    # Needs to be overwritten by the class that uses this mixin.
    search_fields: List[str] = []

    def apply_search(self, search: Union[str, None], queryset: QuerySet) -> QuerySet:
        """
        Applies the provided search query to the provided query. If the search query
        is provided then an `icontains` lookup will be done for each field in the
        search_fields property. One of the fields has to match the query.

        :param search: The search query.
        :type search: str or None
        :param queryset: The queryset where the search query must be applied to.
        :type queryset: QuerySet
        :return: The queryset filtering the results by the search query.
        :rtype: QuerySet
        """

        if not search:
            return queryset

        q = Q()

        for search_field in self.search_fields:
            q.add(Q(**{f"{search_field}__icontains": Value(search)}), Q.OR)

        return queryset.filter(q)


class SortableViewMixin:
    # The fields that can be sorted on.
    # It's a mapping from the field name in the request to teh field name in the
    # database.
    sort_field_mapping: Dict[str, str] = {}
    default_order_by: str = "id"

    def apply_sorts_or_default_sort(
        self, sorts: Union[str, None], queryset: QuerySet
    ) -> QuerySet:
        """
        Takes a comma separated string in the form of +attribute,-attribute2 and
        applies them to a django queryset in order.
        Defaults to sorting by id if no sorts are provided.
        Raises an InvalidSortDirectionException if an attribute does not begin with `+`
        or `-`.
        Raises an InvalidSortAttributeException if an unknown attribute is supplied to
        sort by or multiple of the same attribute are provided.

        :param sorts: The list of sorts to apply to the queryset.
        :param queryset: The queryset to sort.
        :return: The sorted queryset.
        """

        if sorts is None:
            return queryset.order_by(self.default_order_by)

        parsed_django_order_bys = []
        already_seen_sorts = set()
        for s in sorts.split(","):
            if len(s) <= 2:
                raise InvalidSortAttributeException()

            sort_direction_prefix = s[0]
            sort_field_name = s[1:]

            try:
                sort_direction_to_django_prefix = {"+": "", "-": "-"}
                direction = sort_direction_to_django_prefix[sort_direction_prefix]
            except KeyError:
                raise InvalidSortDirectionException()

            try:
                attribute = self.sort_field_mapping[sort_field_name]
            except KeyError:
                raise InvalidSortAttributeException()

            if attribute in already_seen_sorts:
                raise InvalidSortAttributeException()
            else:
                already_seen_sorts.add(attribute)

            parsed_django_order_bys.append(f"{direction}{attribute}")

        return queryset.order_by(*parsed_django_order_bys)


class FilterableViewMixin:
    filters_field_mapping: Dict[str, str] = {}

    def apply_filters(self, query_params: QueryDict, queryset: QuerySet) -> QuerySet:
        """
        Applies the provided filters to the provided query. If the filters are
        provided then an `exact` lookup will be done for each field in the
        filters_fields property. One of the fields has to match the query.

        :param query_params: The request query parameters.
        :param queryset: The queryset where the filters query must be applied to.
        :return: The queryset filtering the results by the filters query.
        """

        q = Q()

        for key, field in self.filters_field_mapping.items():
            if (value := query_params.get(key)) is None:
                continue

            q.add(Q(**{f"{field}": Value(value)}), Q.AND)

        return queryset.filter(q)
