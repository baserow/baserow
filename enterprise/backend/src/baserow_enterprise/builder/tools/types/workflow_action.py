"""
Builder workflow action type models.

Defines ``ActionCreate`` (flat) for creating workflow actions and
``ActionItem`` for reading them back.
"""

import re
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, field_validator, model_validator

from baserow.core.formula.parser.exceptions import BaserowFormulaException
from baserow.core.formula.parser.generated.BaserowFormula import BaserowFormula
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
from baserow.core.tools.errors import ToolInputError
from baserow_enterprise.tools.formula_utils import (
    EMPTY_FORMULA,
    formula_desc,
    formula_object,
    formula_text,
    literal_or_placeholder,
    needs_formula,
)
from baserow_enterprise.tools.types import BaseModel

from .limits import MAX_NESTED_ITEMS

if TYPE_CHECKING:
    from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
    from baserow_enterprise.builder.tools.formulas import BuilderFormulaContext

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
    """Key-value parameter mapping for page/query parameters of an action or link."""

    name: str = Field(..., description="Parameter name.")
    value: str = Field(..., description="Parameter value formula.")


class FieldValueMapping(BaseModel):
    """Field-value mapping for row create/update actions."""

    field_id: str = Field(..., description="The field ID (as string).")
    value: str = Field(
        ...,
        description=(
            "A formula: see the tool description. Quote fixed text: 'like this'."
        ),
    )

    @field_validator("field_id")
    @classmethod
    def _strip_field_id(cls, value: str) -> str:
        return value.strip()


# ---------------------------------------------------------------------------
# Required fields per action type
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "notification": ("title",),
    "open_page": ("navigate_to_page_id",),
    "create_row": ("table_id", "field_values"),
    "update_row": ("table_id", "row_id", "field_values"),
    "delete_row": ("table_id", "row_id"),
    "refresh_data_source": ("data_source",),
}

# What ``update_action`` can change on each type of action.
_CHANGEABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "notification": ("title", "description"),
    "open_page": (
        "navigate_to_page_id",
        "page_parameters",
        "query_parameters",
        "target",
    ),
    "create_row": ("table_id", "field_values"),
    "update_row": ("table_id", "row_id", "field_values"),
    "delete_row": ("table_id", "row_id"),
    "refresh_data_source": ("data_source",),
    "logout": (),
}

# Fields that carry a database ID when given as an int; refs stay strings.
_ID_FIELDS: tuple[str, ...] = (
    "element",
    "navigate_to_page_id",
    "table_id",
    "data_source",
)


_NUMBER_OR_BOOLEAN_RE = re.compile(
    r"-?(?:0|[1-9]\d*)(?:\.\d*[1-9])?|true|false", re.IGNORECASE
)


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


def _is_function_call(value: str | None) -> bool:
    """Whether the whole value is one call to a function the formulas have."""

    if not value or not value.strip():
        return False
    try:
        expr = get_parse_tree_for_formula(value.strip()).expr()
    except (BaserowFormulaException, RecursionError):
        return False
    if not isinstance(expr, BaserowFormula.FunctionCallContext):
        return False
    name = expr.func_name().getText().lower()
    return name in formula_runtime_function_registry.get_types()


def is_text_formula(value: str | None) -> bool:
    """
    Whether a title, description or parameter is a formula. It also counts when the
    whole value is a function call, since a list_actions value like ``upper('abc')``
    is sent back.
    """

    return needs_formula(value) or _is_function_call(value)


def mapping_value_is_formula(value: str) -> bool:
    """
    Whether a field value or link parameter goes through the formula step. A number
    or boolean counts, as a field can need the type, unless a formula would show it
    differently, like ``007``. Sums like ``3/4`` are fixed text.
    """

    return is_text_formula(value) or bool(
        _NUMBER_OR_BOOLEAN_RE.fullmatch(value.strip())
    )


def text_or_placeholder(value: str | None) -> str:
    """The quoted text, or an empty placeholder for a formula the formula step stores."""

    return EMPTY_FORMULA if is_text_formula(value) else literal_or_placeholder(value)


