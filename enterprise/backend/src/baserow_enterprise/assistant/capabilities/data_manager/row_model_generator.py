"""
Dynamic Pydantic model generator for Baserow table rows.
Creates validation models based on TableSchema definitions.
"""

from enum import Enum, StrEnum
from typing import Any, List, Optional, Type, Union
from datetime import date, datetime
from django.db.models import Q
from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator

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


def create_select_field_model(field_name: str, options: list[str]) -> Type[StrEnum]:
    """Create a dynamic enum for use in Pydantic models"""
    enum_name = f"{field_name.title()}Enum"
    return StrEnum(
        enum_name,
        {opt.replace(" ", "_").upper(): opt for opt in options if isinstance(opt, str)},
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
        return str, Field(description=f"Text field: {field.name}")

    elif isinstance(field, LongTextFieldType):
        return str, Field(description=f"Long text field: {field.name}")

    elif isinstance(field, EmailFieldType):
        return Optional[str], Field(description=f"Email field: {field.name}")

    elif isinstance(field, URLFieldType):
        return Optional[str], Field(description=f"URL field: {field.name}")

    elif isinstance(field, NumberFieldType):
        return Union[int, float, None], Field(description=f"Number field: {field.name}")

    elif isinstance(field, RatingFieldType):
        max_rating = getattr(field, "max_rating", 5)
        return Optional[int], Field(
            description=f"Rating field (0-{max_rating}): {field.name}"
        )

    elif isinstance(field, DateFieldType):
        if getattr(field, "include_time", False):
            return Optional[datetime], Field(
                description=f"DateTime field: {field.name}"
            )
        else:
            return Optional[date], Field(description=f"Date field: {field.name}")

    elif isinstance(field, BooleanFieldType):
        return Optional[bool], Field(description=f"Boolean field: {field.name}")

    elif isinstance(field, SingleSelectFieldType):
        # For single select, just use Optional[str] with validation
        # Enums cause issues with validators in dynamic models
        options = field.options
        option_values = ", ".join(
            opt.value if hasattr(opt, "value") else opt for opt in options
        )
        return Optional[str], Field(
            description=f"Single select from. Must be one of {option_values}",
        )

    elif isinstance(field, MultipleSelectFieldType):
        options = field.options
        option_values = ", ".join(
            opt.value if hasattr(opt, "value") else opt for opt in options
        )
        return List[str], Field(
            description=f"Multiple select from: {option_values}",
        )

    elif isinstance(field, MultipleCollaboratorsFieldType):
        return List[int], Field(description=f"List of user IDs: {field.name}")

    elif isinstance(field, LinkRowFieldType):
        if field.name in relations:
            related_primary_field, related_model = relations[field.name]
            column = related_primary_field.db_column
            values = list(
                related_model.objects.filter(
                    Q(**{f"{column}__isnull": False}), ~Q(**{f"{column}": ""})
                ).values_list(column, flat=True)[:20]
            )

            CustomEnum = create_select_field_model(field.name, values)

            if field.multiple:
                description = (
                    f"List of one of values from table {field.linked_table_name}"
                )
            else:
                description = (
                    f"One of these values from table {field.linked_table_name}"
                )

            return List[CustomEnum], Field(description=description)
        else:
            return List[str], Field(description=f"An empty list")

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
    include_validators: bool = True,
    relations: dict[str, GeneratedTableModel] = {},
) -> Type[BaseModel]:
    """
    Create a dynamic Pydantic model from a TableSchema.

    Args:
        table_schema: The table schema to create a model from
        model_name: Optional name for the model (defaults to "{table_name}Row")
        include_validators: Whether to include field validators

    Returns:
        A Pydantic model class for validating row data
    """

    # Generate model name if not provided
    if model_name is None:
        model_name = f"{table_schema.name.replace(' ', '')}Row"

    # Build field definitions
    field_definitions = {}

    # Add primary field
    primary_type, primary_def = get_field_python_type(table_schema.primary_field)
    field_definitions[table_schema.primary_field.name] = (primary_type, primary_def)

    # Add other fields
    for field in table_schema.fields:
        field_type, field_def = get_field_python_type(field, relations=relations)
        if field_type is None:
            continue  # Skip unsupported field types

        field_definitions[field.name] = (field_type, field_def)

    # Create the base model first
    DynamicRowModel = create_model(
        model_name,
        **field_definitions,
        __module__=__name__,
        __config__=ConfigDict(
            extra="forbid",
        ),
    )

    # Add validators if needed
    if include_validators:
        validator_methods = {}

        # Check primary field for select validation
        if isinstance(
            table_schema.primary_field, (SingleSelectFieldType, MultipleSelectFieldType)
        ):
            options = getattr(table_schema.primary_field, "options", [])
            if options:
                option_values = [
                    opt.value if hasattr(opt, "value") else opt for opt in options
                ]
                validator_func = create_validator_for_select_field(
                    table_schema.primary_field.name, option_values
                )
                validator_methods[
                    f"validate_{table_schema.primary_field.name}"
                ] = field_validator(table_schema.primary_field.name)(validator_func)

        # Add validators for other select fields
        for field in table_schema.fields:
            if isinstance(field, (SingleSelectFieldType, MultipleSelectFieldType)):
                options = getattr(field, "options", [])
                if options:
                    option_values = [
                        opt.value if hasattr(opt, "value") else opt for opt in options
                    ]
                    validator_func = create_validator_for_select_field(
                        field.name, option_values
                    )
                    validator_methods[f"validate_{field.name}"] = field_validator(
                        field.name
                    )(validator_func)

        # If we have validators, create a new model class that includes them
        if validator_methods:
            DynamicRowModel = type(model_name, (DynamicRowModel,), validator_methods)

    return DynamicRowModel


