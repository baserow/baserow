from typing import Optional, List
from pydantic import BaseModel, Field

from baserow_enterprise.assistant.types import (
    BaseToolArgsSchema,
    AnyDataOperation,
)


class DataManagerToolArgsSchema(BaseToolArgsSchema):
    instructions: str = Field(
        description="The user's instructions for data operations (create, update, or delete rows)."
    )
    table_id: Optional[int] = Field(
        default=None,
        description=(
            "The ID of the table to operate on. If not provided, the tool will use "
            "the table from the current UI context if available, or ask for clarification."
        ),
    )


class DataManagerToolOutputSchema(BaseModel):
    question: Optional[str] = Field(
        default=None,
        description=(
            "An optional follow-up question for refining or clarifying the data operation. "
            "If the user's request is unclear (e.g., table not specified, ambiguous field names), "
            "this should contain a clarification question and needs_clarification should be set to true."
        ),
    )
    need_clarification: bool = Field(
        default=False,
        description="Whether a clarification is strictly needed before proceeding with the data operations.",
    )
    # data_operations_plan: List[AnyDataOperation] = Field(
    #     default_factory=list,
    #     description=(
    #         "The list of data operations to execute. "
    #         "Can include CreateRowsOperation, UpdateRowsOperation, or DeleteRowsOperation."
    #     ),
    # )
    markdown_description: str = Field(
        description="A markdown formatted description of the data operations to share with the user.",
    )


class GetDatabaseSchemaToolArgsSchema(BaseToolArgsSchema):
    database_id: Optional[int] = Field(
        default=None,
        description=(
            "The ID of the database to retrieve the schema for. If not provided, "
            "the tool will use the database from the current UI context if available, "
            "or ask for clarification."
        ),
    )
    relations_only: bool = Field(
        default=False,
        description=(
            "If true, only include tables and fields that are part of relationships. "
            "Useful for understanding table names and how they are linked together."
        ),
    )


class GetWorkspaceSchemaToolArgsSchema(BaseToolArgsSchema):
    pass
