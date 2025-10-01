from typing import TYPE_CHECKING, Dict, Iterable, List, Optional

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import JSONField, QuerySet, Value

from loguru import logger

from baserow.core.registry import Instance, ModelInstanceMixin, Registry
from baserow.core.search.constants import STANDARD_UNION_FIELDS
from baserow.core.search.data_types import SearchContext, SearchResult
from baserow.core.utils import exception_capturer

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

        qs = self.get_search_queryset(user, workspace, context)
        if qs is None:
            qs = self.model_class.objects.none()
        qs = qs.annotate(
            search_type=Value(self.type, output_field=models.TextField()),
            object_id=models.Cast("id", models.TextField()),
            sort_key=models.F("id"),
            rank=Value(None, output_field=models.FloatField()),
            priority=Value(getattr(self, "priority", 10)),
            title=Value(None, output_field=models.TextField()),
            subtitle=Value(None, output_field=models.TextField()),
            payload=Value({}, output_field=JSONField()),
        )
        return qs.values(*STANDARD_UNION_FIELDS)

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
        for r in rows:
            payload = r.get("payload") or {}
            results.append(
                SearchResult(
                    type=r["search_type"],
                    id=r["object_id"],
                    title=r.get("title") or str(r.get("object_id")),
                    subtitle=r.get("subtitle"),
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

    def search_all_types(
        self, user: "AbstractUser", workspace: "Workspace", context: SearchContext
    ) -> List[SearchResult]:
        """
        Build a single UNION ALL over all registered types standardized value
        querysets, apply global ordering and pagination, then postprocess the
        paginated slice per type.
        """

        # Build union of standardized values querysets
        type_items = [(name, self.get(name)) for name in self.registry.keys()]
        # No need to sort before union; priority is part of rows and used in ordering.

        union_qs: Optional[QuerySet] = None
        for _name, st in type_items:
            try:
                qs = st.get_union_values_queryset(user, workspace, context)
            except Exception as e:
                logger.error(
                    "Workspace search failed building queryset for type {type}",
                    type=st.type,
                )
                exception_capturer(e)
                logger.exception(e)
                continue
            if union_qs is None:
                union_qs = qs
            else:
                union_qs = union_qs.union(qs, all=True)

        if union_qs is None:
            return []

        # Global ordering: priority asc first (type-level ordering),
        # then rank desc within each type, then object_id asc for determinism.
        union_qs = union_qs.order_by(
            "priority",
            models.F("rank").desc(nulls_last=True),
            "sort_key",
            "object_id",
        )

        # Global pagination (+1 for has_more handled by caller/handler)
        start = context.offset
        end = start + context.limit
        page_rows: List[Dict] = list(union_qs[start:end])

        # Group by search_type and postprocess
        rows_by_type: Dict[str, List[Dict]] = {}
        for r in page_rows:
            rows_by_type.setdefault(r["search_type"], []).append(r)

        results_by_type: Dict[str, List[SearchResult]] = {}
        for type_name, rows in rows_by_type.items():
            st = self.get(type_name)
            try:
                results_by_type[type_name] = st.postprocess(rows)
            except Exception as e:
                logger.error(
                    "Workspace search postprocess failed for type {type}",
                    type=type_name,
                )
                exception_capturer(e)
                logger.exception(e)
                results_by_type[type_name] = []

        # Merge back in the original order
        flat_results: List[SearchResult] = []
        for r in page_rows:
            type_name = r["search_type"]
            lst = results_by_type.get(type_name, [])
            if lst:
                flat_results.append(lst.pop(0))
            else:
                # Fallback: ensure count stays consistent for has_more detection
                payload = r.get("payload") or {}
                flat_results.append(
                    SearchResult(
                        type=type_name,
                        id=r["object_id"],
                        title=str(r.get("title") or r["object_id"]),
                        subtitle=r.get("subtitle"),
                        description=payload.get("description"),
                        created_on=payload.get("created_on"),
                        updated_on=payload.get("updated_on"),
                        metadata=payload,
                    )
                )

        return flat_results


workspace_search_registry = WorkspaceSearchRegistry()
