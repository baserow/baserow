"""
Global search handler for orchestrating search operations across different types.
"""

from typing import TYPE_CHECKING, Any, Dict

from django.contrib.auth.models import AbstractUser

from baserow.core.search.data_types import SearchContext
from baserow.core.search.registries import workspace_search_registry

if TYPE_CHECKING:
    from baserow.core.models import Workspace


class WorkspaceSearchHandler:
    """
    Handler for workspace search operations across all registered search types.
    """

    def search_workspace(
        self,
        user: "AbstractUser",
        workspace: "Workspace",
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Execute workspace search within a workspace.

        param user: The user performing the search
        param workspace: The workspace to search within
        param query: Search query string
        param limit: Maximum number of results to return
        param offset: Result offset for pagination

        return Dict with a flat, priority-ordered list of search results
            and has_more flag
        """

        # Use limit+1 to detect if there are more results overall
        search_limit = limit + 1

        context = SearchContext(
            query=query,
            limit=search_limit,
            offset=offset,
        )

        raw_results = workspace_search_registry.search_all_types(
            user, workspace, context
        )

        results_list = [result.to_dict() for result in raw_results]

        has_more = len(results_list) > limit
        if has_more:
            results_list = results_list[:limit]

        return {
            "results": results_list,
            "has_more": has_more,
        }
