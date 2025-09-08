import abc
from typing import TYPE_CHECKING, List, Optional

from django.contrib.auth.models import AbstractUser
from django.db import models

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

    @abc.abstractmethod
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

    @abc.abstractmethod
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

    @abc.abstractmethod
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

    def search_all_types(
        self, user: "AbstractUser", workspace: "Workspace", context: SearchContext
    ) -> List[SearchResult]:
        """
        Priority-based search across all registered item types, returning a flat list.

        param user: The user requesting search
        param workspace: The workspace being searched
        param context: Search context with query, limit, offset
        return List[SearchResult]: Flat list of results ordered by type priority
        """

        types_to_search = list(self.registry.keys())

        search_types = [(name, self.get(name)) for name in types_to_search]
        search_types.sort(key=lambda x: x[1].priority)

        flat_results: List[SearchResult] = []
        total_results_so_far = 0

        for _type_name, search_type in search_types:
            remaining_limit = context.limit - total_results_so_far
            if remaining_limit <= 0:
                break

            type_context = SearchContext(
                query=context.query,
                limit=remaining_limit,
                offset=context.offset if total_results_so_far == 0 else 0,
            )

            type_results = search_type.execute_search(user, workspace, type_context)
            if type_results:
                flat_results.extend(type_results)
                total_results_so_far += len(type_results)

        return flat_results


workspace_search_registry = WorkspaceSearchRegistry()
