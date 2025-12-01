from typing import Annotated, Literal

from pydantic import Field

from baserow_enterprise.assistant.types import BaseModel

from .node import AnyNodeCreate, TriggerNodeCreate


class WorkflowEdgeCreate(BaseModel):
    """Workflow edge connecting two nodes."""

    type: Literal["edge"]
    from_node_label: str = Field(
        ...,
        description="The label of the node where the edge starts",
    )
    to_node_label: str = Field(
        ...,
        description="The label of the node where the edge ends",
    )


class WorkflowRouterEdgeCreate(WorkflowEdgeCreate):
    """Workflow edge connecting to a router node with a branch label."""

    type: Literal["router_branch"]
    router_branch_label: str = Field(
        default="",
        description="The branch label for the router node edge",
    )


AnyWorkflowEdgeCreate = Annotated[
    WorkflowEdgeCreate,
    WorkflowRouterEdgeCreate,
    Field(
        discriminator="type",
        default="edge",
        description=(
            "The type of workflow edge. Use 'edge' in normal linear (a follows b) connections. "
            "Use 'router_branch' when connecting to a router node with a branch label. "
        ),
    ),
]


class WorkflowCreate(BaseModel):
    """Base workflow model."""

    name: str = Field(..., description="The name of the workflow")
    trigger: TriggerNodeCreate = Field(
        ...,
        description="The trigger node configuration for the workflow",
    )
    nodes: list[AnyNodeCreate] = Field(
        default_factory=list,
        description=(
            "The nodes executed or evaluated once the trigger fires. "
            "Every node must have only one incoming edge. If the previous node is a router, "
            "the branch label must be specified for non-default branches. "
            "Only if explicitly requested, this list can be empty."
        ),
    )


class WorkflowItem(WorkflowCreate):
    """Existing workflow with ID."""

    id: int
    state: str = Field(
        ..., description="Workflow state: draft, live, paused, or disabled"
    )
