from itertools import groupby
from typing import List
from django.db.models import Q
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.models import Database
from baserow.contrib.database.table.models import Table

from baserow.contrib.database.fields.registries import field_type_registry
from baserow.core.db import specific_iterator
from baserow.core.models import Workspace
from baserow_enterprise.assistant.types import (
    BaseDatabaseSchema,
    WorkspaceSchema,
    field_registry,
    DatabaseSchema,
    TableSchema,
)


def _get_table_schema(table_fields: List[Field]) -> TableSchema:
    field_type = lambda f: field_registry.get(
        field_type_registry.get_for_class(f.specific_class).type
    )
    table_fields = list(table_fields)
    primary_field = table_fields[0]
    table_schema = TableSchema(
        id=primary_field.table_id,
        name=primary_field.table.name,
        primary_field=field_type(primary_field).from_orm(primary_field),
    )
    for field in table_fields[1:]:
        f = field_type(field)
        if not f:
            continue
        field_schema = f.from_orm(field)
        if field_schema.type == "link_row":
            table_schema.relationships.append(field_schema.linked_table_name)
        table_schema.fields.append(field_schema)
    return table_schema


def get_table_schema(table: Table) -> TableSchema:
    base_field_queryset = FieldHandler().get_base_fields_queryset()
    fields = specific_iterator(
        base_field_queryset.filter(table=table).order_by("-primary", "order", "id"),
        per_content_type_queryset_hook=(
            lambda model, queryset: field_type_registry.get_by_model(
                model
            ).enhance_field_queryset(queryset, model)
        ),
    )
    return _get_table_schema(fields)


def get_database_schema(
    database: Database, relations_only: bool = False
) -> DatabaseSchema:
    """
    Returns the schema of the given database.
    """

    base_field_queryset = FieldHandler().get_base_fields_queryset()
    if relations_only:
        base_field_queryset = base_field_queryset.filter(
            Q(primary=True) | Q(linkrowfield__isnull=False)
        )
    fields = specific_iterator(
        base_field_queryset.filter(table__database_id=database.id).order_by(
            "table_id", "-primary", "order", "id"
        ),
        per_content_type_queryset_hook=(
            lambda model, queryset: field_type_registry.get_by_model(
                model
            ).enhance_field_queryset(queryset, model)
        ),
    )

    tables = {}
    for _, _table_fields in groupby(fields, lambda f: f.table):
        table_schema = _get_table_schema(list(_table_fields))
        tables[table_schema.name] = table_schema

    return DatabaseSchema(id=database.id, name=database.name, tables=tables)


def get_workspace_schema(workspace: Workspace) -> WorkspaceSchema:
    """
    Returns the schema of the given workspace.
    """

    database = [
        BaseDatabaseSchema(**db)
        for db in Database.objects.filter(workspace=workspace).values("id", "name")
    ]
    return WorkspaceSchema(id=workspace.id, name=workspace.name, databases=database)
