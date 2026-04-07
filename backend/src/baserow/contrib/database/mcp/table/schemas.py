from __future__ import annotations

from pydantic import BaseModel, Field

from baserow.contrib.database.mcp.fields.schemas import FieldSpec


class ListDatabasesInput(BaseModel):
    pass


class CreateDatabaseInput(BaseModel):
    name: str = Field(..., description="The name of the database to create.")


class ListTablesInput(BaseModel):
    database_id: int | None = Field(
        None, description="If provided, only return tables from this database."
    )


class CreateTableInput(BaseModel):
    database_id: int = Field(
        ..., description="The ID of the database to create the table in."
    )
    name: str = Field(..., description="The name of the table.")
    fields: list[FieldSpec] | None = Field(
        None,
        description=(
            "Optional list of additional fields. Each item must have "
            "'name' and 'type'. Type-specific extras: "
            "number_decimal_places (number), date_include_time (date), "
            "select_options=[{value, color}] "
            "(single_select/multiple_select), "
            "link_row_table_id (link_row). "
            "Valid types: text, long_text, number, boolean, date, "
            "single_select, multiple_select, link_row, file, email, "
            "url, phone_number, rating, formula, lookup."
        ),
    )


class UpdateTableInput(BaseModel):
    table_id: int = Field(..., description="The ID of the table to rename.")
    name: str = Field(..., description="The new name for the table.")


class DeleteTableInput(BaseModel):
    table_id: int = Field(..., description="The ID of the table to delete.")


class GetTableSchemaInput(BaseModel):
    table_ids: list[int] = Field(
        ..., description="List of table IDs to get the schema for."
    )
