"""
Builder workflow action type models.

Defines ``ActionCreate`` (flat) for creating workflow actions and
``ActionItem`` for reading them back.
"""

from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, model_validator

from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_ADVANCED,
    BaserowFormulaObject,
)
from baserow_enterprise.assistant.tools.shared.formula_utils import (
    formula_desc,
    literal_or_placeholder,
    needs_formula,
)
from baserow_enterprise.assistant.types import BaseModel

if TYPE_CHECKING:
    from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
    from baserow_enterprise.assistant.tools.builder.agents import BuilderFormulaContext

# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

ActionType = Literal[
    "notification",
    "open_page",
    "create_row",
    "update_row",
    "delete_row",
    "refresh_data_source",
    "logout",
]


class ParameterMapping(BaseModel):
    """Key-value parameter mapping for page/query parameters."""

    name: str = Field(..., description="Parameter name.")
    value: str = Field(..., description="Parameter value formula.")


class FieldValueMapping(BaseModel):
    """Field-value mapping for row create/update actions."""

    field_id: str = Field(..., description="The field ID (as string).")
    value: str = Field(
        ...,
        description="Value or $formula: prefix + formula intent.",
    )


# ---------------------------------------------------------------------------
# Required fields per action type
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "notification": ("title",),
    "open_page": ("navigate_to_page_id",),
    "create_row": ("table_id", "field_values"),
    "update_row": ("table_id", "row_id", "field_values"),
    "delete_row": ("table_id", "row_id"),
}


def _strip_formula_prefix(value: str) -> str:
    """
    Strip the ``$formula:`` prefix if present, returning the inner formula.

    The LLM sometimes adds the prefix to values that are already valid formulas
    (e.g. ``$formula: get('current_record.id')``). In contexts where the value
    is used directly (not routed through formula generation), we strip the
    prefix so the underlying formula is used as-is.
    """

    if needs_formula(value):
        return formula_desc(value)
    return value


# ---------------------------------------------------------------------------
# ORM dispatch: action_type -> kwargs builder
# ---------------------------------------------------------------------------


def _notification_orm_kwargs(action: "ActionCreate") -> dict:
    return {
        "title": BaserowFormulaObject.create(
            literal_or_placeholder(action.title),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        ),
        "description": BaserowFormulaObject.create(
            literal_or_placeholder(action.description),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        ),
    }


def _open_page_orm_kwargs(action: "ActionCreate") -> dict:
    return {
        "navigation_type": "page",
        "navigate_to_page_id": action.navigate_to_page_id,
        "page_parameters": [
            {
                "name": p.name,
                "value": BaserowFormulaObject.create(
                    literal_or_placeholder(p.value),
                    mode=BASEROW_FORMULA_MODE_ADVANCED,
                ),
            }
            for p in (action.page_parameters or [])
        ],
        "query_parameters": [
            {
                "name": p.name,
                "value": BaserowFormulaObject.create(
                    literal_or_placeholder(p.value),
                    mode=BASEROW_FORMULA_MODE_ADVANCED,
                ),
            }
            for p in (action.query_parameters or [])
        ],
        "target": action.target,
    }


def _refresh_ds_orm_kwargs(action: "ActionCreate") -> dict:
    if isinstance(action.data_source, int):
        return {"data_source_id": action.data_source}
    return {}


_TO_ORM_KWARGS: dict[str, Any] = {
    "notification": _notification_orm_kwargs,
    "open_page": _open_page_orm_kwargs,
    "refresh_data_source": _refresh_ds_orm_kwargs,
    "logout": lambda _: {},
}

# ---------------------------------------------------------------------------
# Service type dispatch
# ---------------------------------------------------------------------------

_SERVICE_TYPE: dict[str, str | None] = {
    "notification": None,
    "open_page": None,
    "create_row": "local_baserow_upsert_row",
    "update_row": "local_baserow_upsert_row",
    "delete_row": "local_baserow_delete_row",
    "refresh_data_source": None,
    "logout": None,
}


def _row_service_kwargs(action: "ActionCreate", user, workspace) -> dict:
    """Build service kwargs for row-based actions (create/update/delete)."""

    from baserow_enterprise.assistant.tools.builder.helpers import ToolInputError
    from baserow_enterprise.assistant.tools.database.helpers import filter_tables

    table = filter_tables(user, workspace).filter(id=action.table_id).first()
    if table is None:
        raise ToolInputError(f"Table with id {action.table_id} not found.")
    kwargs: dict[str, Any] = {"table": table}

    if action.type in ("update_row", "delete_row") and action.row_id:
        kwargs["row_id"] = BaserowFormulaObject.create(
            _strip_formula_prefix(action.row_id),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )

    return kwargs


