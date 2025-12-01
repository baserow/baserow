from abc import ABC, abstractmethod
from typing import Annotated, Any, Literal, Optional
from uuid import uuid4

from django.conf import settings

from pydantic import Field, PrivateAttr

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_ADVANCED,
    BaserowFormulaObject,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
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


class HasFormulasToCreateMixin(ABC):
    @abstractmethod
    def get_formulas_to_create(self, orm_node: AutomationNode) -> dict[str, str]:
        """
        Creates and returns a mapping between field names and formulas to be created
        for the given ORM node. Every value needs to contain instructions or description
        on how to generate the formula for that field.
        Prefix optional fields with "[optional]: " in the description to indicate they
        are not mandatory.
        """

        pass

    def update_service_with_formulas(self, service: Service, formulas: dict[str, str]):
        save = False
        for field_name, formula in formulas.items():
            if hasattr(service, field_name):
                setattr(
                    service,
                    field_name,
                    BaserowFormulaObject.create(formula=formula),
                )
                save = True
        if save:
            ServiceHandler().update_service(service.get_type(), service)


class PeriodicTriggerSettings(BaseModel):
    interval: Literal["MINUTE", "HOUR", "DAY", "WEEK", "MONTH"] = Field(
        ..., description="The interval for the periodic trigger"
    )
    minute: int = Field(
        default=0,
        description=(
            "If interval=MINUTE, the number of minutes between each trigger. "
            f"Minimum is set to {settings.INTEGRATIONS_PERIODIC_MINUTE_MIN} minutes. "
            "If interval=HOUR, the UTC minute for the periodic trigger. "
        ),
    )
    hour: int = Field(
        default=0,
        description=(
            "The UTC hour for the periodic trigger. "
            "ALWAYS remove timezone offset from the context."
        ),
    )
    day_of_week: int = Field(
        default=0,
        description="The day of the week for the periodic trigger (0=Monday, 6=Sunday)",
    )
    day_of_month: int = Field(
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
        description="UTC configuration for periodic trigger. ALWAYS remove timezone offset from the context.",
    )
    rows_triggers_settings: Optional[RowsTriggersSettings] = Field(
        default=None,
        description="Configuration for rows trigger",
    )

    def to_orm_service_dict(self) -> dict[str, Any]:
        """Convert to ORM dict for node creation service."""

        if self.type == "periodic" and self.periodic_interval:
            values = self.periodic_interval.model_dump()
            if self.periodic_interval.interval == "MINUTE":
                values["minute"] = max(
                    settings.INTEGRATIONS_PERIODIC_MINUTE_MIN,
                    values["minute"],
                )
            return values

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
        description=(
            "The condition formula to evaluate for this branch as boolean. "
            "Use comparison operators and get(...) functions to build the formula with a boolean result. "
            "Always mentions the field values using get(...) functions."
        ),
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


class RouterNodeCreate(RouterNodeBase, RefCreate, EdgeCreate, HasFormulasToCreateMixin):
    """Create a router node with branches and link configuration."""

    def to_orm_service_dict(self) -> dict[str, Any]:
        return {"edges": [branch.to_orm_service_dict() for branch in self.edges]}

    def get_formulas_to_create(self, orm_node: AutomationNode) -> dict[str, str]:
        return {edge.label: edge.condition for edge in self.edges}

    def update_service_with_formulas(self, service: Service, formulas: dict[str, str]):
        orm_edges = service.specific.edges.all()
        formulas = {k.lower(): v for k, v in formulas.items()}
        EdgeModel = service.specific.edges.model
        updates = []
        for orm_edge in orm_edges:
            label = orm_edge.label.lower()
            if label in formulas:
                orm_edge.condition["mode"] = BASEROW_FORMULA_MODE_ADVANCED
                orm_edge.condition["formula"] = formulas[label]
                updates.append(orm_edge)
        if updates:
            EdgeModel.objects.bulk_update(updates, ["condition"])


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


class SendEmailActionCreate(
    SendEmailActionBase, RefCreate, EdgeCreate, HasFormulasToCreateMixin
):
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

    def get_formulas_to_create(self, orm_node: AutomationNode) -> dict[str, str]:
        values = {}
        to_emails_base = (
            "A comma separated list of email addresses to send the email to."
        )
        if self.to_emails:
            values["to_emails"] = (
                to_emails_base + f" Value to resolve: {self.to_emails}"
            )
        else:
            values["to_emails"] = "[optional]: " + to_emails_base

        cc_emails_base = "A comma separated list of email addresses to CC the email to."
        if self.cc_emails:
            values["cc_emails"] = (
                cc_emails_base + f" Value to resolve: {self.cc_emails}"
            )
        else:
            values["cc_emails"] = "[optional]: " + cc_emails_base

        bcc_emails_base = (
            "A comma separated list of email addresses to BCC the email to."
        )
        if self.bcc_emails:
            values["bcc_emails"] = (
                bcc_emails_base + f" Value to resolve: {self.bcc_emails}"
            )
        else:
            values["bcc_emails"] = "[optional]: " + bcc_emails_base

        values["subject"] = "The subject of the email."
        if self.subject:
            values["subject"] += f" Value to resolve: {self.subject}"

        values["body"] = f"The {self.body_type} body content of the email."
        if self.body:
            values["body"] += f" Value to resolve: {self.body}"
        return values


