from typing import List, Literal
from pydantic import BaseModel, Field

from baserow_enterprise.assistant.types import BaseToolArgsSchema, TaskPlan


class TaskPlannerToolArgsSchema(BaseToolArgsSchema):
    instructions: str = Field(
        description="The user's complex request that needs to be broken down into tasks"
    )


class TaskPlannerToolOutputSchema(BaseModel):
    needs_planning: bool = Field(
        description="Whether this request needs task planning (true for multi-step operations)"
    )
    task_plan: List[TaskPlan] = Field(
        default_factory=list, description="List of tasks to execute in sequence"
    )
    summary: str = Field(description="Brief summary of what the plan will accomplish")
