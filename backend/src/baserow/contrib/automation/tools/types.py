"""
The workflow and node definitions the automation tools take, and how they become
service values. Values marked as accepting a formula are a literal or a formula,
see ``formulas``: a valid formula is stored as written, an invalid one is left
empty and reported back.
"""

from typing import Any, Callable, Literal, Optional
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, PrivateAttr, model_validator

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.tools.formulas import (
    EMPTY_FORMULA,
    InvalidAutomationFormula,
    check_automation_formula,
    formula_object,
    needs_formula,
    resolve_node_refs,
    wrap_static_string,
)
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_ADVANCED,
    BASEROW_FORMULA_MODE_SIMPLE,
    BaserowFormulaMode,
)
from baserow.core.services.models import Service


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)


# Appended to the description of the values that take a formula.
SUPPORTS_FORMULA = " A literal or a formula."


# ---------------------------------------------------------------------------
# Service values
# ---------------------------------------------------------------------------


# Returned for a value whose formula is invalid while updating: the value keeps
# what it had.
UNCHANGED = object()


class ServiceValues:
    """
    Builds a node's service values from its definition. A literal is quoted, a
    valid formula is kept. An invalid formula is collected in ``invalid`` and is
    left empty on a new node, or unchanged on an update. A value that can't be set
    at all is collected in ``errors``.
    """

    def __init__(
        self,
        table_field_ids: Callable[[int], set[int]],
        as_formulas: bool = False,
        refs: dict[str, int] | None = None,
        updating: bool = False,
    ):
        """
        :param table_field_ids: Returns the ids of the fields of a table.
        :param as_formulas: Take every value as a formula, for values a caller
            knows are formulas.
        :param refs: The ID of each node defined earlier in the call, by ref.
        :param updating: Whether the values update a node. An invalid formula
            then returns ``UNCHANGED``.
        """

        self.as_formulas = as_formulas
        self.refs = refs or {}
        self.updating = updating
        self.invalid: list[tuple[InvalidAutomationFormula, dict[str, Any]]] = []
        self.errors: list[str] = []
        self._table_field_ids = table_field_ids

    def formula(
        self,
        field: str,
        value: str,
        mode: BaserowFormulaMode = BASEROW_FORMULA_MODE_SIMPLE,
        **target: Any,
    ) -> Any:
        """
        A value that must be a formula. When it's invalid: an empty one, or
        ``UNCHANGED`` while updating.

        :param target: ``field_id`` or ``edge_label``, reported with an error.
        """

        value = resolve_node_refs(value, self.refs)
        try:
            check_automation_formula(field, value)
        except InvalidAutomationFormula as exc:
            self.invalid.append((exc, target))
            return UNCHANGED if self.updating else formula_object("", mode)
        return formula_object(value, mode)

    def value(self, field: str, value: str | None, **target: Any) -> Any:
        """A literal or a formula. An empty value is an empty literal."""

        if not value:
            return EMPTY_FORMULA
        if self.as_formulas or needs_formula(value):
            return self.formula(field, value, **target)
        return wrap_static_string(value)

    def field_mappings(
        self, table_id: int, values: list["AutomationFieldValue"]
    ) -> list[dict[str, Any]]:
        """
        The field mappings of a row action. A field of another table and a field
        with an invalid formula get no mapping.
        """

        field_ids = self._table_field_ids(table_id)
        mappings = []
        for field_value in values:
            if field_value.field_id not in field_ids:
                self.errors.append(
                    f"Field {field_value.field_id} is not in table {table_id}, so "
                    "its value was not set."
                )
                continue
            invalid = len(self.invalid)
            value = self.value(
                "values", field_value.value, field_id=field_value.field_id
            )
            if len(self.invalid) == invalid:
                mappings.append(
                    {"field_id": field_value.field_id, "value": value, "enabled": True}
                )
        return mappings


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


def _is_blank(value: Any) -> bool:
    """
    Whether a required value carries nothing to act on. Only text is judged
    empty: a row action with no values still creates or clears a row, but a blank
    row id names nothing.
    """

    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


