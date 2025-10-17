from typing import TYPE_CHECKING, List

from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import models
from django.db.models import CharField, F, Q, TextField, Value
from django.db.models.functions import Cast, JSONObject

from baserow.core.search.data_types import SearchContext
from baserow.core.search.registries import SearchableItemType

if TYPE_CHECKING:
    from baserow.core.models import Workspace


class ModelSearchableItemType(SearchableItemType):
    """
    Generic model-backed searchable type with shared ORM search logic and hooks.
    Lives in core to avoid core -> contrib imports.
    """

    search_fields: List[str] = []
    supports_full_text: bool = False

    def build_search_query(self, query: str) -> Q:
        if not self.search_fields:
            return Q()
        conditions = Q()
        for field in self.search_fields:
            conditions |= Q(**{f"{field}__icontains": query})
        return conditions

    def get_base_queryset(
        self, user: "AbstractUser", workspace: "Workspace"
    ) -> models.QuerySet:
        return self.model_class.objects.none()

    def get_search_queryset(
        self, user: "AbstractUser", workspace: "Workspace", context: SearchContext
    ) -> models.QuerySet:
        qs = self.get_base_queryset(user, workspace)
        search_q = self.build_search_query(context.query)
        if search_q:
            qs = qs.filter(search_q)
        return qs.annotate(search_type=Value(self.type, output_field=CharField()))

    def build_payload(self):
        return JSONObject()

    def build_title_annotation(self):
        return Cast(F("name"), output_field=TextField())

    def build_subtitle_annotation(self):
        return Value(self.name, output_field=TextField())

    def get_union_values_queryset(
        self, user: "AbstractUser", workspace: "Workspace", context: SearchContext
    ) -> models.QuerySet:
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