# ---------------------------------------------------------------------------
# ORM dispatch: action_type -> kwargs builder
# ---------------------------------------------------------------------------


def _notification_orm_kwargs(action: "ActionCreate") -> dict:
    return {
        "title": formula_object(
            text_or_placeholder(action.title),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        ),
        "description": formula_object(
            text_or_placeholder(action.description),
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
                "value": formula_object(
                    text_or_placeholder(p.value),
                    mode=BASEROW_FORMULA_MODE_ADVANCED,
                ),
            }
            for p in (action.page_parameters or [])
        ],
        "query_parameters": [
            {
                "name": p.name,
                "value": formula_object(
                    text_or_placeholder(p.value),
                    mode=BASEROW_FORMULA_MODE_ADVANCED,
                ),
            }
            for p in (action.query_parameters or [])
        ],
        "target": action.target,
    }


_TO_ORM_KWARGS: dict[str, Any] = {
    "notification": _notification_orm_kwargs,
    "open_page": _open_page_orm_kwargs,
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


def _row_action_table(action: "ActionCreate", user, workspace) -> Any:
    """
    The table a row action writes to.

    :raises ToolInputError: When the table does not exist, or a field the action
        names isn't in it.
    """

    from baserow.contrib.database.mcp.services import filter_tables

    table = filter_tables(user, workspace).filter(id=action.table_id).first()
    if table is None:
        raise ToolInputError(f"Table with id {action.table_id} not found.")

    field_ids = {fv.field_id for fv in action.field_values or []}
    in_table = {str(id) for id in table.field_set.values_list("id", flat=True)}
    if field_ids - in_table:
        raise ToolInputError(
            f"Field {sorted(field_ids - in_table)[0]} is not in the table this action "
            "writes to. Use the IDs of that table's fields."
        )
    return table


def _row_service_kwargs(action: "ActionCreate", user, workspace) -> dict:
    """
    Build service kwargs for row-based actions (create/update/delete).

    :raises ToolInputError: When the referenced table does not exist.
    """

    kwargs: dict[str, Any] = {"table": _row_action_table(action, user, workspace)}

    if action.type in ("update_row", "delete_row") and action.row_id:
        kwargs["row_id"] = formula_object(
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

    # A formula is added by the formula step once it passes, so a refused one writes
    # nothing to its field. Anything else is fixed text.
    return [
        {
            "field_id": int(fv.field_id),
            "value": _advanced(literal_or_placeholder(fv.value)),
            "enabled": True,
        }
        for fv in action.field_values
        if not mapping_value_is_formula(fv.value)
    ]


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
            key = f"field_{fv.field_id}"
            if mapping_value_is_formula(fv.value):
                formulas[key] = formula_desc(fv.value)

    return formulas


def _open_page_formulas(action: "ActionCreate", orm_action, context) -> dict[str, str]:
    """Get formulas for open_page page/query parameters."""

    formulas: dict[str, str] = {}
    for i, p in enumerate(action.page_parameters or []):
        if is_text_formula(p.value):
            formulas[f"page_param_{i}"] = formula_desc(p.value)
    for i, p in enumerate(action.query_parameters or []):
        if is_text_formula(p.value):
            formulas[f"query_param_{i}"] = formula_desc(p.value)
    return formulas


def _notification_formulas(
    action: "ActionCreate", orm_action, context
) -> dict[str, str]:
    """Get formulas for a notification's title and description."""

    return {
        name: formula_desc(value)
        for name, value in [
            ("title", action.title),
            ("description", action.description),
        ]
        if value and is_text_formula(value)
    }


_GET_FORMULAS: dict[str, Any] = {
    "notification": _notification_formulas,
    "create_row": _row_formulas,
    "update_row": _row_formulas,
    "delete_row": _row_formulas,
    "open_page": _open_page_formulas,
}

# ---------------------------------------------------------------------------
# Formula dispatch: values to update an action with its generated formulas
# ---------------------------------------------------------------------------


def _advanced(formula: str) -> Any:
    return formula_object(formula, mode=BASEROW_FORMULA_MODE_ADVANCED)


def _row_formula_values(
    action: "ActionCreate",
    orm_action: "BuilderWorkflowAction",
    formulas: dict[str, str],
) -> dict[str, Any]:
    """The service values that apply generated formulas to a row action."""

    service = orm_action.specific.service.specific
    service_values: dict[str, Any] = {}
    if "row_id" in formulas:
        service_values["row_id"] = _advanced(formulas["row_id"])

    mappings = []
    for mapping in service.field_mappings.all():
        formula = formulas.get(f"field_{mapping.field_id}")
        mappings.append(
            {
                "field_id": mapping.field_id,
                "enabled": mapping.enabled,
                "value": mapping.value if formula is None else _advanced(formula),
            }
        )
    # An update can name a field the action doesn't write to yet.
    mapped = {mapping["field_id"] for mapping in mappings}
    for field_value in action.field_values or []:
        field_id = int(field_value.field_id)
        formula = formulas.get(f"field_{field_value.field_id}")
        if formula is not None and field_id not in mapped:
            mapped.add(field_id)
            mappings.append(
                {"field_id": field_id, "enabled": True, "value": _advanced(formula)}
            )
    # The service replaces its whole list of mappings.
    if any(f"field_{mapping['field_id']}" in formulas for mapping in mappings):
        service_values["field_mappings"] = mappings
    return {"service": service_values} if service_values else {}


def _open_page_formula_values(
    action: "ActionCreate",
    orm_action: "BuilderWorkflowAction",
    formulas: dict[str, str],
) -> dict[str, Any]:
    """The values that apply generated formulas to open_page parameters."""

    specific = orm_action.specific
    values: dict[str, Any] = {}
    for field, prefix in (
        ("page_parameters", "page_param"),
        ("query_parameters", "query_param"),
    ):
        params = [dict(param) for param in getattr(specific, field) or []]
        changed = False
        for i, param in enumerate(params):
            formula = formulas.get(f"{prefix}_{i}")
            if formula is not None:
                param["value"] = _advanced(formula)
                changed = True
        if changed:
            values[field] = params
    return values


def _notification_formula_values(
    action: "ActionCreate",
    orm_action: "BuilderWorkflowAction",
    formulas: dict[str, str],
) -> dict[str, Any]:
    """The values that apply generated formulas to a notification."""

    return {
        name: _advanced(formulas[name])
        for name in ("title", "description")
        if name in formulas
    }


_FORMULA_VALUES: dict[str, Any] = {
    "notification": _notification_formula_values,
    "create_row": _row_formula_values,
    "update_row": _row_formula_values,
    "delete_row": _row_formula_values,
    "open_page": _open_page_formula_values,
}


# ---------------------------------------------------------------------------
# ActionCreate (flat)
# ---------------------------------------------------------------------------


class ActionCreate(BaseModel):
    """
    One workflow action, attached to an element (event "click"), a table button
    column (event "<column name>_click"), or a form container (event "submit").

    ``type`` and ``element`` are always required. Each type also needs:
    - notification: title
    - open_page: navigate_to_page_id
    - create_row: table_id, field_values
    - update_row: table_id, row_id, field_values
    - delete_row: table_id, row_id
    - refresh_data_source: data_source
    - logout: nothing more

    Send all of them in the same call: a call missing any of them is rejected
    in full, and every retry costs a round trip. Numeric IDs must come from a
    tool result; string refs must name an item created in this same call.

    The tag in parentheses on a field description names the types that field
    applies to; leave every other field unset. No key outside this model is
    accepted.

    open_page navigates to a page of this application only — no action opens
    an external URL. External navigation is a property of the link element
    (navigation_type, navigate_to_url, link_variant), not of an action.
    """

    type: ActionType = Field(..., description="Action type.")

    element: int | str = Field(
        ...,
        description="Element this action is attached to: int ID (existing) or string ref (same batch).",
    )
    event: str = Field(
        default="click",
        description=(
            "Event that triggers the action: click for standalone buttons/links, "
            "submit for forms, after_login for login forms. Table button columns: "
            "use '<column name>_click' (e.g. 'Edit_click') or '<uid>_click' with the "
            "column uid from list_elements. Bare click is valid only with one button "
            "column; duplicate column names require the uid event."
        ),
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
        max_length=MAX_NESTED_ITEMS,
        default=None,
        description=(
            "(open_page) Page parameter mappings: exactly the path parameters of "
            "the target page."
        ),
    )
    query_parameters: list[ParameterMapping] | None = Field(
        max_length=MAX_NESTED_ITEMS,
        default=None,
        description="(open_page) Query parameter mappings.",
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
        description="(update_row, delete_row) Row ID formula. Can be a formula: see the tool description.",
    )
    field_values: list[FieldValueMapping] | None = Field(
        max_length=MAX_NESTED_ITEMS,
        default=None,
        description="(create_row, update_row) Field value mappings. Can be a formula: see the tool description.",
    )

    # refresh_data_source
    data_source: int | str | None = Field(
        default=None,
        description="(refresh_data_source) Data source: int ID or string ref.",
    )

    @model_validator(mode="after")
    def _check_required(self) -> "ActionCreate":
        required = _REQUIRED_FIELDS.get(self.type, ())
        missing = [
            name
            for name in required
            if getattr(self, name) is None
            or (
                name in ("row_id", "data_source")
                and isinstance(getattr(self, name), str)
                and not getattr(self, name).strip()
            )
        ]
        if missing:
            raise ValueError(
                f"Type '{self.type}' requires all of: {', '.join(required)}. "
                f"Missing: {', '.join(missing)}. Send every required field in a "
                f"single call. If a value is not known yet, create or look up the "
                f"resource it refers to first, or choose a type that does not "
                f"require it."
            )
        for name in _ID_FIELDS:
            value = getattr(self, name, None)
            if isinstance(value, int) and value <= 0:
                raise ValueError(
                    f"'{name}' is {value}, which is never a valid ID. Use an ID "
                    f"returned by an earlier tool result, or a string ref to an "
                    f"item created in this same call."
                )
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

    def get_required_formulas(self) -> dict[str, str]:
        """Return the formulas this action can't run without."""

        if self.type not in ("update_row", "delete_row") or not self.row_id:
            return {}
        return {"row_id": _strip_formula_prefix(self.row_id)}

    def formula_values(
        self,
        orm_action: "BuilderWorkflowAction",
        formulas: dict[str, str],
    ) -> dict[str, Any]:
        """
        The values to update ``orm_action`` with, through its action type, to apply
        the generated formulas.
        """

        fn = _FORMULA_VALUES.get(self.type)
        return fn(self, orm_action, formulas) if fn and formulas else {}


# ---------------------------------------------------------------------------
# Changes to an existing action
# ---------------------------------------------------------------------------


def _notification_update_values(
    action: "ActionUpdate", orm_action: "BuilderWorkflowAction"
) -> dict[str, Any]:
    return {
        name: _advanced(literal_or_placeholder(value))
        for name, value in [
            ("title", action.title),
            ("description", action.description),
        ]
        if value is not None and not is_text_formula(value)
    }


def _parameters_update_values(
    params: list[ParameterMapping], stored: list[dict] | None
) -> list[dict]:
    """A value still to be checked keeps the one its parameter has until it passes."""

    stored_values = {param["name"]: param["value"] for param in stored or []}
    return [
        {
            "name": param.name,
            "value": (
                stored_values.get(param.name, _advanced(EMPTY_FORMULA))
                if is_text_formula(param.value)
                else _advanced(literal_or_placeholder(param.value))
            ),
        }
        for param in params
    ]


def _open_page_update_values(
    action: "ActionUpdate", orm_action: "BuilderWorkflowAction"
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if action.navigate_to_page_id is not None:
        values["navigation_type"] = "page"
        values["navigate_to_page_id"] = action.navigate_to_page_id
    if action.target is not None:
        values["target"] = action.target
    for field in ("page_parameters", "query_parameters"):
        params = getattr(action, field)
        if params is not None:
            values[field] = _parameters_update_values(
                params, getattr(orm_action, field)
            )
    return values


def _row_update_values(
    action: "ActionUpdate", orm_action: "BuilderWorkflowAction", user, workspace
) -> dict[str, Any]:
    """Row values all go through the formula step, so only the table is left here."""

    if action.table_id is None and not action.field_values:
        return {}
    service = orm_action.service.specific
    table_id = action.table_id or service.table_id
    if table_id is None:
        raise ToolInputError(
            f"Action {orm_action.id} has no table selected. Give table_id as well."
        )
    table = _row_action_table(
        action.model_copy(update={"table_id": table_id}), user, workspace
    )
    if table_id == service.table_id:
        return {}
    service_values: dict[str, Any] = {"table": table}
    # What the action wrote to the old table doesn't apply to the new one.
    if action.type != "delete_row":
        service_values["field_mappings"] = []
    return {"service": service_values}


class ActionUpdate(ActionCreate):
    """
    An existing action with the values to change, for the formula step. Made by
    ``ActionChanges.for_action``, without the checks of a complete new action. A value
    left out is None.
    """

    def get_formulas_to_create(
        self,
        orm_action: "BuilderWorkflowAction",
        context: "BuilderFormulaContext",
    ) -> dict[str, str]:
        """A new row_id or field value has to be a formula, whatever it looks like."""

        return {
            **super().get_formulas_to_create(orm_action, context),
            **self.get_required_formulas(),
            **{
                f"field_{field_value.field_id}": _strip_formula_prefix(
                    field_value.value
                )
                for field_value in self.field_values or []
            },
        }

    def update_values(
        self, orm_action: "BuilderWorkflowAction", user, workspace
    ) -> dict[str, Any]:
        """The values to change that the formula step doesn't store."""

        if self.type == "notification":
            return _notification_update_values(self, orm_action)
        if self.type == "open_page":
            return _open_page_update_values(self, orm_action)
        if self.type == "refresh_data_source":
            return {"data_source_id": self.data_source}
        if self.get_service_type() is not None:
            return _row_update_values(self, orm_action, user, workspace)
        return {}


class ActionChanges(BaseModel):
    """
    The values to change on a workflow action. Set only what should change, and only
    what its type takes:
    - notification: title, description
    - open_page: navigate_to_page_id, page_parameters, query_parameters, target
    - create_row: table_id, field_values
    - update_row: table_id, row_id, field_values
    - delete_row: table_id, row_id
    - refresh_data_source: data_source

    Its type, element and event can't be changed.
    """

    title: str | None = Field(default=None, description="(notification) Title formula.")
    description: str | None = Field(
        default=None, description="(notification) Message formula."
    )
    navigate_to_page_id: int | None = Field(
        default=None, description="(open_page) Target page ID."
    )
    page_parameters: list[ParameterMapping] | None = Field(
        max_length=MAX_NESTED_ITEMS,
        default=None,
        description="(open_page) Page parameter mappings. Replaces the whole list.",
    )
    query_parameters: list[ParameterMapping] | None = Field(
        max_length=MAX_NESTED_ITEMS,
        default=None,
        description="(open_page) Query parameter mappings. Replaces the whole list.",
    )
    target: Literal["self", "blank"] | None = Field(
        default=None, description="(open_page) Navigation target."
    )
    table_id: int | None = Field(
        default=None,
        description=(
            "(row actions) Target table ID. Moving to another table: the field "
            "values are cleared, so send the new ones with it, and row_id stays and "
            "now points into the new table."
        ),
    )
    row_id: str | None = Field(
        default=None, description="(update_row, delete_row) Row ID formula."
    )
    field_values: list[FieldValueMapping] | None = Field(
        max_length=MAX_NESTED_ITEMS,
        default=None,
        description=(
            "(create_row, update_row) Field value formulas. Fields not named here "
            "keep their value."
        ),
    )
    data_source: int | None = Field(
        default=None, description="(refresh_data_source) Data source ID."
    )

    @model_validator(mode="after")
    def _check_values(self) -> "ActionChanges":
        if self.row_id is not None and not self.row_id.strip():
            raise ValueError("'row_id' can't be empty. Leave it out to keep it.")
        for name in _ID_FIELDS:
            value = getattr(self, name, None)
            if isinstance(value, int) and value <= 0:
                raise ValueError(
                    f"'{name}' is {value}, which is never a valid ID. Use an ID "
                    "returned by an earlier tool result."
                )
        return self

    def for_action(self, orm_action: "BuilderWorkflowAction") -> ActionUpdate:
        """
        These changes as the item the formula step and the action writer work with.

        :raises ToolInputError: When there is nothing to change, or the action's type
            doesn't take a value or can't be changed.
        """

        action_type = orm_action.get_type().type
        changeable = _CHANGEABLE_FIELDS.get(action_type)
        if changeable is None:
            raise ToolInputError(
                f"A '{action_type}' action can't be changed with this tool."
            )
        given = [
            name for name in type(self).model_fields if getattr(self, name) is not None
        ]
        if not given:
            raise ToolInputError("There is nothing to change: give a value to change.")
        wrong = [name for name in given if name not in changeable]
        if wrong:
            raise ToolInputError(
                f"{', '.join(wrong)} can't be set on a {action_type} action. It takes: "
                f"{', '.join(changeable) or 'nothing'}."
            )
        if given == ["field_values"] and not self.field_values:
            raise ToolInputError(
                "There is nothing to change: field_values is empty. Name the fields "
                "to set."
            )
        # Every value is set, so ``target`` doesn't take its default for a new action.
        values = {name: getattr(self, name) for name in type(self).model_fields}
        return ActionUpdate.model_construct(
            type=action_type,
            element=orm_action.element_id,
            event=orm_action.event,
            **values,
        )


# ---------------------------------------------------------------------------
# ActionItem (for listing)
# ---------------------------------------------------------------------------


def _parameter_items(parameters: list[dict] | None) -> list["ParameterMapping"]:
    return [
        ParameterMapping(name=p["name"], value=formula_text(p.get("value")))
        for p in parameters or []
    ]


class FieldMappingItem(BaseModel):
    """Field mapping for create_row/update_row workflow actions."""

    field_id: int
    field_name: str
    value: str


class ActionItem(BaseModel):
    """
    Existing workflow action with ID. The values are what ``create_actions`` and
    ``update_action`` take, formulas as plain strings, and only the ones of the
    action's type are set.
    """

    id: int
    type: str
    element_id: int | None = None
    event: str = "click"
    title: str | None = None
    description: str | None = None
    navigation_type: str | None = None
    navigate_to_page_id: int | None = None
    target: str | None = None
    page_parameters: list[ParameterMapping] | None = None
    query_parameters: list[ParameterMapping] | None = None
    data_source_id: int | None = None
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

        if action_type == "notification":
            kwargs["title"] = formula_text(specific.title)
            kwargs["description"] = formula_text(specific.description)
        elif action_type == "open_page":
            kwargs["navigation_type"] = specific.navigation_type
            kwargs["navigate_to_page_id"] = specific.navigate_to_page_id
            kwargs["target"] = specific.target
            kwargs["page_parameters"] = _parameter_items(specific.page_parameters)
            kwargs["query_parameters"] = _parameter_items(specific.query_parameters)
        elif action_type == "refresh_data_source":
            kwargs["data_source_id"] = specific.data_source_id

        if action_type in ("create_row", "update_row", "delete_row"):
            if hasattr(specific, "service") and specific.service:
                service = specific.service.specific
                if hasattr(service, "table") and service.table:
                    kwargs["table_id"] = service.table_id
                if hasattr(service, "row_id") and service.row_id:
                    kwargs["row_id_formula"] = formula_text(service.row_id)
                if action_type in ("create_row", "update_row"):
                    if hasattr(service, "field_mappings"):
                        mappings = [
                            FieldMappingItem(
                                field_id=m.field_id,
                                field_name=m.field.name,
                                value=formula_text(m.value),
                            )
                            for m in service.field_mappings.all()
                        ]
                        if mappings:
                            kwargs["field_mappings"] = mappings

        return cls(**kwargs)
