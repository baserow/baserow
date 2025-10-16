from typing import Annotated, Any, Literal, Optional
from uuid import uuid4

from pydantic import Field, PrivateAttr

from baserow_enterprise.assistant.types import BaseModel


class NodeBase(BaseModel):
    """Base node model."""

    label: str = Field(..., description="The human readable name of the node")
    type: str


class RefCreate(BaseModel):
    """Base node creation model."""

    ref: str = Field(
        ..., description="A reference ID for the node, only used during creation"
    )


class Item(BaseModel):
    id: str


class PeriodicTriggerSettings(BaseModel):
    """Periodic trigger interval model."""

    interval: Literal["MINUTE", "HOUR", "DAY", "WEEK", "MONTH"] = Field(
        ..., description="The interval for the periodic trigger"
    )
    minute: Optional[int] = Field(
        default=0, description="The number of minutes for the periodic trigger"
    )
    hour: Optional[int] = Field(
        default=0, description="The number of hours for the periodic trigger"
    )
    day_of_week: Optional[int] = Field(
        default=0,
        description="The day of the week for the periodic trigger (0=Monday, 6=Sunday)",
    )
    day_of_month: Optional[int] = Field(
        default=1, description="The day of the month for the periodic trigger (1-31)"
    )


class RowsTriggersSettings(BaseModel):
    """Table trigger configuration."""

    table_id: int = Field(..., description="The ID of the table to monitor")


class TriggerNodeCreate(NodeBase, RefCreate):
    """Create a trigger node in a workflow."""

    type: Literal[
        "periodic",
        "http_trigger",
        "rows_updated",
        "rows_created",
        "rows_deleted",
    ]

    # periodic trigger specific
    periodic_interval: Optional[PeriodicTriggerSettings] = Field(
        default=None,
        description="Configuration for periodic trigger",
    )
    rows_triggers_settings: Optional[RowsTriggersSettings] = Field(
        default=None,
        description="Configuration for rows trigger",
    )

    def to_orm_service_dict(self) -> dict[str, Any]:
        """Convert to ORM dict for node creation service."""

        if self.type == "periodic" and self.periodic_interval:
            return self.periodic_interval.model_dump()

        if (
            self.type in ["rows_created", "rows_updated", "rows_deleted"]
            and self.rows_triggers_settings
        ):
            return self.rows_triggers_settings.model_dump()

        return {}


class TriggerNodeItem(TriggerNodeCreate, Item):
    """Existing trigger node with ID."""

    http_trigger_url: str | None = Field(
        default=None, description="The URL to trigger the HTTP request"
    )


class EdgeCreate(BaseModel):
    previous_node_ref: str = Field(
        ...,
        description="The reference ID of the previous node to link from. Every node can have only one previous node.",
    )
    router_edge_label: str = Field(
        default="",
        description="If the previous node is a router, the edge label to link from if different from default",
    )

    def to_orm_reference_node(
        self, node_mapping: dict
    ) -> tuple[Optional[int], Optional[str]]:
        """Get the ORM node ID and output label from the previous node reference."""

        if self.previous_node_ref not in node_mapping:
            raise ValueError(
                f"Previous node ref '{self.previous_node_ref}' not found in mapping"
            )

        previous_orm_node, previous_node_create = node_mapping[self.previous_node_ref]

        output = ""
        if self.router_edge_label and previous_node_create.type == "router":
            output = next(
                (
                    edge._uid
                    for edge in previous_node_create.edges
                    if edge.label == self.router_edge_label
                ),
                None,
            )
            if output is None:
                raise ValueError(
                    f"Branch label '{self.router_edge_label}' not found in previous router node"
                )

        return previous_orm_node.id, output


class RouterEdgeCreate(BaseModel):
    """Router branch configuration."""

    label: str = Field(
        description="The label of the router branch. Order of branches matters: first matching branch is taken.",
    )
    condition: str = Field(
        default="",
        description="A brief description of the condition for this branch that will be converted to a formula.",
    )

    _uid: str = PrivateAttr(default_factory=lambda: str(uuid4()))

    def to_orm_service_dict(self) -> dict[str, Any]:
        return {
            "uid": self._uid,
            "label": self.label,
        }


class RouterBranch(RouterEdgeCreate, Item):
    """Existing router branch with ID."""


class RouterNodeBase(NodeBase):
    """Create a router node with branches."""

    type: Literal["router"]
    edges: list[RouterEdgeCreate] = Field(
        ...,
        description="List of branches for the router node. A default branch is created automatically.",
    )


