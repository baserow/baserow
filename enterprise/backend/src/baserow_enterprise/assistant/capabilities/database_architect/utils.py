from typing import Dict, List, Set, Tuple
from pydantic import BaseModel
from .types import (
    CreateFieldOperation,
    DeleteTableOperation,
    TableSchema,
    AnyFieldType,
    LinkRowFieldType,
    CreateTableOperation,
    DatabaseSchema,
    ExecutionPlan,
)


def create_execution_plan(
    current_schema: DatabaseSchema, final_schema: DatabaseSchema
) -> ExecutionPlan:
    """
    Create an execution plan to transform current_schema into final_schema.

    The plan will be ordered to handle dependencies:
    1. Create new tables (before any fields can reference them)
    2. Delete tables that no longer exist
    3. Update existing tables
    4. Delete fields that no longer exist
    5. Update existing fields
    6. Create new fields (after all tables exist for link fields)
    """
    operations = []

    # Build lookup dictionaries
    starting_tables = {t.name: t for t in current_schema.tables}
    final_tables = {t.name: t for t in final_schema.tables}

    starting_table_names = set(starting_tables.keys())
    final_table_names = set(final_tables.keys())

    # 1. Create new tables (just the table, not fields yet)
    tables_to_create = final_table_names - starting_table_names
    for table_name in tables_to_create:
        operations.append(CreateTableOperation(name=table_name))

    # # 2. Delete tables that no longer exist
    # tables_to_delete = starting_table_names - final_table_names
    # for table_name in tables_to_delete:
    #     operations.append(DeleteTableOperation(table_id=...))

    # 3. Process field changes for existing tables and new tables
    for table_name in final_table_names:
        final_table = final_tables[table_name]

        if table_name in starting_tables:
            # Existing table - compare fields
            starting_table = starting_tables[table_name]
            _process_field_changes(operations, table_name, starting_table, final_table)
        else:
            # New table - add all fields
            _add_all_fields(operations, table_name, final_table)

    # 4. Order operations to handle dependencies
    operations = _order_operations(operations, final_tables)

    return ExecutionPlan(operations=operations)


def _process_field_changes(
    operations: List,
    table_name: str,
    starting_table: TableSchema,
    final_table: TableSchema,
) -> None:
    """Process field changes for an existing table."""

    # Build field lookups by name
    starting_fields = {f.name: f for f in starting_table.fields}
    final_fields = {f.name: f for f in final_table.fields}

    starting_field_names = set(starting_fields.keys())
    final_field_names = set(final_fields.keys())

    # Check primary field changes
    if starting_table.primary_field.name != final_table.primary_field.name:
        # Primary field changed - this is a special case
        # You might want to handle this differently
        operations.append(
            CreateFieldOperation(table_name=table_name, field=final_table.primary_field)
        )

    # Delete fields that no longer exist
    # fields_to_delete = starting_field_names - final_field_names
    # Note: You'd need field_id for DeleteFieldOperation
    # for field_name in fields_to_delete:
    #     operations.append(DeleteFieldOperation(field_id=...))

    # Update existing fields that changed
    common_fields = starting_field_names & final_field_names
    for field_name in common_fields:
        starting_field = starting_fields[field_name]
        final_field = final_fields[field_name]

        if not _fields_are_equal(starting_field, final_field):
            # Note: You'd need field_id for UpdateFieldOperation
            # operations.append(
            #     UpdateFieldOperation(field_id=..., to_field=final_field)
            # )
            # For now, we'll recreate the field
            operations.append(
                CreateFieldOperation(table_name=table_name, field=final_field)
            )

    # Create new fields
    fields_to_create = final_field_names - starting_field_names
    for field_name in fields_to_create:
        operations.append(
            CreateFieldOperation(table_name=table_name, field=final_fields[field_name])
        )


def _add_all_fields(operations: List, table_name: str, table: TableSchema) -> None:
    """Add all fields for a new table."""

    # Add primary field first
    operations.append(
        CreateFieldOperation(table_name=table_name, field=table.primary_field)
    )

    # Add other fields
    for field in table.fields:
        operations.append(CreateFieldOperation(table_name=table_name, field=field))


def _fields_are_equal(field1: AnyFieldType, field2: AnyFieldType) -> bool:
    """Check if two fields are equal."""
    # Compare field definitions
    # You might want to customize this based on what changes you consider significant
    return field1.model_dump() == field2.model_dump()


def _order_operations(operations: List, final_tables: Dict[str, TableSchema]) -> List:
    """
    Order operations to handle dependencies.

    1. Create all tables first
    2. Create non-link fields
    3. Create link fields (ensures linked tables exist)
    """

    create_tables = []
    create_non_link_fields = []
    create_link_fields = []
    other_ops = []

    for op in operations:
        if isinstance(op, CreateTableOperation):
            create_tables.append(op)
        elif isinstance(op, CreateFieldOperation):
            if isinstance(op.field, LinkRowFieldType):
                create_link_fields.append(op)
            else:
                create_non_link_fields.append(op)
        else:
            other_ops.append(op)

    # Further sort link fields by dependency
    create_link_fields = _sort_link_fields_by_dependency(
        create_link_fields, final_tables
    )

    return create_tables + create_non_link_fields + create_link_fields + other_ops


def _sort_link_fields_by_dependency(
    link_operations: List[CreateFieldOperation], final_tables: Dict[str, TableSchema]
) -> List[CreateFieldOperation]:
    """
    Sort link field operations to ensure linked tables are created first.

    This handles cases where tables have circular references.
    """

    # Build dependency graph
    dependencies = {}
    for op in link_operations:
        if isinstance(op.field, LinkRowFieldType):
            source_table = op.table_name
            target_table = op.field.linked_table_name

            if source_table not in dependencies:
                dependencies[source_table] = set()
            dependencies[source_table].add(target_table)

    # Topological sort (simple version - may need cycle detection for complex cases)
    sorted_ops = []
    visited = set()

    def visit(table_name: str):
        if table_name in visited:
            return
        visited.add(table_name)

        # Visit dependencies first
        if table_name in dependencies:
            for dep in dependencies[table_name]:
                visit(dep)

        # Add operations for this table
        for op in link_operations:
            if op.table_name == table_name and op not in sorted_ops:
                sorted_ops.append(op)

    # Visit all tables mentioned in operations
    for op in link_operations:
        visit(op.table_name)

    return sorted_ops
