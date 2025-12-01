from typing import TYPE_CHECKING, Dict, Iterable, List, Optional

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import QuerySet

from baserow.core.registry import Instance, ModelInstanceMixin, Registry
from baserow.core.search.data_types import SearchContext, SearchResult

if TYPE_CHECKING:
    from baserow.core.models import Workspace


class SearchableItemType(ModelInstanceMixin, Instance):
    """
    Base class for all searchable item types in workspace search.

    Each searchable item type represents a different type of content
    that can be searched (tables, applications, rows, etc.).
    """

    type: str = None
    name: str = None
    model_class = None
    priority: int = 10

    def __init__(self):
        super().__init__()
        if not self.name:
            raise ValueError(f"SearchableItemType {self.type} must define a name")

    def get_base_queryset(
        self, user: "AbstractUser", workspace: "Workspace"
    ) -> models.QuerySet:
        """
        Get the base queryset for searching this item type in a workspace.

        param user: The user requesting the search (for permission filtering)
        param workspace: The workspace to search in
        return models.QuerySet: Base queryset for this item type
        """

        pass

    def get_search_queryset(
        self,
        user: "AbstractUser",
        workspace: "Workspace",
        context: SearchContext,
    ) -> models.QuerySet:
        """
        Build search queryset without executing it for optimal query combining.

        param user: The user requesting search
        param workspace: The workspace being searched
        param context: Search context with query, limit, offset
        return models.QuerySet: Prepared queryset ready for execution
        """

        pass

    def get_union_values_queryset(
        self,
        user: "AbstractUser",
        workspace: "Workspace",
        context: SearchContext,
    ) -> QuerySet:
        """
        Return a queryset of dict rows with the standardized fields defined in
        STANDARD_UNION_FIELDS. Implementations must ensure the queryset only
        returns rows the user has permission to see and filters by the query.
        No limit/offset should be applied here.
        """

        raise NotImplementedError("This method must be implemented by the subclass")

    def execute_search(
        self, user: "AbstractUser", workspace: "Workspace", context: SearchContext
    ) -> List[SearchResult]:
        """
        Execute search with user and workspace objects.

        param user: The user requesting search
        param workspace: The workspace being searched
        param context: Search context with query, limit, offset
        return List[SearchResult]: List of search results
        """

        queryset = self.get_search_queryset(user, workspace, context)

        start = context.offset
        end = start + context.limit
        items = queryset[start:end]

        results = []
        for item in items:
            result = self.serialize_result(item, user, workspace)
            if result:
                results.append(result)

        return results

    def postprocess(self, rows: Iterable[Dict]) -> List[SearchResult]:
        """
        Convert standardized union rows belonging to this type into SearchResult
        objects. Implementations can override to bulk-fetch extra data or compute
        additional fields (like highlights). Default maps directly.
        """

        results: List[SearchResult] = []
        for row in rows:
            payload = row.get("payload") or {}
            results.append(
                SearchResult(
                    type=row["search_type"],
                    id=row["object_id"],
                    title=row.get("title") or str(row.get("object_id")),
                    subtitle=row.get("subtitle"),
                    description=payload.get("description"),
                    created_on=payload.get("created_on"),
                    updated_on=payload.get("updated_on"),
                    metadata=payload,
                )
            )
        return results

    def serialize_result(
        self, item: models.Model, user: "AbstractUser", workspace: "Workspace"
    ) -> Optional[SearchResult]:
        """
        Convert a model instance to a SearchResult.

        param item: The model instance to serialize
        param user: The user requesting the search
        param workspace: The workspace context
        return Optional[SearchResult]: Serialized search result, or None to exclude
        """

        pass


class WorkspaceSearchRegistry(Registry):
    """
    Registry for all searchable item types in workspace search.
    """

    name = "workspace_search"


workspace_search_registry = WorkspaceSearchRegistry()