class PeriodicTriggerSettings(BaseModel):
    """All times in UTC — remove timezone offsets."""

    interval: Literal["MINUTE", "HOUR", "DAY", "WEEK", "MONTH"]
    minute: int = Field(
        default=0,
        ge=0,
        le=59,
        description=f"MINUTE: minutes between triggers (min {settings.INTEGRATIONS_PERIODIC_MINUTE_MIN}). HOUR: minute of the hour.",
    )
    hour: int = Field(default=0, ge=0, le=23, description="UTC hour (0-23).")
    day_of_week: int = Field(default=0, ge=0, le=6, description="0=Monday, 6=Sunday.")
    day_of_month: int = Field(default=1, ge=1, le=31, description="1-31.")


class RowsTriggersSettings(BaseModel):
    """Table trigger configuration."""

    table_id: int = Field(..., description="The ID of the table to monitor")


class RouterEdgeCreate(BaseModel):
    """Router branch. Order matters: first matching branch is taken."""

    label: str = Field(max_length=75, description="Branch label.")
    condition: str = Field(
        description="A formula that is true when this branch is taken, for example "
        "greater_than(get('previous_node.1.0.field_2'), 100).",
    )

    _uid: str = PrivateAttr(default_factory=lambda: str(uuid4()))

    def to_orm_service_dict(self, values: ServiceValues) -> dict[str, Any]:
        return {
            "uid": self._uid,
            "label": self.label,
            "condition": values.formula(
                "condition",
                self.condition,
                BASEROW_FORMULA_MODE_ADVANCED,
                edge_label=self.label,
            ),
        }


class RouterEdgeUpdate(BaseModel):
    """A new condition for an existing router branch."""

    label: str = Field(description="The label of the branch.")
    condition: str = Field(description="The new condition formula.")


class AutomationFieldValue(BaseModel):
    """Field ID → value mapping for row actions."""

    field_id: int = Field(..., description="Database field ID.")
    value: str = Field(..., description=f"Field value.{SUPPORTS_FORMULA}")


# ---------------------------------------------------------------------------
# Node references
# ---------------------------------------------------------------------------


class NodeRefs:
    """
    The nodes a new node can follow, by the ref of a node defined earlier in the
    call, or by the ID of a node already in the workflow. A node is known before
    it exists, so a whole call can be checked before anything is written.
    """

    def __init__(self):
        self._nodes: dict[str, tuple[int | None, dict[str, str] | None]] = {}

    def copy(self) -> "NodeRefs":
        refs = NodeRefs()
        refs._nodes = dict(self._nodes)
        return refs

    def add(
        self, ref: str, node_id: int | None, edges: dict[str, str] | None = None
    ) -> None:
        """
        :param edges: The uid of each branch by label, for a router.
        """

        self._nodes[str(ref)] = (node_id, edges)

    def ids(self) -> dict[str, int]:
        """The ID of each node that exists, by ref."""

        return {ref: node_id for ref, (node_id, _) in self._nodes.items() if node_id}

    def __contains__(self, ref: str) -> bool:
        return str(ref) in self._nodes

    def resolve(self, ref: str, edge_label: str = "") -> tuple[int | None, str]:
        """
        The node a ref names, and the output of it to attach to.

        :raises DjangoValidationError: When the ref or the branch is unknown.
        """

        if ref not in self._nodes:
            raise DjangoValidationError(
                f"previous_node_ref '{ref}' is neither the ref of a node defined "
                "earlier in this call nor the ID of a node in the workflow."
            )
        node_id, edges = self._nodes[ref]
        if not edge_label or edges is None:
            return node_id, ""
        uid = edges.get(edge_label)
        if uid is None:
            matches = [
                uid
                for label, uid in edges.items()
                if label.lower() == edge_label.lower()
            ]
            uid = matches[0] if len(matches) == 1 else None
        if uid is None:
            labels = ", ".join(f"'{label}'" for label in edges) or "none"
            raise DjangoValidationError(
                f"router_edge_label '{edge_label}' is not a branch of node "
                f"'{ref}'. Its branches: {labels}."
            )
        return node_id, uid


# ---------------------------------------------------------------------------
# Trigger
# ---------------------------------------------------------------------------


_PERIODIC_KEYS = {"interval", "minute", "hour", "day_of_week", "day_of_month"}


# Registered node types, and the short names the definitions use.
CANONICAL_TO_SHORT_TYPE = {
    "local_baserow_rows_created": "rows_created",
    "local_baserow_rows_updated": "rows_updated",
    "local_baserow_rows_deleted": "rows_deleted",
    "local_baserow_create_row": "create_row",
    "local_baserow_update_row": "update_row",
    "local_baserow_delete_row": "delete_row",
}


