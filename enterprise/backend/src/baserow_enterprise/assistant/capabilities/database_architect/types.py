from typing import Annotated, List, NamedTuple, Optional, Literal, Sequence
from pydantic import BaseModel, ConfigDict, Field
from operator import add

from baserow_enterprise.assistant.types import BaseToolArgsSchema, AnySchemaOperation


class DatabaseArchitectToolArgsSchema(BaseToolArgsSchema):
    model_config = ConfigDict(
        extra="forbid",
    )
    instructions: str = Field(
        description="The user's instructions for the database schema design."
    )
    database_id: Optional[int] = Field(
        description="The ID of the existing database to modify. If not provided, a new database will be created."
    )
    new_database_name: Optional[str] = Field(
        description="The name for the new database if creating one. Required if database_id is not provided."
    )


class DatabaseArchitectToolOutputSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    question: str = Field(
        description=(
            "An optional follow-up question for refining or clarifying the current plan. "
        ),
    )
    schema_operations_plan: list[AnySchemaOperation] = Field(
        description="The list of operations needed to transform the starting schema into the final schema.",
    )
    markdown_description: str = Field(
        description="A markdown formatted super-concise description of the plan to share with the user.",
    )
