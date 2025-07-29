import json
from typing import List, Dict, Any, Literal, Optional, Tuple, Annotated, Type
from uuid import uuid4
from pydantic import BaseModel, Field
from asgiref.sync import sync_to_async
from django.conf import settings

from baserow.contrib.database.models import Table
from baserow.contrib.database.rows.actions import (
    CreateRowsActionType,
    UpdateRowsActionType,
)
from baserow.core.mcp.utils import internal_api_request
from django.contrib.auth.models import AbstractUser
from baserow_enterprise.ai_assistant.tools.base import (
    EMPTY,
    BaserowBaseTool,
    BaserowToolError,
    create_row_model,
)
from django.db import transaction

from pydantic import BaseModel, Field


class DynamicRowToolFactory:
    """Factory for creating row manipulation tools based on table schema"""

    @classmethod
    async def update_rows_tool(
        cls,
        user: AbstractUser,
        table: Table,
    ) -> Type[BaserowBaseTool]:
        @sync_to_async
        def get_tool():
            model = table.get_model()

            RowModel = create_row_model(model, include_id=True)

            # Fetch example rows from the table
            example_rows = []
            try:
                rows = model.objects.all()[:3]  # Get first 3 rows as examples
                for row in rows:
                    example_row = {}
                    for field_object in model.get_field_objects():
                        field = field_object["field"]
                        field_type = field_object["type"]
                        value = field_type.serialize_to_input_value(
                            field, getattr(row, field.db_column)
                        )
                        example_row[field.db_column] = value

                    example_rows.append(example_row)
            except Exception:
                pass

            example_description = ""
            _json_schema_extra = {}
            if example_rows:
                example_description = f"Example existing rows: {example_rows}"
                _json_schema_extra = {"example": {"rows_values": example_rows}}

            # Create the input model with examples
            class RowsValuesInputWithExamples(BaseModel):
                rows_values: List[RowModel] = Field(
                    description=f"Data for the new rows. {example_description}"
                )

                class Config:
                    json_schema_extra = _json_schema_extra

            class UpdateRowsTool(BaserowBaseTool):
                name: str = f"update_table_rows"
                description: str = (
                    f"Update multiple rows in the current table {table.name} in a single operation. "
                    "When asked to add random data, base the new rows on the example rows if available."
                    "IMPORTANT: Always pass ALL rows you want to update in a single call as a list."
                )
                args_schema: type = RowsValuesInputWithExamples

                def _run_impl(
                    self,
                    rows_values,
                ) -> Tuple[str, Any]:
                    """Update existing rows in the specified table."""

                    # Fix: Create a list of dictionaries, one for each row
                    data = []
                    for row_values in rows_values:
                        row_data = {
                            k: v
                            for k, v in row_values.model_dump().items()
                            if v is not EMPTY
                        }
                        data.append(row_data)

                    try:
                        with transaction.atomic():
                            updated_rows = UpdateRowsActionType.do(
                                user, table, data, model=model
                            )

                        primary_field = model.get_primary_field()
                        cache = {}
                        content = f"{len(updated_rows)} rows updated successfully:\n\n"
                        content += f"| ID  | {primary_field.name}   |\n"
                        content += "|-----|------------------------|\n"
                        content += "\n".join(
                            f"| {row.id} | {primary_field.get_type().get_export_serialized_value(row, primary_field.db_column, cache)} |"
                            for row in updated_rows
                        )

                        return (
                            content,
                            {
                                "updated_rows": updated_rows,
                                "latest_action_is_undoable": True,
                            },
                        )
                    except Exception as e:
                        return (
                            "Error updating rows.",
                            BaserowToolError(status="error", error=str(e)),
                        )

            return UpdateRowsTool()

        return await get_tool()

    @classmethod
    async def create_rows_tool(
        cls,
        user: AbstractUser,
        table: Table,
    ) -> Type[BaserowBaseTool]:
        @sync_to_async
        def get_tool():
            model = table.get_model()

            RowModel = create_row_model(model)

            # Fetch example rows from the table
            example_rows = []
            try:
                rows = model.objects.all()[:3]  # Get first 3 rows as examples
                for row in rows:
                    example_row = {}
                    for field_object in model.get_field_objects():
                        field = field_object["field"]
                        field_type = field_object["type"]
                        value = field_type.serialize_to_input_value(
                            field, getattr(row, field.db_column)
                        )
                        example_row[field.db_column] = value

                    example_rows.append(example_row)
            except Exception:
                pass

            example_description = ""
            _json_schema_extra = {}
            if example_rows:
                example_description = f"Example existing rows: {example_rows}"
                _json_schema_extra = {"example": {"rows_values": example_rows}}

            # Create the input model with examples
            class RowsValuesInputWithExamples(BaseModel):
                rows_values: List[RowModel] = Field(
                    description=f"Data for the new rows. {example_description}"
                )

                class Config:
                    json_schema_extra = _json_schema_extra

            class CreateRowsTool(BaserowBaseTool):
                name: str = f"create_table_rows"
                description: str = (
                    f"Create multiple rows in the current table {table.name} in a single operation. "
                    "When asked to add random data, base the new rows on the example rows if available."
                    "IMPORTANT: Always pass ALL rows you want to create in a single call as a list."
                )
                args_schema: type = RowsValuesInputWithExamples

                def _run_impl(
                    self,
                    rows_values,
                ) -> Tuple[str, Any]:
                    """Create new rows in the specified table."""

                    # Fix: Create a list of dictionaries, one for each row
                    data = []
                    for row_values in rows_values:
                        row_data = {
                            k: v
                            for k, v in row_values.model_dump().items()
                            if v is not EMPTY
                        }
                        data.append(row_data)

                    try:
                        created_rows = CreateRowsActionType.do(
                            user, table, data, model=model
                        )

                        primary_field = model.get_primary_field()
                        cache = {}
                        content = f"{len(created_rows)} rows created successfully:\n\n"
                        content += f"| ID  | {primary_field.name}   |\n"
                        content += "|-----|------------------------|\n"
                        content += "\n".join(
                            f"| {row.id} | {primary_field.get_type().get_export_serialized_value(row, primary_field.db_column, cache)} |"
                            for row in created_rows
                        )

                        return (
                            content,
                            {
                                "created_rows": created_rows,
                                "latest_action_is_undoable": True,
                            },
                        )
                    except Exception as e:
                        return (
                            "Error creating rows.",
                            BaserowToolError(status="error", error=str(e)),
                        )

            return CreateRowsTool()

        return await get_tool()

    @classmethod
    async def list_rows_tool(
        cls,
        user: AbstractUser,
        table: Table,
    ) -> Type[BaserowBaseTool]:
        class ListRowsArgsSchema(BaseModel):
            search: Optional[str] = Field(
                default=None, description="Search term to filter rows."
            )
            page: int = Field(default=1, description="Page number for pagination.")
            size: int = Field(
                default=settings.ROW_PAGE_SIZE_LIMIT,
                le=settings.ROW_PAGE_SIZE_LIMIT,
                description="Number of rows per page.",
            )

        @sync_to_async
        def get_tool():
            class ListRowsTool(BaserowBaseTool):
                name: str = f"list_table_rows"
                description: str = (
                    f"List rows in the current table {table.name}. "
                    "You can filter the rows by providing a search term and paginate them with page and size."
                )
                args_schema: type = ListRowsArgsSchema

                def _run_impl(
                    self,
                    search: str = "",
                    page: int = 1,
                    size: int = settings.ROW_PAGE_SIZE_LIMIT,
                ) -> Tuple[str, Any]:
                    rsp = internal_api_request(
                        "api:database:rows:list",
                        path_params={"table_id": table.id},
                        user=user,
                        query_params={
                            "user_field_names": "true",
                            "search": search,
                            "page": page,
                            "size": size,
                        },
                    ).json()

                    results = rsp["results"]
                    content = f"Found {rsp['count']} in total. \n"
                    if rsp["next"]:
                        content += (
                            f"There are more results available at {rsp['next']}\n\n"
                        )
                    content += f"Results from page {page} with size {size}: {json.dumps(results)}\n"
                    return content, results

            return ListRowsTool()

        return await get_tool()
