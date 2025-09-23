from typing import Annotated, List, NamedTuple, Optional, Literal, Sequence
from pydantic import BaseModel, Field
from operator import add

from baserow_enterprise.assistant.types import BaseToolArgsSchema, AnySchemaOperation


class DatabaseArchitectToolArgsSchema(BaseToolArgsSchema):
    instructions: str = Field(
        description="The user's instructions for the database schema design."
    )


class DatabaseArchitectToolOutputSchema(BaseModel):
    question: str = Field(
        description=(
            "An optional follow-up question for refining or clarifying the current plan. "
            "If the user's request is unclear, this should contain a clarification question and "
            "needs_clarification should be set to true. "
            "If the request is already clear, use it to suggest iterative improvements to the plan."
        ),
    )
    need_clarification: bool = Field(
        default=False,
        description="Whether a clarification is strictly needed before proceeding.",
    )
    schema_operations_plan: list[AnySchemaOperation] = Field(
        description="The list of operations needed to transform the starting schema into the final schema.",
    )
    new_database_name: Optional[str] = Field(
        default=None,
        description=(
            "If a new database needs to be created, the name of the new database. "
            "Otherwise, null."
        ),
    )
    markdown_description: str = Field(
        description="A markdown formatted super-concise description of the plan to share with the user.",
    )