# ---------------------------------------------------------------------------
# Field mapping dispatch
# ---------------------------------------------------------------------------


def _field_mappings(action: "ActionCreate") -> list[dict] | None:
    """Build field mappings for create/update row actions."""

    if action.type not in ("create_row", "update_row") or not action.field_values:
        return None

    mappings = []
    for fv in action.field_values:
        if needs_formula(fv.value):
            formula_value = "''"
        else:
            formula_value = fv.value
        mappings.append(
            {
                "field_id": int(fv.field_id),
                "value": BaserowFormulaObject.create(
                    formula_value, mode=BASEROW_FORMULA_MODE_ADVANCED
                ),
                "enabled": True,
            }
        )
    return mappings


# ---------------------------------------------------------------------------
# Formula dispatch: get_formulas_to_create
# ---------------------------------------------------------------------------


def _row_formulas(action: "ActionCreate", orm_action, context) -> dict[str, str]:
    """Get formulas for create_row / update_row / delete_row actions."""

    formulas: dict[str, str] = {}

    # Row ID for update/delete
    if action.type in ("update_row", "delete_row") and action.row_id:
        if needs_formula(action.row_id):
            formulas["row_id"] = formula_desc(action.row_id)

    # Field values for create/update
    if action.field_values:
        for fv in action.field_values:
            if needs_formula(fv.value):
                formulas[f"field_{fv.field_id}"] = formula_desc(fv.value)

    return formulas


def _open_page_formulas(action: "ActionCreate", orm_action, context) -> dict[str, str]:
    """Get formulas for open_page page/query parameters."""

    formulas: dict[str, str] = {}
    for i, p in enumerate(action.page_parameters or []):
        if needs_formula(p.value):
            formulas[f"page_param_{i}"] = formula_desc(p.value)
    for i, p in enumerate(action.query_parameters or []):
        if needs_formula(p.value):
            formulas[f"query_param_{i}"] = formula_desc(p.value)
    return formulas


_GET_FORMULAS: dict[str, Any] = {
    "create_row": _row_formulas,
    "update_row": _row_formulas,
    "delete_row": _row_formulas,
    "open_page": _open_page_formulas,
}

# ---------------------------------------------------------------------------
# Formula dispatch: update_action_with_formulas
# ---------------------------------------------------------------------------


def _update_row_formulas(
    action: "ActionCreate",
    orm_action: "BuilderWorkflowAction",
    formulas: dict[str, str],
) -> None:
    """Apply generated formulas to row-based workflow actions."""

    if not formulas:
        return

    service = orm_action.specific.service.specific

    # Update row_id
    if "row_id" in formulas:
        service.row_id = BaserowFormulaObject.create(
            formulas["row_id"], mode=BASEROW_FORMULA_MODE_ADVANCED
        )
        service.save(update_fields=["row_id"])

    # Update field mappings
    for mapping in service.field_mappings.all():
        key = f"field_{mapping.field_id}"
        if key in formulas:
            mapping.value = BaserowFormulaObject.create(
                formulas[key], mode=BASEROW_FORMULA_MODE_ADVANCED
            )
            mapping.save(update_fields=["value"])


def _update_open_page_formulas(
    action: "ActionCreate",
    orm_action: "BuilderWorkflowAction",
    formulas: dict[str, str],
) -> None:
    """Apply generated formulas to open_page page/query parameters."""

    if not formulas:
        return

    specific = orm_action.specific
    page_params = specific.page_parameters or []
    query_params = specific.query_parameters or []

    for i, p in enumerate(page_params):
        key = f"page_param_{i}"
        if key in formulas:
            p["value"] = BaserowFormulaObject.create(
                formulas[key], mode=BASEROW_FORMULA_MODE_ADVANCED
            )

    for i, p in enumerate(query_params):
        key = f"query_param_{i}"
        if key in formulas:
            p["value"] = BaserowFormulaObject.create(
                formulas[key], mode=BASEROW_FORMULA_MODE_ADVANCED
            )

    specific.page_parameters = page_params
    specific.query_parameters = query_params
    specific.save(update_fields=["page_parameters", "query_parameters"])


_UPDATE_FORMULAS: dict[str, Any] = {
    "create_row": _update_row_formulas,
    "update_row": _update_row_formulas,
    "delete_row": _update_row_formulas,
    "open_page": _update_open_page_formulas,
}


# ---------------------------------------------------------------------------
# ActionCreate (flat)
# ---------------------------------------------------------------------------


