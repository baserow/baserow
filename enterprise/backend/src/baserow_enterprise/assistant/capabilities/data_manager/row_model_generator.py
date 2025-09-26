"""
Dynamic Pydantic model generator for Baserow table rows.
Creates validation models based on TableSchema definitions.
"""

import re
from typing import Any, List, Literal, Optional, Type, Union
from datetime import date, datetime
from django.db.models import Q
from pydantic import BaseModel, ConfigDict, Field, create_model

from baserow.contrib.database.table.models import GeneratedTableModel
from baserow_enterprise.assistant.types import (
    TableSchema,
    AnyFieldType,
    TextFieldType,
    LongTextFieldType,
    EmailFieldType,
    URLFieldType,
    NumberFieldType,
    RatingFieldType,
    DateFieldType,
    BooleanFieldType,
    SingleSelectFieldType,
    MultipleSelectFieldType,
    MultipleCollaboratorsFieldType,
    LinkRowFieldType,
    FileFieldType,
    CreateRowsOperation,
    UpdateRowsOperation,
    DeleteRowsOperation,
)


def get_field_python_type(
    field: AnyFieldType,
    relations: dict[str, GeneratedTableModel] = {},
) -> tuple[type, Any]:
    """
    Map a Baserow field type to Python type and field definition.

    Returns a tuple of (python_type, field_definition) for use with Pydantic.
    """

    if isinstance(field, TextFieldType):
        return str, Field(description=f"Text field: {field.name}", title=field.name)

    elif isinstance(field, LongTextFieldType):
        return str, Field(
            description=f"Long text field: {field.name}", title=field.name
        )

    elif isinstance(field, EmailFieldType):
        return Optional[str], Field(
            description=f"Email field: {field.name}", title=field.name
        )

    elif isinstance(field, URLFieldType):
        return Optional[str], Field(
            description=f"URL field: {field.name}", title=field.name
        )

    elif isinstance(field, NumberFieldType):
        return Union[int, float, None], Field(
            description=f"Number field: {field.name}", title=field.name
        )

    elif isinstance(field, RatingFieldType):
        max_rating = getattr(field, "max_rating", 5)
        return Optional[int], Field(
            description=f"Rating field (0-{max_rating}): {field.name}", title=field.name
        )

    elif isinstance(field, DateFieldType):
        if getattr(field, "include_time", False):
            return Optional[str], Field(
                description=f"ISO 8601 date-time string: {field.name}", title=field.name
            )
        else:
            return Optional[str], Field(
                description=f"ISO 8601 date string: {field.name}", title=field.name
            )

    elif isinstance(field, BooleanFieldType):
        return bool, Field(description=f"Boolean field: {field.name}", title=field.name)

    elif isinstance(field, SingleSelectFieldType):
        # For single select, just use Optional[str] with validation
        # Enums cause issues with validators in dynamic models
        options = field.options
        option_values = [opt.value if hasattr(opt, "value") else opt for opt in options]
        OptionEnum = Literal[*tuple(option_values)]
        return Optional[OptionEnum], Field(
            description=f"Single select from. Must be one of {option_values}",
            title=field.name,
        )

    elif isinstance(field, MultipleSelectFieldType):
        options = field.options
        option_values = [opt.value if hasattr(opt, "value") else opt for opt in options]
        OptionEnum = Literal[*tuple(option_values)]
        return List[OptionEnum], Field(
            description=f"Multiple select from: {option_values}",
            title=field.name,
        )

    elif isinstance(field, MultipleCollaboratorsFieldType):
        return List[int], Field(
            description=f"List of user IDs: {field.name}", title=field.name
        )

    elif isinstance(field, LinkRowFieldType):
        if field.name in relations:
            related_primary_field, related_model = relations[field.name]
            column = related_primary_field.db_column
            values = list(
                related_model.objects.filter(
                    Q(**{f"{column}__isnull": False}), ~Q(**{f"{column}": ""})
                ).values_list(column, flat=True)[:20]
            )

            if not values:
                return None, None  # No existing values to reference

            CustomEnum = Literal[*tuple(values)]

            return List[CustomEnum], Field(
                description=f"List of one of values from table {field.linked_table_name}",
                title=field.name,
            )
        else:
            return List[str], Field(description=f"An empty list", title=field.name)

    elif isinstance(field, FileFieldType):
        # TODO
        return None, None

    # Default fallback for unknown types
    else:
        return None, None


def create_validator_for_select_field(field_name: str, options: List[str]):
    """
    Create a validator function for select fields to ensure values are valid options.
    """

    def validate_select_options(v):
        if v is None:
            return v  # Allow None for optional fields

        if isinstance(v, list):
            # Multiple select
            invalid = [item for item in v if item not in options]
            if invalid:
                raise ValueError(
                    f"Invalid options for {field_name}: {invalid}. "
                    f"Must be from: {options}"
                )
        elif v is not None and v not in options:
            # Single select - handle both string and enum values
            value_to_check = v.value if hasattr(v, "value") else v
            if value_to_check not in options:
                raise ValueError(
                    f"Invalid option for {field_name}: {value_to_check}. "
                    f"Must be one of: {options}"
                )
        return v

    # Return the validator function with the field name
    validate_select_options.__qualname__ = f"validate_{field_name}"
    return validate_select_options


