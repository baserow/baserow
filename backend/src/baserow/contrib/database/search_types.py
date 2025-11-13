from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import (
    Case,
    CharField,
    F,
    FloatField,
    IntegerField,
    OuterRef,
    Prefetch,
    QuerySet,
    Subquery,
    TextField,
    Value,
    When,
    Window,
)
from django.db.models.functions import Cast, Concat, JSONObject, RowNumber

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.operations import ListFieldsOperationType
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.models import Database
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.search_base import DatabaseSearchableItemType
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.operations import ReadDatabaseTableOperationType
from baserow.core.db import specific_iterator
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.search.data_types import SearchResult
from baserow.core.search.registries import SearchableItemType
from baserow.core.search.search_types import ApplicationSearchType


def _empty_annotated_table_queryset(search_type: str, priority: int):
    return (
        Table.objects.none()
        .annotate(
            search_type=Value(search_type, output_field=TextField()),
            object_id=Value("", output_field=TextField()),
            sort_key=Value(0, output_field=IntegerField()),
            rank=Value(None, output_field=FloatField()),
            priority=Value(priority),
            title=Value(None, output_field=TextField()),
            subtitle=Value(None, output_field=TextField()),
            payload=JSONObject(),
        )
        .values(
            "search_type",
            "object_id",
            "sort_key",
            "rank",
            "priority",
            "title",
            "subtitle",
            "payload",
        )
    )


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
            subtitle=self.name,
            created_on=result.created_on,
            updated_on=result.updated_on,
            metadata={
                "workspace_id": workspace.id,
                "workspace_name": workspace.name,
                "database_id": result.id,
            },
        )

    def build_subtitle_annotation(self):
        return Value(self.name, output_field=TextField())


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
            .select_related("database__workspace")
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

    def build_payload(self):
        return JSONObject(
            title=F("name"),
            subtitle=F("database__name"),
            workspace_id=F("database__workspace_id"),
            database_id=F("database_id"),
            table_id=F("id"),
            table_name=F("name"),
            database_name=F("database__name"),
        )

    def build_subtitle_annotation(self):
        return Concat(
            Value("Table in ", output_field=TextField()),
            Cast(F("database__name"), output_field=TextField()),
            output_field=TextField(),
        )

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
        return FieldHandler().get_base_fields_queryset()

    def get_search_queryset(self, user, workspace, context) -> QuerySet:
        allowed_tables_qs = Table.objects.filter(
            trashed=False,
            database__trashed=False,
            database__workspace=workspace,
        ).values("id")

        queryset = self.get_base_queryset(user, workspace).filter(
            trashed=False,
            table__trashed=False,
            table__database__trashed=False,
            table_id__in=allowed_tables_qs,
        )

        queryset = CoreHandler().filter_queryset(
            user,
            ListFieldsOperationType.type,
            queryset,
            workspace=workspace,
        )

        search_q = self.build_search_query(context.query)
        if search_q:
            queryset = queryset.filter(search_q)
        return queryset.annotate(
            search_type=Value(self.type, output_field=CharField()),
            title=F("name"),
            subtitle=self.build_subtitle_annotation(),
            payload=self.build_payload(),
        ).order_by("id")

    def build_subtitle_annotation(self):
        return Concat(
            Value("Field in ", output_field=TextField()),
            Cast(F("table__database__name"), output_field=TextField()),
            Value(" / ", output_field=TextField()),
            Cast(F("table__name"), output_field=TextField()),
            output_field=TextField(),
        )

    def build_payload(self):
        return JSONObject(
            workspace_id=F("table__database__workspace_id"),
            database_id=F("table__database_id"),
            table_id=F("table_id"),
            field_id=F("id"),
        )

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
            .prefetch_related(Prefetch("field_set", queryset=Field.objects.all()))
            .order_by("database__order", "order", "id")
        )

        tables = CoreHandler().filter_queryset(
            user,
            ReadDatabaseTableOperationType.type,
            tables,
            workspace=workspace,
        )
        return tables

    def get_union_values_queryset(self, user, workspace, context) -> QuerySet:
        """
        Optimized approach using window function to pick best field per row.
        Uses ROW_NUMBER() OVER (
            PARTITION BY table_id, row_id ORDER BY rank DESC, field_id ASC
        )
        to select only the highest-ranking field for each row.
        """

        if not SearchHandler.workspace_search_table_exists(workspace.id):
            return _empty_annotated_table_queryset(
                self.type, getattr(self, "priority", 10)
            )

        sanitized_query = SearchHandler.escape_postgres_query(context.query)
        if not sanitized_query:
            return _empty_annotated_table_queryset(
                self.type, getattr(self, "priority", 10)
            )

        # Limit to tables user can read
        tables_qs = Table.objects.filter(
            trashed=False,
            database__trashed=False,
            database__workspace=workspace,
        )
        tables_qs = CoreHandler().filter_queryset(
            user,
            ReadDatabaseTableOperationType.type,
            tables_qs,
            workspace=workspace,
        )
        allowed_table_ids = list(tables_qs.values_list("id", flat=True))
        if not allowed_table_ids:
            return _empty_annotated_table_queryset(
                self.type, getattr(self, "priority", 10)
            )

        search_model = SearchHandler.get_workspace_search_table_model(workspace.id)
        search_query = SearchQuery(
            sanitized_query, search_type="raw", config=SearchHandler.search_config()
        )

        # Get permission-filtered fields with table_id using the handler without
        # deferring fields to avoid conflicts with select_related
        base_fields_qs = (
            FieldHandler()
            .get_base_fields_queryset()
            .filter(
                trashed=False,
                table__trashed=False,
                table__database__trashed=False,
                table__database__workspace=workspace,
                table_id__in=allowed_table_ids,
            )
        )

        # Apply permission filtering to fields query before reducing to tuples
        fields_qs = CoreHandler().filter_queryset(
            user,
            ListFieldsOperationType.type,
            base_fields_qs,
            workspace=workspace,
        )
        base_fields = list(fields_qs.values_list("id", "table_id"))
        if not base_fields:
            return _empty_annotated_table_queryset(
                self.type, getattr(self, "priority", 10)
            )

        # Build field_id -> table_id mapping for CASE expression
        when_clauses = [
            When(field_id=f_id, then=Value(t_id)) for (f_id, t_id) in base_fields
        ]
        table_id_case = Case(
            *when_clauses, default=Value(0), output_field=IntegerField()
        )

        # Use window function to pick best field per row (highest rank, lowest field_id)
        qs = (
            search_model.objects.filter(
                field_id__in=[f_id for (f_id, _t_id) in base_fields], value=search_query
            )
            .annotate(
                rank=SearchRank(F("value"), search_query),
                table_id=table_id_case,
                rn=Window(
                    expression=RowNumber(),
                    partition_by=[F("table_id"), F("row_id")],
                    order_by=[F("rank").desc(), F("field_id").asc()],
                ),
            )
            .filter(rn=1)  # Only keep the best field per row
            .annotate(
                search_type=Value(self.type, output_field=TextField()),
                object_id=Concat(
                    Cast(F("table_id"), output_field=TextField()),
                    Value("_", output_field=TextField()),
                    Cast(F("row_id"), output_field=TextField()),
                    output_field=TextField(),
                ),
                sort_key=F("row_id"),
                priority=Value(self.priority),
                title=Concat(
                    Value("row "),
                    Cast(F("row_id"), output_field=TextField()),
                    output_field=TextField(),
                ),
                subtitle=Value(None, output_field=TextField()),
                payload=JSONObject(
                    table_id=F("table_id"),
                    row_id=F("row_id"),
                    field_id=F("field_id"),
                    query=Value(context.query),
                ),
            )
            .values(
                "search_type",
                "object_id",
                "sort_key",
                "rank",
                "priority",
                "title",
                "subtitle",
                "payload",
            )
        )

        return qs

    def _fetch_primary_field_values(
        self,
        rows_list: List[Dict],
        table_id_to_primary_field: Dict[int, Tuple[Table, Field]],
    ) -> Dict[Tuple[int, int], str]:
        """
        Fetch primary field values for all rows efficiently.
        Uses the same approach as link row fields - leverages get_model()
        and model.__str__() which already handles all field types properly.

        :param rows_list: List of row dicts from search results
        :param table_id_to_primary_field: Mapping of table IDs to their primary field
        :return: {(table_id, row_id): human_readable_value}
        """

        rows_by_table = defaultdict(list)
        for r in rows_list:
            payload = r.get("payload", {})
            table_id = payload.get("table_id")
            row_id = payload.get("row_id")
            rows_by_table[table_id].append(row_id)

        if not rows_by_table:
            return {}

        primary_values = {}

        for table_id, row_ids in rows_by_table.items():
            table, primary_field = table_id_to_primary_field.get(table_id)
            model = table.get_model(
                fields=[primary_field], field_ids=[], add_dependencies=False
            )
            rows_qs = (
                model.objects.only(primary_field.db_column)
                .filter(id__in=row_ids)
                .order_by()
            )
            field_type = field_type_registry.get_by_model(primary_field)
            rows_qs = field_type.enhance_queryset(
                rows_qs, primary_field, primary_field.db_column
            )

            for row in rows_qs:
                primary_values[(table_id, row.id)] = str(row)

        return primary_values

    def postprocess(self, rows: Iterable[Dict]) -> List[SearchResult]:
        """
        Return minimal row results with primary field values for better UX.
        """

        if not rows:
            return []

        rows_list = list(rows)
        if not rows_list:
            return []

        field_ids = sorted(
            {
                int(r.get("payload", {}).get("field_id"))
                for r in rows_list
                if r.get("payload", {}).get("field_id") is not None
            }
        )

        # Early return if no field IDs to process
        if not field_ids:
            return []

        fields_qs = (
            FieldHandler()
            .get_base_fields_queryset()
            .filter(id__in=field_ids)
            .annotate(
                primary_field_id=Subquery(
                    Field.objects.filter(
                        table_id=OuterRef("table_id"), primary=True
                    ).values("id")[:1]
                )
            )
        )

        field_id_to_name = {}
        field_id_to_table_id = {}
        table_id_to_name = {}
        table_id_to_database_id = {}
        database_id_to_name = {}
        database_id_to_workspace_id = {}
        table_id_to_primary_field = {}

        primary_field_ids = set()
        for f in fields_qs:
            primary_field_ids.add(f.primary_field_id)

        primary_fields = {
            f.id: f
            for f in specific_iterator(Field.objects.filter(id__in=primary_field_ids))
        }

        for f in fields_qs:
            field_id_to_name[f.id] = f.name
            field_id_to_table_id[f.id] = f.table_id
            table_id_to_name[f.table_id] = f.table.name
            table_id_to_database_id[f.table_id] = f.table.database_id
            database_id_to_name[f.table.database_id] = f.table.database.name
            database_id_to_workspace_id[
                f.table.database_id
            ] = f.table.database.workspace_id
            table_id_to_primary_field[f.table_id] = (
                f.table,
                primary_fields[f.primary_field_id],
            )

        # Fetch primary field values for all rows, reusing already-fetched tables
        primary_values = self._fetch_primary_field_values(
            rows_list, table_id_to_primary_field
        )

        results_list = []
        for r in rows_list:
            payload = r.get("payload", {})
            table_id = payload.get("table_id")
            row_id = payload.get("row_id")
            field_id = payload.get("field_id")

            if not all(x is not None for x in [table_id, row_id, field_id]):
                continue

            object_id = r.get("object_id")
            rank = r.get("rank")

            field_id_int = int(field_id)
            table_id_int = field_id_to_table_id.get(field_id_int) or int(table_id)
            database_id = table_id_to_database_id.get(table_id_int)
            database_name = database_id_to_name.get(database_id)
            workspace_id = database_id_to_workspace_id.get(database_id)
            table_name = table_id_to_name.get(table_id_int)
            field_name = field_id_to_name.get(field_id_int)

            parts = []
            if database_name:
                parts.append(database_name)
            if table_name:
                parts.append(table_name)
            subtitle_suffix = " / ".join(parts) if parts else None
            subtitle = f"Row in {subtitle_suffix}" if subtitle_suffix else None

            # Get primary field value or fallback to "Row #N"
            primary_value = primary_values.get((table_id_int, int(row_id)))
            title = primary_value if primary_value else f"Row #{row_id}"

            results_list.append(
                SearchResult(
                    type=self.type,
                    id=object_id,
                    title=title,
                    subtitle=subtitle,
                    description=None,
                    metadata={
                        "workspace_id": workspace_id,
                        "database_id": database_id,
                        "table_id": int(table_id),
                        "row_id": int(row_id),
                        "field_id": int(field_id),
                        "database_name": database_name,
                        "table_name": table_name,
                        "field_name": field_name,
                        "rank": rank,
                        "primary_field_value": primary_value,
                    },
                )
            )

        return results_list