class ActionCreate(BaseModel):
    """
    Flat model for creating a workflow action.

    All type-specific fields are optional — a ``@model_validator``
    enforces the correct required fields per type.
    """

    type: ActionType = Field(..., description="Action type.")

    element: int | str = Field(
        ...,
        description="Element this action is attached to: int ID (existing) or string ref (same batch).",
    )
    event: str = Field(
        default="click",
        description="Event that triggers the action: click, submit, after_login.",
    )

    # notification
    title: str | None = Field(default=None, description="(notification) Title formula.")
    description: str | None = Field(
        default=None, description="(notification) Message formula."
    )

    # open_page
    navigate_to_page_id: int | None = Field(
        default=None, description="(open_page) Target page ID."
    )
    page_parameters: list[ParameterMapping] | None = Field(
        default=None, description="(open_page) Page parameter mappings."
    )
    query_parameters: list[ParameterMapping] | None = Field(
        default=None, description="(open_page) Query parameter mappings."
    )
    target: Literal["self", "blank"] = Field(
        default="self", description="(open_page) Navigation target."
    )

    # create_row / update_row / delete_row
    table_id: int | None = Field(
        default=None, description="(row actions) Target table ID."
    )
    row_id: str | None = Field(
        default=None,
        description="(update_row, delete_row) Row ID formula. Supports $formula: prefix.",
    )
    field_values: list[FieldValueMapping] | None = Field(
        default=None,
        description="(create_row, update_row) Field value mappings. Supports $formula: prefix.",
    )

    # refresh_data_source
    data_source: int | str | None = Field(
        default=None,
        description="(refresh_data_source) Data source: int ID or string ref.",
    )

    @model_validator(mode="after")
    def _check_required(self):
        for field_name in _REQUIRED_FIELDS.get(self.type, ()):
            if getattr(self, field_name) is None:
                raise ValueError(f"'{field_name}' is required for type '{self.type}'.")
        return self

    # -- ORM helpers --------------------------------------------------------

    def get_action_type(self) -> str:
        """Return the action type string."""
        return self.type

    def get_service_type(self) -> str | None:
        """Return the service type string, or None for non-service actions."""
        return _SERVICE_TYPE.get(self.type)

    def to_orm_kwargs(self) -> dict:
        """Return non-service kwargs for action creation."""
        fn = _TO_ORM_KWARGS.get(self.type)
        return fn(self) if fn else {}

    def to_service_kwargs(self, user, workspace) -> dict | None:
        """Return service kwargs for service-based actions."""
        if self.get_service_type() is None:
            return None
        return _row_service_kwargs(self, user, workspace)

    def get_field_mappings(self) -> list[dict] | None:
        """Return field mappings for service-based actions."""
        return _field_mappings(self)

    # -- Formula helpers ----------------------------------------------------

    def get_formulas_to_create(
        self,
        orm_action: "BuilderWorkflowAction",
        context: "BuilderFormulaContext",
    ) -> dict[str, str]:
        """Return ``{field_path: description}`` for LLM formula generation."""
        fn = _GET_FORMULAS.get(self.type)
        return fn(self, orm_action, context) if fn else {}

    def update_with_formulas(
        self,
        orm_action: "BuilderWorkflowAction",
        formulas: dict[str, str],
    ) -> None:
        """Apply LLM-generated formulas to this action."""
        fn = _UPDATE_FORMULAS.get(self.type)
        if fn:
            fn(self, orm_action, formulas)


# ---------------------------------------------------------------------------
# ActionItem (for listing)
# ---------------------------------------------------------------------------


class FieldMappingItem(BaseModel):
    """Field mapping for create_row/update_row workflow actions."""

    field_id: int
    field_name: str
    value: str


class ActionItem(BaseModel):
    """Existing workflow action with ID."""

    id: int
    type: str
    element_id: int | None = None
    event: str = "click"
    table_id: int | None = None
    row_id_formula: str | None = None
    field_mappings: list[FieldMappingItem] | None = None

    @classmethod
    def from_orm(cls, action) -> "ActionItem":
        """Create ActionItem from ORM BuilderWorkflowAction instance."""

        action_type = action.get_type().type
        kwargs: dict[str, Any] = {
            "id": action.id,
            "type": action_type,
            "element_id": action.element_id,
            "event": action.event,
        }

        specific = action.specific

        if action_type in ("create_row", "update_row", "delete_row"):
            if hasattr(specific, "service") and specific.service:
                service = specific.service.specific
                if hasattr(service, "table") and service.table:
                    kwargs["table_id"] = service.table_id
                if hasattr(service, "row_id") and service.row_id:
                    kwargs["row_id_formula"] = str(service.row_id)
                if action_type in ("create_row", "update_row"):
                    if hasattr(service, "field_mappings"):
                        mappings = [
                            FieldMappingItem(
                                field_id=m.field_id,
                                field_name=m.field.name,
                                value=str(m.value) if m.value else "",
                            )
                            for m in service.field_mappings.all()
                        ]
                        if mappings:
                            kwargs["field_mappings"] = mappings

        return cls(**kwargs)
