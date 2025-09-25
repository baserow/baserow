from typing import List, Literal
from pydantic import BaseModel, Field, ConfigDict

from baserow_enterprise.assistant.types import BaseToolArgsSchema, TaskPlan


class TaskPlannerToolArgsSchema(BaseToolArgsSchema):
    model_config = ConfigDict(
        extra="forbid",
    )

    instructions: str = Field(
        description="The user's complex request that needs to be broken down into tasks"
    )


class TaskPlannerToolOutputSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    task_plan: List[TaskPlan] = Field(
        description="List of tasks to execute in sequence"
    )
    summary: str = Field(description="Brief summary of what the plan will accomplish")
