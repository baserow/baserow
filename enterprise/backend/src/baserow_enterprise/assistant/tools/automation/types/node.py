"""
Automation node type models and ORM conversion logic.

Defines ``TriggerNodeCreate``, ``ActionNodeCreate``, and their read-back
counterparts (``TriggerNodeItem``, ``ActionNodeItem``), plus the dispatch
tables that convert between Pydantic models and Django ORM representations.
"""

import re
from typing import Any, Callable, Literal, Optional
from uuid import uuid4

from django.conf import settings

from pydantic import Field, PrivateAttr, model_serializer, model_validator

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_ADVANCED,
    BaserowFormulaObject,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow_enterprise.assistant.types import BaseModel

FORMULA_PREFIX = "$formula:"

# Short marker appended to fields that support $formula: dynamic values.
# The full explanation lives in the create_workflows tool description.
_F = f" Supports {FORMULA_PREFIX} prefix."

# Detects raw formula syntax the LLM might write instead of using $formula:.
# Matches: get('...'), concat(...), {{ ... }}, comparison operators, if(...),
# today(), now().
_RAW_FORMULA_RE = re.compile(
    r"\bget\s*\(|\bconcat\s*\(|\{\{.*\}\}"
    r"|\b(?:equal|not_equal|greater_than|less_than|greater_than_equal|less_than_equal)\s*\("
    r"|\bif\s*\(|\btoday\s*\(|\bnow\s*\("
)


# ---------------------------------------------------------------------------
# Formula value helpers
# ---------------------------------------------------------------------------


def _needs_formula(value: str | None) -> bool:
    """
    Check if a value requires formula processing.

    Returns True for explicit ``$formula:`` prefixed values *and* for raw
    formula expressions the LLM may write inline (e.g. ``get('field')``
    or ``{{ get('field') }}``).
    """

    if not value:
        return False
    stripped = value.strip()
    return stripped.lower().startswith(FORMULA_PREFIX) or bool(
        _RAW_FORMULA_RE.search(stripped)
    )


def _formula_desc(value: str) -> str:
    """
    Extract the formula description from a value.

    For ``$formula:`` prefixed values, strips the prefix.
    For raw formula expressions, returns the value as-is so the
    formula generator can convert it to a proper formula.
    """

    stripped = value.strip()
    if stripped.lower().startswith(FORMULA_PREFIX):
        return stripped[len(FORMULA_PREFIX) :].strip()
    # Raw formula expression — pass through for the generator to fix up
    return stripped


def _literal_or_placeholder(value: str | None) -> str:
    """Return a quoted literal formula, or empty placeholder for formula values."""
    if not value or _needs_formula(value):
        return "''"
    return f"'{value}'"


# ---------------------------------------------------------------------------
# Field-mapping helpers (shared by apply_direct / update_formulas)
# ---------------------------------------------------------------------------


def _upsert_field_mappings(
    service: Service,
    values: dict[int, tuple[str, bool]],
):
    """
    Bulk-upsert field mappings on a service.

    ``values`` maps ``field_id → (formula_value, enabled)``.
    Existing mappings are updated in place; missing ones are created.
    """

    if not values:
        return

    existing = {m.field_id: m for m in service.field_mappings.all()}
    FieldMapping = service.field_mappings.model
    to_create, to_update = [], []

    for field_id, (formula, enabled) in values.items():
        if field_id in existing:
            mapping = existing[field_id]
            mapping.value = formula
            mapping.enabled = enabled
            to_update.append(mapping)
        else:
            to_create.append(
                FieldMapping(
                    field_id=field_id,
                    value=formula,
                    enabled=enabled,
                    service_id=service.id,
                )
            )

    if to_create:
        service.field_mappings.bulk_create(to_create)
    if to_update:
        FieldMapping.objects.bulk_update(to_update, ["value", "enabled"])


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class PeriodicTriggerSettings(BaseModel):
    """All times in UTC — remove timezone offsets."""

    interval: Literal["MINUTE", "HOUR", "DAY", "WEEK", "MONTH"]
    minute: int = Field(
        default=0,
        description=f"MINUTE: minutes between triggers (min {settings.INTEGRATIONS_PERIODIC_MINUTE_MIN}). HOUR: minute of the hour.",
    )
    hour: int = Field(default=0, description="UTC hour (0-23).")
    day_of_week: int = Field(default=0, description="0=Monday, 6=Sunday.")
    day_of_month: int = Field(default=1, description="1-31.")