def _fold_type_alias(data):
    """
    Replace a registered node type with its short name, leaving malformed types
    for validation.
    """

    if isinstance(data, dict):
        node_type = data.get("type")
        if isinstance(node_type, str) and node_type in CANONICAL_TO_SHORT_TYPE:
            data["type"] = CANONICAL_TO_SHORT_TYPE[node_type]
    return data


# Row-action service types differ from the short node names.
_SERVICE_TO_DISPATCH_TYPE = {
    "local_baserow_upsert_row": "update_row",
    "local_baserow_delete_row": "delete_row",
}


def service_dispatch_type(service: Service | None) -> str | None:
    """The short node type a node's service is handled as."""

    if service is None:
        return None
    service_type = service.get_type().type
    return _SERVICE_TO_DISPATCH_TYPE.get(service_type, service_type)


# Short forms only: _fold_type_alias rewrites registered names before validation.
ROW_TRIGGER_TYPES = frozenset({"rows_created", "rows_updated", "rows_deleted"})
ROW_ACTION_TYPES = frozenset({"create_row", "update_row", "delete_row"})


class TriggerNodeCreate(BaseModel):
    """Create a trigger node in a workflow."""

    ref: str = Field(..., description="Temporary reference ID for creation.")
    label: str = Field(
        "", max_length=75, description="Display name. Defaults to the node type."
    )
    # Registered names are accepted too, as list_nodes returns them.
    type: Literal[
        "periodic",
        "http_trigger",
        "rows_updated",
        "rows_created",
        "rows_deleted",
        "local_baserow_rows_updated",
        "local_baserow_rows_created",
        "local_baserow_rows_deleted",
    ]

    periodic_interval: Optional[PeriodicTriggerSettings] = Field(
        default=None,
        description="(periodic) Schedule settings in UTC.",
    )
    rows_triggers_settings: Optional[RowsTriggersSettings] = Field(
        default=None,
        description="(rows_*) Table to monitor.",
    )

    @model_validator(mode="before")
    @classmethod
    def _fold_registered_type(cls, data):
        return _fold_type_alias(data)

    @model_validator(mode="before")
    @classmethod
    def _fold_flat_periodic(cls, data):
        """Accept flat periodic fields (interval, hour, ...) and nest them."""

        if not isinstance(data, dict):
            return data
        if data.get("periodic_interval") is not None:
            return data
        flat = {k: data.pop(k) for k in list(data) if k in _PERIODIC_KEYS}
        if flat:
            data["periodic_interval"] = flat
        return data

    @model_validator(mode="after")
    def _validate_trigger_settings(self):
        if not self.label:
            self.label = self.type.replace("_", " ").capitalize()
        if self.type == "periodic" and self.periodic_interval is None:
            raise ValueError("periodic trigger requires periodic_interval")
        if self.type in ROW_TRIGGER_TYPES:
            if self.rows_triggers_settings is None:
                raise ValueError(f"{self.type} trigger requires rows_triggers_settings")
        return self

    def table_id(self) -> int | None:
        """The table a row trigger watches."""

        if self.type in ROW_TRIGGER_TYPES and self.rows_triggers_settings:
            return self.rows_triggers_settings.table_id
        return None

    def to_orm_service_dict(self) -> dict[str, Any]:
        """
        Convert to ORM dict for node creation service.

        :return: The type-specific trigger settings as service kwargs.
        """

        if self.type == "periodic" and self.periodic_interval:
            values = self.periodic_interval.model_dump()
            if self.periodic_interval.interval == "MINUTE":
                values["minute"] = max(
                    settings.INTEGRATIONS_PERIODIC_MINUTE_MIN,
                    values["minute"],
                )
            return values

        if self.type in ROW_TRIGGER_TYPES and self.rows_triggers_settings:
            return self.rows_triggers_settings.model_dump()

        return {}


# ---------------------------------------------------------------------------
# Action node
# ---------------------------------------------------------------------------

# Registered names are accepted too, as list_nodes returns them.
ActionNodeType = Literal[
    "router",
    "smtp_email",
    "slack_write_message",
    "create_row",
    "update_row",
    "delete_row",
    "ai_agent",
    "local_baserow_create_row",
    "local_baserow_update_row",
    "local_baserow_delete_row",
]