class RouterNodeCreate(RouterNodeBase, RefCreate, EdgeCreate):
    """Create a router node with branches and link configuration."""

    def to_orm_service_dict(self) -> dict[str, Any]:
        return {"edges": [branch.to_orm_service_dict() for branch in self.edges]}


class RouterNodeItem(RouterNodeBase, Item):
    """Existing router node with ID."""


class SendEmailActionBase(NodeBase):
    """Send email action configuration."""

    type: Literal["smtp_email"]
    to_emails: str
    cc_emails: Optional[str]
    bcc_emails: Optional[str]
    subject: str
    body: str
    body_type: Literal["plain", "html"] = Field(default="plain")


class SendEmailActionCreate(SendEmailActionBase, RefCreate, EdgeCreate):
    """Create a send email action with edge configuration."""

    def to_orm_service_dict(self) -> dict[str, Any]:
        return {
            "to_email": f"'{self.to_emails}'",
            "cc_email": f"'{self.cc_emails or ''}'",
            "bcc_email": f"'{self.bcc_emails or ''}'",
            "subject": f"'{self.subject}'",
            "body": f"'{self.body}'",
            "body_type": f"'{self.body_type}'",
        }


class SendEmailActionItem(SendEmailActionBase, Item):
    """Existing send email action with ID."""


class CreateRowActionBase(NodeBase):
    """Create row action configuration."""

    type: Literal["create_row"]
    table_id: int
    values: dict[str, Any]


class RowActionService:
    def to_orm_service_dict(self) -> dict[str, Any]:
        return {
            "table_id": self.table_id,
        }


class CreateRowActionCreate(
    RowActionService, CreateRowActionBase, RefCreate, EdgeCreate
):
    """Create a create row action with edge configuration."""


class CreateRowActionItem(CreateRowActionBase, Item):
    """Existing create row action with ID."""


class UpdateRowActionBase(NodeBase):
    """Update row action configuration."""

    type: Literal["update_row"]
    table_id: int
    row: str = Field(..., description="The row ID or a formula to identify the row")
    values: dict[str, Any]


class UpdateRowActionCreate(
    RowActionService, UpdateRowActionBase, RefCreate, EdgeCreate
):
    """Create an update row action with edge configuration."""


class UpdateRowActionItem(UpdateRowActionBase, Item):
    """Existing update row action with ID."""


class DeleteRowActionBase(NodeBase):
    """Delete row action configuration."""

    type: Literal["delete_row"]
    table_id: int
    row: str = Field(..., description="The row ID or a formula to identify the row")


class DeleteRowActionCreate(
    RowActionService, DeleteRowActionBase, RefCreate, EdgeCreate
):
    """Create a delete row action with edge configuration."""


class DeleteRowActionItem(DeleteRowActionBase, Item):
    """Existing delete row action with ID."""


class AiAgentNodeBase(NodeBase):
    """AI Agent action configuration."""

    type: Literal["ai_agent"] = Field(
        ...,
        description="Don't stop at this node. Chain some other action to use the AI output.",
    )
    output_type: Literal["text", "choice"] = Field(default="text")
    choices: Optional[list[str]] = Field(
        default=None,
        description="List of choices if output_type is 'choice'",
    )
    temperature: float | None = Field(default=None)
    prompt: str


class AiAgentNodeCreate(AiAgentNodeBase, RefCreate, EdgeCreate):
    """Create an AI Agent action with edge configuration."""

    def to_orm_service_dict(self) -> dict[str, Any]:
        return {
            "ai_choices": (self.choices or []) if self.output_type == "choice" else [],
            "ai_temperature": self.temperature,
            "ai_prompt": f"'{self.prompt}'",
            "ai_output_type": self.output_type,
        }


class AiAgentNodeItem(AiAgentNodeBase, Item):
    """Existing AI Agent action with ID."""


AnyNodeCreate = Annotated[
    RouterNodeCreate
    # actions
    | SendEmailActionCreate
    | CreateRowActionCreate
    | UpdateRowActionCreate
    | DeleteRowActionCreate
    | AiAgentNodeCreate,
    Field(discriminator="type"),
]

AnyNodeItem = (
    RouterNodeItem
    # actions
    | SendEmailActionItem
    | CreateRowActionItem
    | UpdateRowActionItem
    | DeleteRowActionItem
    | AiAgentNodeItem
)
