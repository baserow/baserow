from typing import TYPE_CHECKING, List

from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import models
from django.db.models import CharField, F, Q, TextField, Value
from django.db.models.functions import Cast, JSONObject

from baserow.core.search.data_types import SearchContext
from baserow.core.search.model_search_base import ModelSearchableItemType

if TYPE_CHECKING:
    from baserow.core.models import Workspace


class DatabaseSearchableItemType(ModelSearchableItemType):
    """
    Base class for searchable item types that use Django ORM for database operations.
    """

    search_fields: List[str] = []
    result_fields: List[str] = []
    supports_full_text: bool = False

    def build_search_query(self, query: str) -> Q:
        """
        Build Django Q object for searching across search_fields.

        Default implementation searches across all search_fields using icontains.
        Override for custom search logic.

        param query: The search query string
        return Q: Django Q object for the search
        """

        if not self.search_fields:
            return Q()

        search_conditions = Q()
        for field in self.search_fields:
            search_conditions |= Q(**{f"{field}__icontains": query})

        return search_conditions

    def get_search_queryset(
        self,
        user: "AbstractUser",
        workspace: "Workspace",
        context: SearchContext,
    ) -> models.QuerySet:
        """
        Build search queryset using Django ORM and search_fields.

        Default implementation that works for most Django model-based searches.
        Override for custom search logic (like RowSearchType).

        param user: The user requesting search
        param workspace: The workspace being searched
        param context: Search context with query, limit, offset
        return models.QuerySet: Prepared queryset ready for execution
        """

        queryset = self.get_base_queryset(user, workspace)

        search_q = self.build_search_query(context.query)
        if search_q:
            queryset = queryset.filter(search_q)

        queryset = queryset.annotate(
            search_type=Value(self.type, output_field=CharField())
        )
        return queryset

    def build_payload(self):
        """
        Default payload for name-based searchable items.
        """

        return JSONObject()

    def build_title_annotation(self):
        return Cast(F("name"), output_field=TextField())

    def build_subtitle_annotation(self):
        return Value(self.type, output_field=TextField())

    def get_union_values_queryset(
        self,
        user: "AbstractUser",
        workspace: "Workspace",
        context: SearchContext,
    ) -> models.QuerySet:
        """
        Default union values queryset: ranks by SearchRank on name and emits
        standardized fields including a JSON payload. Subclasses can override
        build_payload() to customize the payload.
        """

        qs = self.get_search_queryset(user, workspace, context)

        search_query = SearchQuery(
            context.query, search_type="websearch", config="english"
        )
        search_vector = SearchVector("name", config="english")

        qs = qs.annotate(
            search_type=Value(self.type, output_field=TextField()),
            object_id=Cast(F("id"), output_field=TextField()),
            sort_key=F("id"),
            rank=SearchRank(search_vector, search_query),
            priority=Value(self.priority),
            title=self.build_title_annotation(),
            subtitle=self.build_subtitle_annotation(),
            payload=self.build_payload(),
        )

        return qs.values(
            "search_type",
            "object_id",
            "sort_key",
            "rank",
            "priority",
            "title",
            "subtitle",
            "payload",
        )