class ActionNodeCreate(BaseModel):
    """Flat model for creating an action node: type + type-specific fields."""

    @model_validator(mode="before")
    @classmethod
    def _fold_registered_type(cls, data):
        return _fold_type_alias(data)

    ref: str = Field(..., description="Temporary reference ID for creation.")
    label: str = Field(
        "", max_length=75, description="Display name. Defaults to the node type."
    )
    type: ActionNodeType
    previous_node_ref: str = Field(
        ...,
        description="The ref of the node this one follows: a node defined earlier "
        "in the call, or the ID of a node already in the workflow.",
    )
    router_edge_label: str = Field(
        default="",
        description="Branch label if previous node is a router.",
    )

    # -- router --
    edges: list[RouterEdgeCreate] | None = Field(
        default=None,
        description="(router) Branches. A default branch is auto-created.",
    )

    # -- smtp_email --
    to_emails: str | None = Field(
        default=None, description=f"(smtp_email) Recipients.{SUPPORTS_FORMULA}"
    )
    cc_emails: str | None = Field(
        default=None, description=f"(smtp_email) CC.{SUPPORTS_FORMULA}"
    )
    bcc_emails: str | None = Field(
        default=None, description=f"(smtp_email) BCC.{SUPPORTS_FORMULA}"
    )
    subject: str | None = Field(
        default=None, description=f"(smtp_email) Subject.{SUPPORTS_FORMULA}"
    )
    body: str | None = Field(
        default=None, description=f"(smtp_email) Body.{SUPPORTS_FORMULA}"
    )
    body_type: Literal["plain", "html"] = "plain"

    # -- slack_write_message --
    channel: str | None = Field(default=None, max_length=80)
    text: str | None = Field(
        default=None, description=f"(slack) Message.{SUPPORTS_FORMULA}"
    )

    # -- create_row / update_row / delete_row --
    table_id: int | None = None
    row_id: str | None = Field(
        default=None,
        description=(
            "(update/delete_row) Required: which row to act on. After a row "
            "trigger this is usually the triggering row: "
            "get('previous_node.<trigger node id>.0.id')."
            f"{SUPPORTS_FORMULA}"
        ),
    )
    values: list[AutomationFieldValue] | None = None

    # -- ai_agent --
    output_type: Literal["text", "choice"] = Field(
        default="text",
        description="(ai_agent) Chain another action to use the output.",
    )
    choices: list[str] | None = Field(
        default=None,
        description="(ai_agent) Choices if output_type='choice'.",
    )
    prompt: str | None = Field(
        default=None, description=f"(ai_agent) Prompt.{SUPPORTS_FORMULA}"
    )

    # Required fields per type
    _REQUIRED_FIELDS: dict[str, list[tuple[str, str]]] = {
        "router": [("edges", "edges")],
        "smtp_email": [
            ("to_emails", "to_emails"),
            ("subject", "subject"),
            ("body", "body"),
        ],
        "slack_write_message": [("channel", "channel"), ("text", "text")],
        "create_row": [("table_id", "table_id"), ("values", "values")],
        "update_row": [
            ("table_id", "table_id"),
            ("row_id", "row_id"),
            ("values", "values"),
        ],
        "delete_row": [("table_id", "table_id"), ("row_id", "row_id")],
        "ai_agent": [("prompt", "prompt")],
    }

    @model_validator(mode="after")
    def _validate_required_for_type(self):
        if not self.label:
            self.label = self.type.replace("_", " ").capitalize()
        labels = [edge.label.lower() for edge in self.edges or []]
        if len(labels) != len(set(labels)):
            raise ValueError("Each router branch needs its own label.")
        required = self._REQUIRED_FIELDS.get(self.type)
        if required:
            missing = [
                name for attr, name in required if _is_blank(getattr(self, attr))
            ]
            if missing:
                raise ValueError(f"{self.type} requires {', '.join(missing)}")
        return self

    def router_edges(self) -> dict[str, str] | None:
        """The uid of each branch by label, for a router."""

        if self.type != "router":
            return None
        return {edge.label: edge._uid for edge in self.edges or []}

    def to_orm_service_dict(self, values: ServiceValues) -> dict[str, Any]:
        """The service values of the node, with its formulas checked."""

        return _TO_ORM_SERVICE[self.type](self, values)


def _router_to_orm(n: ActionNodeCreate, values: ServiceValues) -> dict[str, Any]:
    return {"edges": [edge.to_orm_service_dict(values) for edge in n.edges]}