class SendEmailActionItem(SendEmailActionBase, Item):
    """Existing send email action with ID."""


class SlackWriteMessageActionBase(NodeBase):
    """Send Slack message action configuration."""

    type: Literal["slack_write_message"]
    channel: str
    text: str


class SlackWriteMessageActionCreate(
    SlackWriteMessageActionBase, RefCreate, EdgeCreate, HasFormulasToCreateMixin
):
    """Create a send Slack message action with edge configuration."""

    def to_orm_service_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "text": f"'{self.text}'",
        }

    def get_formulas_to_create(self, orm_node: AutomationNode) -> dict[str, str]:
        values = {}

        message_base = "The message content."
        if self.text:
            values["text"] = message_base + f" Value to resolve: '{self.text}'"
        else:
            values["text"] = "[optional]: " + message_base
        return values


class CreateRowActionBase(NodeBase):
    """Create row action configuration."""

    type: Literal["create_row"]
    table_id: int
    values: dict[int, Any] = Field(
        ..., description="A mapping of field IDs to values or formulas to update"
    )


class RowActionService:
    def to_orm_service_dict(self) -> dict[str, Any]:
        return {
            "table_id": self.table_id,
        }


class RowActionFormulaToCreate(HasFormulasToCreateMixin):
    def get_formulas_to_create(self, orm_node: AutomationNode) -> dict[str, str]:
        from baserow_enterprise.assistant.tools.automation.utils import (
            _minimize_json_schema,
        )

        service = orm_node.service.specific
        schema = service.get_type().generate_schema(service.specific)
        values = {"row_id": "the row ID to update"}
        for v in _minimize_json_schema(schema).values():
            desc = v["desc"]
            value = self.values.get(int(v["id"]))
            if value:
                desc += f" Value to resolve: {value}"
            else:
                desc = "[optional]: " + desc
            values[int(v["id"])] = {**v, "desc": desc}
        return values

    def update_service_with_formulas(self, service: Service, formulas: dict[str, str]):
        row_id_formula = formulas.pop("row_id", None)

        field_mappings = {m.field_id: m for m in service.field_mappings.all()}
        field_mapping_to_create = []
        field_mapping_to_update = []
        FieldMapping = service.field_mappings.model
        for field_id, formula in formulas.items():
            if field_id in field_mappings:
                field_mappings[field_id].value = formula
                field_mappings[field_id].enabled = True
                field_mapping_to_update.append(field_mappings[field_id])
            else:
                field_mapping_to_create.append(
                    FieldMapping(
                        field_id=field_id,
                        value=formula,
                        enabled=True,
                        service_id=service.id,
                    )
                )
        if field_mapping_to_create:
            service.field_mappings.bulk_create(field_mapping_to_create)
        if field_mapping_to_update:
            FieldMapping.objects.bulk_update(
                field_mapping_to_update, ["value", "enabled"]
            )

        if row_id_formula:
            service.row_id = row_id_formula
            ServiceHandler().update_service(service.get_type(), service)


class CreateRowActionCreate(
    RowActionService,
    CreateRowActionBase,
    RefCreate,
    EdgeCreate,
    RowActionFormulaToCreate,
):
    """Create a create row action with edge configuration."""


class CreateRowActionItem(CreateRowActionBase, Item):
    """Existing create row action with ID."""


class UpdateRowActionBase(NodeBase):
    """Update row action configuration."""

    type: Literal["update_row"]
    table_id: int
    row_id: str = Field(..., description="The row ID or a formula to identify the row")
    values: dict[int, Any] = Field(
        ..., description="A mapping of field IDs to values or formulas to update"
    )


class UpdateRowActionCreate(
    RowActionService,
    UpdateRowActionBase,
    RefCreate,
    EdgeCreate,
    RowActionFormulaToCreate,
):
    """Create an update row action with edge configuration."""


class UpdateRowActionItem(UpdateRowActionBase, Item):
    """Existing update row action with ID."""


class DeleteRowActionBase(NodeBase):
    """Delete row action configuration."""

    type: Literal["delete_row"]
    table_id: int
    row_id: str = Field(..., description="The row ID or a formula to identify the row")


class DeleteRowActionCreate(
    RowActionService,
    DeleteRowActionBase,
    RefCreate,
    EdgeCreate,
    RowActionFormulaToCreate,
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
    prompt: str


class AiAgentNodeCreate(
    AiAgentNodeBase, RefCreate, EdgeCreate, HasFormulasToCreateMixin
):
    """Create an AI Agent action with edge configuration."""

    def to_orm_service_dict(self) -> dict[str, Any]:
        return {
            "ai_choices": (self.choices or []) if self.output_type == "choice" else [],
            "ai_prompt": f"'{self.prompt}'",
            "ai_output_type": self.output_type,
        }

    def get_formulas_to_create(self, orm_node: AutomationNode) -> dict[str, str]:
        return {"ai_prompt": self.prompt}


class AiAgentNodeItem(AiAgentNodeBase, Item):
    """Existing AI Agent action with ID."""


AnyNodeCreate = Annotated[
    RouterNodeCreate
    # actions
    | SendEmailActionCreate
    | SlackWriteMessageActionCreate
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