def create_dynamic_operations_from_schema(
    table_schema: TableSchema,
) -> tuple[Type[BaseModel], Type[BaseModel], Type[BaseModel]]:
    """
    Create dynamic operation classes that use the generated row model.

    Returns:
        Tuple of (DynamicCreateRowsOperation, DynamicUpdateRowsOperation, DynamicDeleteRowsOperation)
    """

    # Create the row model for this table
    RowModel = create_row_model_from_schema(table_schema, include_validators=True)

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
    )

    # DeleteRowsOperation doesn't need data, so we can reuse the base class
    DynamicDeleteRowsOperation = create_model(
        f"Dynamic{table_name}DeleteRowsOperation",
        __base__=DeleteRowsOperation,
        __module__=__name__,
    )

    return (
        DynamicCreateRowsOperation,
        DynamicUpdateRowsOperation,
        DynamicDeleteRowsOperation,
    )


def create_dynamic_tool_output_schema(
    table_schema: TableSchema,
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
    ) = create_dynamic_operations_from_schema(table_schema)

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
    row_model = create_row_model_from_schema(
        table_schema, include_validators=True, relations=relations
    )

    create_op, update_op, delete_op = create_dynamic_operations_from_schema(
        table_schema
    )
    output_schema = create_dynamic_tool_output_schema(table_schema)

    return {
        "row_model": row_model,
        "create_operation": create_op,
        "update_operation": update_op,
        "delete_operation": delete_op,
        "output_schema": output_schema,
    }


# Usage example:
"""
from baserow_enterprise.assistant.types import TableSchema, TextFieldType, NumberFieldType, SingleSelectFieldType

# Example schema
table_schema = TableSchema(
    name="Products",
    primary_field=TextFieldType(name="name", type="text"),
    fields=[
        NumberFieldType(name="price", type="number"),
        SingleSelectFieldType(
            name="category",
            type="single_select",
            options=[{"value": "Electronics"}, {"value": "Clothing"}]
        )
    ]
)

# Method 1: Create individual components
ProductRow = create_row_model_from_schema(table_schema)
DynamicCreateOp, DynamicUpdateOp, DynamicDeleteOp = create_dynamic_operations_from_schema(table_schema)
DynamicOutputSchema = create_dynamic_tool_output_schema(table_schema)

# Method 2: Get all components at once
components = get_dynamic_components_for_table(table_schema)
ProductRow = components['row_model']
DynamicOutputSchema = components['output_schema']

# Now you can use the LLM with the dynamic schema
model = model.with_structured_output(DynamicOutputSchema)

# Example usage of the row model
try:
    product = ProductRow(
        name="iPhone",
        price=999.99,
        category="Electronics"
    )
    validated_data = product.model_dump()
except ValidationError as e:
    print(f"Validation error: {e}")

# Example LLM output structure
llm_response = DynamicOutputSchema(
    question=None,
    need_clarification=False,
    data_operations_plan=[
        DynamicCreateOp(
            type="create_rows",
            table_name="Products",
            data=[
                ProductRow(name="iPhone 15", price=999.99, category="Electronics"),
                ProductRow(name="MacBook Pro", price=1999.99, category="Electronics")
            ]
        )
    ],
    markdown_description="Creating 2 new products in the Products table."
)
"""
