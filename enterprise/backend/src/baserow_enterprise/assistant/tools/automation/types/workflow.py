from pydantic import Field

from baserow_enterprise.assistant.types import BaseModel

from .node import ActionNodeCreate, TriggerNodeCreate


class WorkflowCreate(BaseModel):
    """Base workflow model."""

    name: str = Field(..., description="Workflow name.")
    trigger: TriggerNodeCreate = Field(..., description="The trigger node.")
    nodes: list[ActionNodeCreate] = Field(
        default_factory=list,
        description="Action nodes executed after the trigger. Each node has one previous_node_ref.",
    )


class WorkflowItem(WorkflowCreate):
    """Existing workflow with ID."""

    id: int
    state: str = Field(
        ..., description="Workflow state: draft, live, paused, or disabled"
    )