def create_row_model_from_schema(
    table_schema: TableSchema,
    model_name: Optional[str] = None,
    relations: dict[str, GeneratedTableModel] = {},
) -> Type[BaseModel]:
    """
    Create a dynamic Pydantic model from a TableSchema.

    Args:
        table_schema: The table schema to create a model from
        model_name: Optional name for the model (defaults to "{table_name}Row")

    Returns:
        A Pydantic model class for validating row data
    """

    # Generate model name if not provided
    if model_name is None:
        model_name = f"Table{table_schema.id}Row"

    # Make sure name is compliant with json schema (alphanumeric, _, -)
    model_name = re.sub(r"[^a-zA-Z0-9_-]", "", model_name)

    # Build field definitions
    field_definitions = {}

    # Add primary field
    primary_type, primary_def = get_field_python_type(table_schema.primary_field)
    field_definitions[table_schema.primary_field.name] = (primary_type, primary_def)

    # Add other fields
    date_fields = []
    for field in table_schema.fields:
        field_type, field_def = get_field_python_type(field, relations=relations)
        if field_type is None:
            continue  # Skip unsupported field types
        elif field.type == "date":
            date_fields.append(field)  # Remember first date field for sorting

        field_definitions[field.name] = (field_type, field_def)

    # examples = []
    # for date_field in date_fields or []:
    #     examples.append(
    #         {
    #             date_field.name: datetime.now().isoformat()
    #             if date_field.include_time
    #             else date.today().isoformat()
    #         }
    #     )

    # json_schema_extra = {}
    # if examples:
    #     json_schema_extra["examples"] = examples

    # Create the base model first
    DynamicRowModel = create_model(
        model_name,
        **field_definitions,
        __module__=__name__,
        __config__=ConfigDict(
            extra="forbid",
            #
            # str_to_date=True,
            # json_schema_extra=json_schema_extra,
        ),
    )

    return DynamicRowModel


def create_dynamic_operations_from_schema(
    table_schema: TableSchema,
    relations: dict[str, GeneratedTableModel] = {},
) -> tuple[Type[BaseModel], Type[BaseModel], Type[BaseModel]]:
    """
    Create dynamic operation classes that use the generated row model.

    Returns:
        Tuple of (DynamicCreateRowsOperation, DynamicUpdateRowsOperation, DynamicDeleteRowsOperation)
    """

    # Create the row model for this table
    RowModel = create_row_model_from_schema(table_schema, relations=relations)

    table_name = table_schema.name.replace(" ", "")

    # Create dynamic CreateRowsOperation
    DynamicCreateRowsOperation = create_model(
        f"Dynamic{table_name}CreateRowsOperation",
        __base__=CreateRowsOperation,
        rows_values=(
            List[RowModel],
            Field(description=f"List of {table_name} rows to create"),
        ),
        __module__=__name__,
        __config__=ConfigDict(
            extra="forbid",
        ),
    )

    # Create dynamic UpdateRowsOperation
    DynamicUpdateRowsOperation = create_model(
        f"Dynamic{table_name}UpdateRowsOperation",
        __base__=UpdateRowsOperation,
        rows_values=(
            List[RowModel],
            Field(description=f"List of {table_name} row updates"),
        ),
        __module__=__name__,
        __config__=ConfigDict(
            extra="forbid",
        ),
    )

    # DeleteRowsOperation doesn't need data, so we can reuse the base class
    DynamicDeleteRowsOperation = create_model(
        f"Dynamic{table_name}DeleteRowsOperation",
        __base__=DeleteRowsOperation,
        __module__=__name__,
        __config__=ConfigDict(
            extra="forbid",
        ),
    )

    return (
        DynamicCreateRowsOperation,
        DynamicUpdateRowsOperation,
        DynamicDeleteRowsOperation,
    )


def create_dynamic_tool_output_schema(
    table_schema: TableSchema,
    relations: dict[str, GeneratedTableModel] = {},
) -> Type[BaseModel]:
    """
    Create a dynamic DataManagerToolOutputSchema that includes the table-specific operations.

    Args:
        table_schema: The table schema to create operations for

    Returns:
        A dynamic output schema class with typed operations
    """

    # Get the dynamic operation classes
    (
        DynamicCreateRowsOp,
        DynamicUpdateRowsOp,
        DynamicDeleteRowsOp,
    ) = create_dynamic_operations_from_schema(table_schema, relations=relations)

    table_name = table_schema.name.replace(" ", "")

    # Create union of all possible operations for this table
    DynamicDataOperation = Union[
        DynamicCreateRowsOp, DynamicUpdateRowsOp, DynamicDeleteRowsOp
    ]

    # Create the dynamic output schema
    DynamicToolOutputSchema = create_model(
        f"Dynamic{table_name}ManagerToolOutputSchema",
        data_operations_plan=(
            List[DynamicCreateRowsOp],
            Field(
                default_factory=list,
                description=(
                    f"The list of data operations to execute on {table_name} table. "
                    f"Can include create, update, or delete operations with properly typed data."
                ),
            ),
        ),
        __config__=ConfigDict(
            extra="forbid",
        ),
    )

    return DynamicToolOutputSchema


def get_dynamic_components_for_table(
    table_schema: TableSchema,
    relations: dict[str, GeneratedTableModel] = {},
) -> dict:
    """
    Get all dynamic components needed for a table's data operations.

    Returns:
        Dictionary containing:
        - row_model: The Pydantic model for full rows
        - partial_row_model: The Pydantic model for partial row updates
        - create_operation: The dynamic CreateRowsOperation class
        - update_operation: The dynamic UpdateRowsOperation class
        - delete_operation: The dynamic DeleteRowsOperation class
        - output_schema: The dynamic DataManagerToolOutputSchema class
    """

    # Create all components
    row_model = create_row_model_from_schema(table_schema, relations=relations)

    create_op, update_op, delete_op = create_dynamic_operations_from_schema(
        table_schema, relations=relations
    )
    output_schema = create_dynamic_tool_output_schema(table_schema, relations=relations)

    return {
        "row_model": row_model,
        "create_operation": create_op,
        "update_operation": update_op,
        "delete_operation": delete_op,
        "output_schema": output_schema,
    }
