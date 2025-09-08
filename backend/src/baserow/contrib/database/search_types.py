from collections import defaultdict
from typing import Optional

from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank
from django.db.models import (
    Case,
    CharField,
    F,
    IntegerField,
    Prefetch,
    QuerySet,
    Value,
    When,
)

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.operations import ListFieldsOperationType
from baserow.contrib.database.models import Database
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.search_base import DatabaseSearchableItemType
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.operations import ReadDatabaseTableOperationType
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.search.data_types import SearchResult
from baserow.core.search.registries import SearchableItemType
from baserow.core.search.search_types import ApplicationSearchType


class DatabaseSearchType(ApplicationSearchType):
    """
    Searchable item type specifically for databases.
    """

    priority = 1

    type = "database"
    name = "Database"
    model_class = Database

    def serialize_result(
        self, result: Database, user: "AbstractUser", workspace: "Workspace"
    ) -> Optional[SearchResult]:
        """Convert database to search result with database_id in metadata."""

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
                "database_id": result.id,
            },
        )


class TableSearchType(DatabaseSearchableItemType):
    """
    Searchable item type for database tables.
    """

    type = "database_table"
    name = "Tables"
    model_class = Table
    priority = 2

    search_fields = ["name"]
    result_fields = ["id", "name", "created_on", "updated_on"]
    supports_full_text = False

    def get_base_queryset(self, user, workspace) -> QuerySet:
        return (
            Table.objects.filter(
                trashed=False,
                database__trashed=False,
                database__workspace=workspace,
            )
            .select_related("database", "database__workspace")
            .order_by("database__order", "order", "id")
        )

    def get_search_queryset(self, user, workspace, context) -> QuerySet:
        queryset = self.get_base_queryset(user, workspace)

        queryset = CoreHandler().filter_queryset(
            user,
            ReadDatabaseTableOperationType.type,
            queryset,
            workspace=workspace,
        )

        search_q = self.build_search_query(context.query)
        if search_q:
            queryset = queryset.filter(search_q)
        return queryset.annotate(search_type=Value(self.type, output_field=CharField()))

    def serialize_result(self, item, user, workspace) -> Optional[SearchResult]:
        database = item.database
        return SearchResult(
            type=self.type,
            id=item.id,
            title=item.name,
            subtitle=f"{database.name}",
            metadata={
                "workspace_id": workspace.id,
                "database_id": database.id,
                "table_id": item.id,
            },
        )


class FieldDefinitionSearchType(DatabaseSearchableItemType):
    """
    Searchable item type for database fields (definitions only).
    """

    type = "database_field"
    name = "Fields"
    model_class = Field
    priority = 6

    search_fields = ["name", "description"]
    result_fields = ["id", "name", "created_on", "updated_on"]
    supports_full_text = False

    def get_base_queryset(self, user, workspace) -> QuerySet:
        return (
            Field.objects.filter(
                trashed=False,
                table__trashed=False,
                table__database__trashed=False,
                table__database__workspace=workspace,
            )
            .select_related("table", "table__database", "table__database__workspace")
            .order_by("table__database__order", "table__order", "order", "id")
        )

    def get_search_queryset(self, user, workspace, context) -> QuerySet:
        queryset = self.get_base_queryset(user, workspace)

        queryset = CoreHandler().filter_queryset(
            user,
            ListFieldsOperationType.type,
            queryset,
            workspace=workspace,
        )

        search_q = self.build_search_query(context.query)
        if search_q:
            queryset = queryset.filter(search_q)
        return queryset.annotate(search_type=Value(self.type, output_field=CharField()))

    def serialize_result(self, item, user, workspace) -> Optional[SearchResult]:
        database = item.table.database
        table = item.table
        return SearchResult(
            type=self.type,
            id=item.id,
            title=item.name,
            subtitle=f"{database.name} / {table.name}",
            metadata={
                "workspace_id": workspace.id,
                "database_id": database.id,
                "table_id": table.id,
            },
        )


