from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import QuerySet

from loguru import logger
from typing_extensions import List

from baserow.api.search.constants import DEFAULT_SEARCH_LIMIT
from baserow.core.search.data_types import SearchContext, SearchResult
from baserow.core.search.registries import workspace_search_registry

if TYPE_CHECKING:
    from baserow.core.models import Workspace


class WorkspaceSearchHandler:
    """
    Handler for workspace search operations across all registered search types.
    """

    def search_all_types(
        self, user: "AbstractUser", workspace: "Workspace", context: SearchContext
    ) -> Tuple[List[SearchResult], bool]:
        """
        Build a single UNION ALL over all registered types standardized value
        querysets, apply global ordering and pagination, then postprocess the
        paginated slice per type.
        """

        # Build union of standardized values querysets
        type_items = [
            (name, workspace_search_registry.get(name))
            for name in workspace_search_registry.registry.keys()
        ]
        # No need to sort before union; priority is part of rows and used in ordering.

        union_qs: Optional[QuerySet] = None
        for _name, st in type_items:
            try:
                qs = st.get_union_values_queryset(user, workspace, context)
            except Exception:
                logger.exception(
                    "Workspace search failed building queryset for type {type}",
                    type=st.type,
                )
                continue
            if union_qs is None:
                union_qs = qs
            else:
                union_qs = union_qs.union(qs, all=True)

        if union_qs is None:
            return [], False

        # Global ordering: priority asc first (type-level ordering),
        # then rank desc within each type, then object_id asc for determinism.
        union_qs = union_qs.order_by(
            "priority",
            models.F("rank").desc(nulls_last=True),
            "sort_key",
        )

        # Global pagination (+1 for has_more handled by caller/handler)
        start = context.offset
        end = start + context.limit
        page_rows: List[Dict] = list(union_qs[start:end])
        has_more = len(page_rows) == (end - start)

        # Group by search_type and postprocess
        rows_by_type: Dict[str, List[Dict]] = {}
        for result in page_rows:
            rows_by_type.setdefault(result["search_type"], []).append(result)

        results_by_type: Dict[str, List[SearchResult]] = {}
        for type_name, results in rows_by_type.items():
            st = workspace_search_registry.get(type_name)
            try:
                results_by_type[type_name] = st.postprocess(results)
            except Exception:
                logger.exception(
                    "Workspace search postprocess failed for type {type}",
                    type=type_name,
                )
                results_by_type[type_name] = []

        # Index results by id per type to ensure stable ordering matching page_rows
        results_by_type_and_id: Dict[str, Dict[Any, SearchResult]] = {}
        for type_name, results in results_by_type.items():
            by_id: Dict[Any, SearchResult] = {}
            for result in results:
                by_id[str(result.id)] = result
            results_by_type_and_id[type_name] = by_id

        # Merge back in the original order
        flat_results: List[SearchResult] = []
        for result in page_rows:
            type_name = result["search_type"]
            by_id = results_by_type_and_id.get(type_name, {})
            result = by_id.pop(result["object_id"], None)
            if result is not None:
                flat_results.append(result)

        return flat_results, has_more

    def search_workspace(
        self,
        user: "AbstractUser",
        workspace: "Workspace",
        query: str,
        limit: int = DEFAULT_SEARCH_LIMIT,
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

        raw_results, has_more = self.search_all_types(user, workspace, context)

        results_list = [result.to_dict() for result in raw_results]

        if len(results_list) > limit:
            results_list = results_list[:limit]

        return {
            "results": results_list,
            "has_more": has_more,
        }