class RowsTriggersSettings(BaseModel):
    """Table trigger configuration."""

    table_id: int = Field(..., description="The ID of the table to monitor")


class RouterEdgeCreate(BaseModel):
    """Router branch. Order matters: first matching branch is taken."""

    label: str = Field(description="Branch label.")
    condition: str = Field(
        description="Boolean condition using comparison operators and get() functions.",
    )

    _uid: str = PrivateAttr(default_factory=lambda: str(uuid4()))

    def to_orm_service_dict(self) -> dict[str, Any]:
        return {"uid": self._uid, "label": self.label}


class RouterBranch(RouterEdgeCreate):
    """Existing router branch with ID."""

    id: str


class AutomationFieldValue(BaseModel):
    """Field ID → value mapping for row actions."""

    field_id: int = Field(..., description="Database field ID.")
    value: str = Field(..., description=f"Field value.{_F}")


# ---------------------------------------------------------------------------
# Trigger
# ---------------------------------------------------------------------------


_PERIODIC_KEYS = {"interval", "minute", "hour", "day_of_week", "day_of_month"}


class TriggerNodeCreate(BaseModel):
    """Create a trigger node in a workflow."""

    ref: str = Field(..., description="Temporary reference ID for creation.")
    label: str = Field(..., description="Display name.")
    type: Literal[
        "periodic",
        "http_trigger",
        "rows_updated",
        "rows_created",
        "rows_deleted",
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
        if self.type == "periodic" and self.periodic_interval is None:
            raise ValueError("periodic trigger requires periodic_interval")
        if self.type in ("rows_created", "rows_updated", "rows_deleted"):
            if self.rows_triggers_settings is None:
                raise ValueError(f"{self.type} trigger requires rows_triggers_settings")
        return self

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


class TriggerNodeItem(TriggerNodeCreate):
    """Existing trigger node with ID."""

    id: str
    http_trigger_url: str | None = Field(
        default=None, description="The URL to trigger the HTTP request"
    )


# ---------------------------------------------------------------------------
# Action node
# ---------------------------------------------------------------------------

ActionNodeType = Literal[
    "router",
    "smtp_email",
    "slack_write_message",
    "create_row",
    "update_row",
    "delete_row",
    "ai_agent",
]


class ActionNodeCreate(BaseModel):
    """Flat model for creating an action node: type + type-specific fields."""

    ref: str = Field(..., description="Temporary reference ID for creation.")
    label: str = Field(..., description="Display name.")
    type: ActionNodeType
    previous_node_ref: str = Field(..., description="Ref of the preceding node.")
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
        default=None, description=f"(smtp_email) Recipients.{_F}"
    )
    cc_emails: str | None = Field(default=None, description=f"(smtp_email) CC.{_F}")
    bcc_emails: str | None = Field(default=None, description=f"(smtp_email) BCC.{_F}")
    subject: str | None = Field(default=None, description=f"(smtp_email) Subject.{_F}")
    body: str | None = Field(default=None, description=f"(smtp_email) Body.{_F}")
    body_type: Literal["plain", "html"] = "plain"

    # -- slack_write_message --
    channel: str | None = None
    text: str | None = Field(default=None, description=f"(slack) Message.{_F}")

    # -- create_row / update_row / delete_row --
    table_id: int | None = None
    row_id: str | None = Field(
        default=None, description=f"(update/delete_row) Row ID.{_F}"
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
    prompt: str | None = Field(default=None, description=f"(ai_agent) Prompt.{_F}")

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
        required = self._REQUIRED_FIELDS.get(self.type)
        if required:
            missing = [name for attr, name in required if getattr(self, attr) is None]
            if missing:
                raise ValueError(f"{self.type} requires {', '.join(missing)}")
        return self

    # -- ORM conversion --

    def to_orm_service_dict(self) -> dict[str, Any]:
        """Convert type-specific fields to an ORM service dict."""
        return _TO_ORM_SERVICE[self.type](self)

    def to_orm_reference_node(self, node_mapping: dict) -> tuple[Optional[int], str]:
        """Resolve the previous node reference into an ORM node ID and output label."""

        if self.previous_node_ref not in node_mapping:
            raise ValueError(
                f"Previous node ref '{self.previous_node_ref}' not found in mapping"
            )

        previous_orm_node, previous_node_create = node_mapping[self.previous_node_ref]

        output = ""
        if (
            self.router_edge_label
            and getattr(previous_node_create, "type", None) == "router"
        ):
            edges = getattr(previous_node_create, "edges", None) or []
            output = next(
                (edge._uid for edge in edges if edge.label == self.router_edge_label),
                None,
            )
            if output is None:
                raise ValueError(
                    f"Branch label '{self.router_edge_label}' not found in previous router node"
                )

        return previous_orm_node.id, output

    # -- Formula lifecycle --

    def get_formulas_to_create(self, orm_node: AutomationNode) -> dict[str, str] | None:
        """Return a ``{key: description}`` dict of formulas to generate, or None."""

        fn = _GET_FORMULAS.get(self.type)
        return fn(self, orm_node) if fn else None

    def apply_direct_values(self, service: Service):
        """Apply literal (non-$formula) values directly to the service."""

        fn = _APPLY_DIRECT.get(self.type)
        if fn is not None:
            fn(self, service)

    def update_service_with_formulas(self, service: Service, formulas: dict[str, str]):
        """Write generated formulas back to the ORM service."""

        fn = _UPDATE_FORMULAS.get(self.type)
        if fn is not None:
            fn(self, service, formulas)
        else:
            _default_update_formulas(service, formulas)


# ---------------------------------------------------------------------------
# to_orm_service dispatch: (ActionNodeCreate) -> dict
# ---------------------------------------------------------------------------


def _router_to_orm(n: ActionNodeCreate) -> dict[str, Any]:
    return {"edges": [branch.to_orm_service_dict() for branch in n.edges]}


def _email_to_orm(n: ActionNodeCreate) -> dict[str, Any]:
    return {
        "to_email": _literal_or_placeholder(n.to_emails),
        "cc_email": _literal_or_placeholder(n.cc_emails),
        "bcc_email": _literal_or_placeholder(n.bcc_emails),
        "subject": _literal_or_placeholder(n.subject),
        "body": _literal_or_placeholder(n.body),
        "body_type": f"'{n.body_type}'",
    }


def _slack_to_orm(n: ActionNodeCreate) -> dict[str, Any]:
    channel = (n.channel or "").lstrip("#")
    return {
        "channel": channel,
        "text": _literal_or_placeholder(n.text),
    }


def _row_action_to_orm(n: ActionNodeCreate) -> dict[str, Any]:
    return {"table_id": n.table_id}


def _ai_agent_to_orm(n: ActionNodeCreate) -> dict[str, Any]:
    return {
        "ai_choices": (n.choices or []) if n.output_type == "choice" else [],
        "ai_prompt": _literal_or_placeholder(n.prompt),
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
# get_formulas_to_create dispatch: (ActionNodeCreate, AutomationNode) -> dict | None
# ---------------------------------------------------------------------------


def _router_formulas(n: ActionNodeCreate, orm_node: AutomationNode) -> dict[str, str]:
    return {edge.label: edge.condition for edge in n.edges}


def _email_formulas(
    n: ActionNodeCreate, orm_node: AutomationNode
) -> dict[str, str] | None:
    fields = {
        "to_emails": (
            "A comma separated list of email addresses to send the email to.",
            n.to_emails,
        ),
        "cc_emails": (
            "A comma separated list of email addresses to CC the email to.",
            n.cc_emails,
        ),
        "bcc_emails": (
            "A comma separated list of email addresses to BCC the email to.",
            n.bcc_emails,
        ),
        "subject": ("The subject of the email.", n.subject),
        "body": (f"The {n.body_type} body content of the email.", n.body),
    }
    values = {
        key: f"{base_desc} Value to resolve: {_formula_desc(val)}"
        for key, (base_desc, val) in fields.items()
        if _needs_formula(val)
    }
    return values or None


def _slack_formulas(
    n: ActionNodeCreate, orm_node: AutomationNode
) -> dict[str, str] | None:
    if _needs_formula(n.text):
        return {
            "text": f"The message content. Value to resolve: {_formula_desc(n.text)}"
        }
    return None


def _row_action_formulas(
    n: ActionNodeCreate, orm_node: AutomationNode
) -> dict[str, str] | None:
    from baserow_enterprise.assistant.tools.shared.formula_utils import (
        minimize_json_schema,
    )

    service = orm_node.service.specific
    schema = service.get_type().generate_schema(service.specific)
    values_by_id = {fv.field_id: fv.value for fv in (n.values or [])}
    values = {}

    if _needs_formula(n.row_id):
        values["row_id"] = (
            f"the row ID to update. Value to resolve: {_formula_desc(n.row_id)}"
        )

    for v in minimize_json_schema(schema).values():
        value = values_by_id.get(int(v["id"]))
        if _needs_formula(value):
            desc = v["desc"] + f" Value to resolve: {_formula_desc(value)}"
            values[int(v["id"])] = {**v, "desc": desc}

    return values or None


def _ai_agent_formulas(
    n: ActionNodeCreate, orm_node: AutomationNode
) -> dict[str, str] | None:
    if _needs_formula(n.prompt):
        return {
            "ai_prompt": f"The AI prompt. Value to resolve: {_formula_desc(n.prompt)}"
        }
    return None


_GET_FORMULAS: dict[str, Callable] = {
    "router": _router_formulas,
    "smtp_email": _email_formulas,
    "slack_write_message": _slack_formulas,
    "create_row": _row_action_formulas,
    "update_row": _row_action_formulas,
    "delete_row": _row_action_formulas,
    "ai_agent": _ai_agent_formulas,
}


# ---------------------------------------------------------------------------
# update_service_with_formulas dispatch
# ---------------------------------------------------------------------------


def _default_update_formulas(service: Service, formulas: dict[str, str]):
    """Set ``BaserowFormulaObject`` on named service fields."""

    save = False
    for field_name, formula in formulas.items():
        if hasattr(service, field_name):
            setattr(service, field_name, BaserowFormulaObject.create(formula=formula))
            save = True
    if save:
        ServiceHandler().update_service(service.get_type(), service)


def _router_update_formulas(
    n: ActionNodeCreate, service: Service, formulas: dict[str, str]
):
    """Write generated condition formulas to router edges."""

    formulas_lower = {k.lower(): v for k, v in formulas.items()}
    EdgeModel = service.specific.edges.model
    updates = []
    for orm_edge in service.specific.edges.all():
        label = orm_edge.label.lower()
        if label in formulas_lower:
            orm_edge.condition["mode"] = BASEROW_FORMULA_MODE_ADVANCED
            orm_edge.condition["formula"] = formulas_lower[label]
            updates.append(orm_edge)
    if updates:
        EdgeModel.objects.bulk_update(updates, ["condition"])


def _row_action_update_formulas(
    n: ActionNodeCreate, service: Service, formulas: dict[str, str]
):
    """Write generated formulas to row action field mappings and row_id."""

    row_id_formula = formulas.pop("row_id", None)

    _upsert_field_mappings(
        service,
        {field_id: (formula, True) for field_id, formula in formulas.items()},
    )

    if row_id_formula:
        service.row_id = row_id_formula
        ServiceHandler().update_service(service.get_type(), service)


_UPDATE_FORMULAS: dict[str, Callable] = {
    "router": _router_update_formulas,
    "create_row": _row_action_update_formulas,
    "update_row": _row_action_update_formulas,
    "delete_row": _row_action_update_formulas,
}


# ---------------------------------------------------------------------------
# apply_direct_values dispatch
# ---------------------------------------------------------------------------


def _row_action_apply_direct(n: ActionNodeCreate, service: Service):
    """Write literal (non-$formula) field values as quoted formulas."""

    _upsert_field_mappings(
        service,
        {
            fv.field_id: (f"'{fv.value}'", True)
            for fv in (n.values or [])
            if not _needs_formula(fv.value)
        },
    )

    if n.row_id and not _needs_formula(n.row_id):
        service.row_id = f"'{n.row_id}'"
        ServiceHandler().update_service(service.get_type(), service)


_APPLY_DIRECT: dict[str, Callable] = {
    "create_row": _row_action_apply_direct,
    "update_row": _row_action_apply_direct,
    "delete_row": _row_action_apply_direct,
}


# ---------------------------------------------------------------------------
# ActionNodeItem (read-back)
# ---------------------------------------------------------------------------


class ActionNodeItem(BaseModel):
    """Existing action node with ID — flat structure, excludes None values."""

    id: str
    label: str
    type: str
    previous_node_ref: str | None = None
    router_edge_label: str | None = None

    # (router)
    edges: list[RouterBranch] | None = None

    # (smtp_email)
    to_emails: str | None = None
    cc_emails: str | None = None
    bcc_emails: str | None = None
    subject: str | None = None
    body: str | None = None
    body_type: str | None = None

    # (slack_write_message)
    channel: str | None = None
    text: str | None = None

    # (create_row, update_row, delete_row)
    table_id: int | None = None
    row_id: str | None = None
    values: list[AutomationFieldValue] | None = None

    # (ai_agent)
    output_type: str | None = None
    choices: list[str] | None = None
    prompt: str | None = None

    @model_serializer(mode="wrap")
    def _exclude_none(self, handler):
        return {k: v for k, v in handler(self).items() if v is not None}