def _email_to_orm(n: ActionNodeCreate, values: ServiceValues) -> dict[str, Any]:
    return {
        "to_emails": values.value("to_emails", n.to_emails),
        "cc_emails": values.value("cc_emails", n.cc_emails),
        "bcc_emails": values.value("bcc_emails", n.bcc_emails),
        "subject": values.value("subject", n.subject),
        "body": values.value("body", n.body),
        "body_type": n.body_type,
    }


def _slack_to_orm(n: ActionNodeCreate, values: ServiceValues) -> dict[str, Any]:
    return {
        "channel": (n.channel or "").lstrip("#"),
        "text": values.value("text", n.text),
    }


def _row_action_to_orm(n: ActionNodeCreate, values: ServiceValues) -> dict[str, Any]:
    service: dict[str, Any] = {"table_id": n.table_id}
    if n.type == "delete_row":
        if n.values:
            values.errors.append("A delete_row node takes no values.")
    else:
        service["field_mappings"] = values.field_mappings(n.table_id, n.values or [])
    if n.type == "create_row":
        if n.row_id:
            # A row id would make the node update that row instead.
            values.errors.append("A create_row node takes no row_id.")
    elif n.row_id:
        service["row_id"] = values.value("row_id", n.row_id)
    return service


def _ai_agent_to_orm(n: ActionNodeCreate, values: ServiceValues) -> dict[str, Any]:
    return {
        "ai_choices": (n.choices or []) if n.output_type == "choice" else [],
        "ai_prompt": values.value("prompt", n.prompt),
        "ai_output_type": n.output_type,
    }


_TO_ORM_SERVICE: dict[str, Callable] = {
    "router": _router_to_orm,
    "smtp_email": _email_to_orm,
    "slack_write_message": _slack_to_orm,
    "create_row": _row_action_to_orm,
    "update_row": _row_action_to_orm,
    "delete_row": _row_action_to_orm,
    "ai_agent": _ai_agent_to_orm,
}


# ---------------------------------------------------------------------------
# NodeUpdate
# ---------------------------------------------------------------------------


class NodeUpdate(BaseModel):
    """Flat model for updating an automation node."""

    node_id: int = Field(..., description="The ID of the node to update.")
    label: str | None = Field(None, max_length=75, description="New display name.")

    # -- router --
    edges: list[RouterEdgeUpdate] | None = Field(
        default=None,
        description="(router) New conditions for existing branches, by label. "
        "Branches not listed keep theirs.",
    )

    # -- smtp_email --
    to_emails: str | None = Field(
        default=None, description=f"(smtp_email) Recipients.{SUPPORTS_FORMULA}"
    )
    cc_emails: str | None = Field(
        default=None, description=f"(smtp_email) CC.{SUPPORTS_FORMULA}"
    )
    bcc_emails: str | None = Field(
        default=None, description=f"(smtp_email) BCC.{SUPPORTS_FORMULA}"
    )
    subject: str | None = Field(
        default=None, description=f"(smtp_email) Subject.{SUPPORTS_FORMULA}"
    )
    body: str | None = Field(
        default=None, description=f"(smtp_email) Body.{SUPPORTS_FORMULA}"
    )
    body_type: Literal["plain", "html"] | None = None

    # -- slack_write_message --
    channel: str | None = Field(default=None, max_length=80)
    text: str | None = Field(
        default=None, description=f"(slack) Message.{SUPPORTS_FORMULA}"
    )

    # -- create_row / update_row / delete_row --
    table_id: int | None = None
    row_id: str | None = Field(
        default=None, description=f"(update/delete_row) Row ID.{SUPPORTS_FORMULA}"
    )
    values: list[AutomationFieldValue] | None = Field(
        default=None,
        description="(create/update_row) Field values to set. Fields not listed "
        "keep theirs.",
    )

    # -- ai_agent --
    output_type: Literal["text", "choice"] | None = None
    choices: list[str] | None = None
    prompt: str | None = Field(
        default=None, description=f"(ai_agent) Prompt.{SUPPORTS_FORMULA}"
    )

    def to_update_service_dict(
        self, node: AutomationNode, values: ServiceValues
    ) -> dict[str, Any] | None:
        """
        The service values to change, with their formulas checked.

        :param node: The node to update.
        :return: The service kwargs, or None when no service value changes.
        """

        builder = _TO_UPDATE_SERVICE.get(service_dispatch_type(node.service))
        if builder is None:
            return None
        service = builder(self, node, values)
        return {k: v for k, v in service.items() if v is not UNCHANGED} or None


