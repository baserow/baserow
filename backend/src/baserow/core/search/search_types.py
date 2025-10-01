from typing import Optional

from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import CharField, F, QuerySet, TextField, Value
from django.db.models.functions import Cast, JSONObject

from baserow.contrib.database.search_base import DatabaseSearchableItemType
from baserow.core.handler import CoreHandler
from baserow.core.models import Application, Workspace
from baserow.core.operations import ReadApplicationOperationType
from baserow.core.search.data_types import SearchContext, SearchResult


class ApplicationSearchType(DatabaseSearchableItemType):
    """
    Searchable item type for applications (databases, builders, etc.).
    """

    type = "application"
    name = "Applications"
    model_class = Application
    search_fields = ["name"]

    def get_base_queryset(
        self, user: "AbstractUser", workspace: "Workspace"
    ) -> QuerySet:
        """Get applications in the workspace.

        param user: The user requesting the search
        param workspace: The workspace being searched

        return QuerySet: Queryset of applications in the workspace
        """

        return (
            self.model_class.objects.filter(
                workspace=workspace, workspace__trashed=False
            )
            .select_related("workspace")
            .order_by("order", "id")
        )

    def get_search_queryset(
        self,
        user: "AbstractUser",
        workspace: "Workspace",
        context: SearchContext,
    ) -> QuerySet:
        """Build search queryset for applications.

        param user: The user requesting the search
        param workspace: The workspace being searched
        param context: The search context

        return QuerySet: Queryset of applications in the workspace
        """

        queryset = self.get_base_queryset(user, workspace)

        # Apply permission filtering using the existing system, scoping to workspace.
        # This ensures we only return applications the user can read, in a single
        # queryset.
        queryset = CoreHandler().filter_queryset(
            user,
            ReadApplicationOperationType.type,
            queryset,
            workspace=workspace,
        )
        search_q = self.build_search_query(context.query)
        if search_q:
            queryset = queryset.filter(search_q)
        queryset = queryset.annotate(
            search_type=Value(self.type, output_field=CharField())
        )
        return queryset

    def get_union_values_queryset(
        self,
        user: "AbstractUser",
        workspace: "Workspace",
        context: SearchContext,
    ) -> QuerySet:
        qs = self.get_search_queryset(user, workspace, context)

        # Create search query and vector for ranking
        search_query = SearchQuery(
            context.query, search_type="websearch", config="english"
        )
        search_vector = SearchVector("name", config="english")

        qs = qs.annotate(
            search_type=Value(self.type, output_field=TextField()),
            object_id=Cast(F("id"), output_field=TextField()),
            sort_key=F("id"),
            rank=SearchRank(search_vector, search_query),
            priority=Value(getattr(self, "priority", 10)),
            title=Cast(F("name"), output_field=TextField()),
            subtitle=Value(self.type),
            payload=JSONObject(),
        ).values(
            "search_type",
            "object_id",
            "sort_key",
            "rank",
            "priority",
            "title",
            "subtitle",
            "payload",
        )
        return qs

    def serialize_result(
        self, result: Application, user: "AbstractUser", workspace: "Workspace"
    ) -> Optional[SearchResult]:
        """Convert application to search result.

        param item: The application to serialize
        param user: The user requesting the search
        param workspace: The workspace being searched

        return Optional[SearchResult]: Serialized search result
        """

        return SearchResult(
            type=self.type,
            id=result.id,
            title=result.name,
            subtitle=self.type,
            created_on=result.created_on.isoformat() if result.created_on else None,
            updated_on=result.updated_on.isoformat() if result.updated_on else None,
            metadata={
                "workspace_id": workspace.id,
                "workspace_name": workspace.name,
            },
        )