class RowSearchType(SearchableItemType):
    """
    Searchable item type for rows across all tables in a workspace using full text.
    """

    type = "database_row"
    name = "Rows"
    model_class = Table
    supports_full_text = True
    priority = 7

    def get_search_queryset(self, user, workspace, context) -> QuerySet:
        tables = (
            Table.objects.filter(
                trashed=False,
                database__trashed=False,
                database__workspace=workspace,
            )
            .select_related("database", "database__workspace")
            .prefetch_related(
                Prefetch(
                    "field_set", queryset=Field.objects.select_related("content_type")
                )
            )
            .order_by("database__order", "order", "id")
        )

        tables = CoreHandler().filter_queryset(
            user,
            ReadDatabaseTableOperationType.type,
            tables,
            workspace=workspace,
        )
        return tables

    def execute_search(self, user, workspace, context):
        """Optimized row search using search table directly with single query.

        param user: The user requesting the search
        param workspace: The workspace being searched
        param context: Search context with query, limit, offset
        return List[SearchResult]: List of search results
        """

        if not SearchHandler.workspace_search_table_exists(workspace.id):
            return []

        sanitized_query = SearchHandler.escape_postgres_query(context.query)
        if not sanitized_query:
            return []

        return self._search_in_tables(context, workspace, sanitized_query)

    def _format_field_value(self, field_value) -> str:
        """Format the field value for the search result."""

        return str(field_value)[:10]

    def _resolve_specifics_for_model_if_needed(
        self, model, ids_by_model, specific_cache_by_model
    ):
        """Resolve specific field instances for a model if needed."""

        if model in specific_cache_by_model:
            return
        ids = ids_by_model.get(model, [])
        if not ids:
            specific_cache_by_model[model] = {}
            return
        queryset = model._base_manager.filter(pk__in=ids)
        specific_cache_by_model[model] = {item.id: item for item in queryset}

    def _get_effective_field(
        self, f, ct_id_to_model, specific_cache_by_model, ids_by_model
    ):
        """Get the effective field instance (specific or base)."""

        model = ct_id_to_model.get(f.content_type_id)
        self._resolve_specifics_for_model_if_needed(
            model, ids_by_model, specific_cache_by_model
        )
        return specific_cache_by_model.get(model, {}).get(f.id, f)

    def _build_content_type_mapping(self, base_fields):
        """Build content type to model mapping and organize field IDs by model."""

        ct_ids = {f.content_type_id for f in base_fields}
        ct_map = ContentType.objects.in_bulk(ct_ids)
        ct_id_to_model = {
            ct_id: ct_map[ct_id].model_class() for ct_id in ct_ids if ct_id in ct_map
        }

        ids_by_model = defaultdict(list)
        for field in base_fields:
            model = ct_id_to_model.get(field.content_type_id)
            if model is None:
                continue
            ids_by_model[model].append(field.id)

        return ct_id_to_model, ids_by_model

    def _search_in_tables(self, context, workspace, sanitized_query):
        """Optimized search using single query with search table directly."""

        # TODO: Consider raising exception so it can be shown in frontend
        # and trigger update of search table
        if not SearchHandler.workspace_search_table_exists(workspace.id):
            return []

        search_model = SearchHandler.get_workspace_search_table_model(workspace.id)
        search_query = SearchQuery(
            sanitized_query, search_type="raw", config=SearchHandler.search_config()
        )
        fields_query = (
            Field.objects.filter(
                trashed=False,
                table__trashed=False,
                table__database__trashed=False,
                table__database__workspace=workspace,
            )
            .select_related("table__database__workspace", "content_type")
            .all()
        )

        base_fields = list(
            fields_query.only("id", "content_type_id", "name", "table_id", "primary")
        )

        # Build content type mapping and organize field IDs by model
        ct_id_to_model, ids_by_model = self._build_content_type_mapping(base_fields)
        specific_cache_by_model = {}

        # Build a field mapping directly from base_fields (no per-table iteration)
        field_id_to_info = {
            f.id: {
                "field": f,
                "table_id": f.table_id,
            }
            for f in base_fields
        }

        if not field_id_to_info:
            return []

        # Build table_id case for ordering
        when_clauses = [
            When(field_id=fid, then=Value(info["table_id"]))
            for fid, info in field_id_to_info.items()
        ]
        table_id_case = Case(
            *when_clauses, default=Value(0), output_field=IntegerField()
        )

        # Fetch matching search rows with ranking
        matching_search_data = (
            search_model.objects.filter(
                field_id__in=list(field_id_to_info.keys()), value=search_query
            )
            .annotate(
                rank=SearchRank(F("value"), search_query),
                table_id=table_id_case,
            )
            .order_by("-rank", "table_id", "row_id", "field_id")
        )

        paginated_data = list(
            matching_search_data[context.offset : context.offset + context.limit]
        )

        # Gather candidates and group by table
        candidates = []
        table_to_rows = {}
        table_to_fields = {}
        needed_table_ids = set()
        needed_field_ids = set()
        for item in paginated_data:
            field_id = item.field_id
            row_id = item.row_id
            info = field_id_to_info.get(field_id)
            if info is None:
                continue
            table_id = info["table_id"]
            candidates.append((table_id, field_id, row_id, item))
            needed_table_ids.add(table_id)
            needed_field_ids.add(field_id)
            table_to_rows.setdefault(table_id, set()).add(row_id)
            table_to_fields.setdefault(table_id, set()).add(field_id)

        # Now resolve specifics only for field_ids that are actually in the results
        base_fields_by_id = {f.id: f for f in base_fields}
        field_id_to_specific = {}
        for fid in needed_field_ids:
            base_f = base_fields_by_id.get(fid)
            if base_f is None:
                continue
            field_id_to_specific[fid] = self._get_effective_field(
                base_f, ct_id_to_model, specific_cache_by_model, ids_by_model
            )

        # Fetch needed tables in one query
        tables_by_id = {
            t.id: t
            for t in Table.objects.filter(id__in=list(needed_table_ids)).select_related(
                "database"
            )
        }

        # Compute snippets only for the needed tables/fields/rows
        snippets = {}
        for table_id in needed_table_ids:
            table = tables_by_id.get(table_id)
            if table is None:
                continue
            field_ids = list(table_to_fields.get(table_id, set()))
            if not field_ids:
                continue
            row_ids = list(table_to_rows.get(table_id, set()))
            if not row_ids:
                continue

            # Limit generated model to just the needed fields for performance
            model = table.get_model(field_ids=field_ids)
            base_qs = model.objects.filter(id__in=row_ids)

            for field_id in field_ids:
                specific_field = field_id_to_specific.get(field_id)
                if specific_field is None:
                    continue
                field_qs = base_qs.all()
                text_expr = specific_field.get_type().get_search_expression(
                    specific_field, field_qs
                )
                annotated = field_qs.annotate(
                    snippet=SearchHeadline(
                        text_expr,
                        search_query,
                        config=SearchHandler.search_config(),
                        start_sel="[[H]]",
                        stop_sel="[[/H]]",
                        max_fragments=1,
                        max_words=8,
                        min_words=3,
                        short_word=1,
                        fragment_delimiter=" … ",
                    )
                ).values("id", "snippet")

                for row in annotated:
                    key = (table_id, row["id"], field_id)
                    snippets[key] = row["snippet"]

        # Build final results
        results = []
        for table_id, field_id, row_id, item in candidates:
            table = tables_by_id.get(table_id)
            specific_field = field_id_to_specific.get(field_id)
            subtitle_field = (
                specific_field.name if specific_field is not None else field_id
            )
            snippet = snippets.get((table_id, row_id, field_id))
            results.append(
                SearchResult(
                    type=self.type,
                    id=f"{table_id}_{row_id}",
                    title=f"row {row_id}",
                    subtitle=f"{table.name} > {subtitle_field}",
                    description=snippet,
                    metadata={
                        "workspace_id": workspace.id,
                        "database_id": table.database_id,
                        "table_id": table_id,
                        "row_id": row_id,
                        "field_id": field_id,
                        "rank": getattr(item, "rank", None),
                    },
                )
            )
        return results