def _email_update_service(
    n: NodeUpdate, node: AutomationNode, values: ServiceValues
) -> dict[str, Any]:
    d = {}
    for name in ("to_emails", "cc_emails", "bcc_emails", "subject", "body"):
        if getattr(n, name) is not None:
            d[name] = values.value(name, getattr(n, name))
    if n.body_type is not None:
        d["body_type"] = n.body_type
    return d


def _slack_update_service(
    n: NodeUpdate, node: AutomationNode, values: ServiceValues
) -> dict[str, Any]:
    d = {}
    if n.channel is not None:
        d["channel"] = n.channel.lstrip("#")
    if n.text is not None:
        d["text"] = values.value("text", n.text)
    return d


def _row_action_update_service(
    n: NodeUpdate, node: AutomationNode, values: ServiceValues
) -> dict[str, Any]:
    service = node.service.specific
    node_type = CANONICAL_TO_SHORT_TYPE.get(node.get_type().type)
    d: dict[str, Any] = {}
    table_id = service.table_id
    if n.table_id is not None and n.table_id != table_id:
        d["table_id"] = table_id = n.table_id
    if n.row_id is not None:
        if node_type == "create_row":
            # A row id would make the node update that row instead.
            values.errors.append("A create_row node takes no row_id.")
        else:
            d["row_id"] = values.value("row_id", n.row_id)
    if node_type == "delete_row":
        if n.values:
            values.errors.append("A delete_row node takes no values.")
        return d
    if n.values is not None or "table_id" in d:
        # Mappings of the previous table can't be dispatched on the new one.
        mappings = (
            {}
            if "table_id" in d
            else {
                mapping.field_id: {
                    "field_id": mapping.field_id,
                    "value": mapping.value,
                    "enabled": mapping.enabled,
                }
                for mapping in service.field_mappings.all()
            }
        )
        if table_id is not None:
            for mapping in values.field_mappings(table_id, n.values or []):
                mappings[mapping["field_id"]] = mapping
        elif n.values:
            values.errors.append(
                "The node has no table, so its values were not set. Give a "
                "table_id with them."
            )
        d["field_mappings"] = list(mappings.values())
    return d


def _router_update_service(
    n: NodeUpdate, node: AutomationNode, values: ServiceValues
) -> dict[str, Any]:
    if not n.edges:
        return {}
    edges = [
        {"uid": str(edge.uid), "label": edge.label, "condition": edge.condition}
        for edge in node.service.specific.edges.all()
    ]
    for update in n.edges:
        matches = [edge for edge in edges if edge["label"] == update.label] or [
            edge for edge in edges if edge["label"].lower() == update.label.lower()
        ]
        if len(matches) != 1:
            labels = ", ".join(f"'{edge['label']}'" for edge in edges) or "none"
            reason = "names several branches" if matches else "is not a branch"
            values.errors.append(
                f"'{update.label}' {reason} of node {n.node_id}, so its condition "
                f"was not set. Its branches: {labels}."
            )
            continue
        condition = values.formula(
            "condition",
            update.condition,
            BASEROW_FORMULA_MODE_ADVANCED,
            edge_label=matches[0]["label"],
        )
        if condition is not UNCHANGED:
            matches[0]["condition"] = condition
    return {"edges": edges}


def _ai_agent_update_service(
    n: NodeUpdate, node: AutomationNode, values: ServiceValues
) -> dict[str, Any]:
    d = {}
    if n.prompt is not None:
        d["ai_prompt"] = values.value("prompt", n.prompt)
    if n.output_type is not None:
        d["ai_output_type"] = n.output_type
    if n.choices is not None:
        d["ai_choices"] = n.choices
    return d


_TO_UPDATE_SERVICE: dict[str, Callable] = {
    "router": _router_update_service,
    "smtp_email": _email_update_service,
    "slack_write_message": _slack_update_service,
    "update_row": _row_action_update_service,
    "delete_row": _row_action_update_service,
    "ai_agent": _ai_agent_update_service,
}


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


class WorkflowCreate(BaseModel):
    """A workflow to create, with its trigger and the nodes after it."""

    name: str = Field(..., max_length=255, description="Workflow name.")
    trigger: TriggerNodeCreate = Field(..., description="The trigger node.")
    nodes: list[ActionNodeCreate] = Field(
        default_factory=list,
        description="Action nodes executed after the trigger. Each node has one previous_node_ref.",
    )
