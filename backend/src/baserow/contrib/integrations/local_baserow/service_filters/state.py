"""
The filter state of a Local Baserow service, the operations that change it, and the
validation of the result.

Everything here is pure Python working on data loaded up-front, so it can validate
changes repeatedly, e.g. while a model retries, without touching the database.
"""

from dataclasses import dataclass, replace
from typing import Any, Callable, Literal

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, model_validator

from baserow.contrib.database.fields.models import Field as DatabaseField
from baserow.contrib.database.views.registries import view_filter_type_registry
from baserow.contrib.database.views.view_filters import (
    BaseDateMultiStepViewFilterType,
    DateEqualsDayOfMonthViewFilterType,
    TimezoneAwareDateViewFilterType,
)
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableServiceFilter,
)
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_ADVANCED,
    BASEROW_FORMULA_MODE_RAW,
    BaserowFormulaObject,
)
from baserow.core.services.models import SERVICE_FILTER_TYPE_AND


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)


FilterTypeLiteral = Literal["AND", "OR"]

# Filter types which don't compare the field against a value.
VALUELESS_FILTER_TYPES = {
    "empty",
    "not_empty",
    "is_even_and_whole",
    "has_empty_value",
    "has_not_empty_value",
}

SELECT_OPTION_FILTER_TYPES = {
    "single_select_equal",
    "single_select_not_equal",
    "single_select_is_any_of",
    "single_select_is_none_of",
    "multiple_select_has",
    "multiple_select_has_not",
    "has_any_select_option_equal",
    "has_none_select_option_equal",
}

NUMBER_FILTER_TYPES = {
    "higher_than",
    "higher_than_or_equal",
    "lower_than",
    "lower_than_or_equal",
    "length_is_lower_than",
    "files_lower_than",
    "link_row_has",
    "link_row_has_not",
}

BOOLEAN_VALUES = {"1", "0", "true", "false"}


class ServiceFilterValidationError(Exception):
    """Raised with every problem found in the agent's changes."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


class FilterOperation(BaseModel):
    """
    One change to the filters. A flat model (rather than a union per operation)
    keeps the schema simple for every model provider.
    """

    op: Literal[
        "add_filter",
        "update_filter",
        "delete_filter",
        "add_group",
        "update_group",
        "delete_group",
        "set_filter_type",
    ] = Field(description="The kind of change.")
    filter_id: str | None = Field(
        default=None,
        description="update_filter/delete_filter: the id of an existing filter.",
    )
    group_id: str | None = Field(
        default=None,
        description=(
            "update_group/delete_group: the id of an existing group. add_group: a "
            "new unique reference for the group, e.g. 'new_group_1', which "
            "add_filter and add_group can use in `group` / `parent_group`."
        ),
    )
    field_id: int | None = Field(
        default=None,
        description="add_filter (required) / update_filter: the field to filter on.",
    )
    type: str | None = Field(
        default=None,
        description=(
            "add_filter (required) / update_filter: the filter type. Must be one of "
            "the filter types compatible with the field."
        ),
    )
    value: str | None = Field(
        default=None,
        description=(
            "add_filter / update_filter: the value to compare against, in the format "
            "the filter type expects, or a formula when `value_is_formula` is true. "
            "Leave empty for filter types without a value."
        ),
    )
    value_is_formula: bool | None = Field(
        default=None,
        description=(
            "add_filter / update_filter: true when `value` is a formula computing "
            "the value, e.g. get('page_parameter.id'). Defaults to false."
        ),
    )
    group: str | None = Field(
        default=None,
        description=(
            "add_filter / update_filter: the id or new reference of the group the "
            "filter belongs to. Null for a filter at the top level."
        ),
    )
    parent_group: str | None = Field(
        default=None,
        description=(
            "add_group: the id or new reference of the group to nest the new group "
            "in. Null for a group at the top level."
        ),
    )
    filter_type: FilterTypeLiteral | None = Field(
        default=None,
        description=(
            "add_group (required) / update_group (required) / set_filter_type "
            "(required): whether all (AND) or any (OR) of the conditions must match."
        ),
    )

    @model_validator(mode="after")
    def _check_required_arguments(self):
        required = {
            "add_filter": ("field_id", "type"),
            "update_filter": ("filter_id",),
            "delete_filter": ("filter_id",),
            "add_group": ("group_id", "filter_type"),
            "update_group": ("group_id", "filter_type"),
            "delete_group": ("group_id",),
            "set_filter_type": ("filter_type",),
        }[self.op]
        missing = [name for name in required if getattr(self, name) is None]
        if missing:
            raise ValueError(f"{self.op} requires: {', '.join(missing)}.")
        return self


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StateFilter:
    id: str
    field_id: int
    type: str
    value: dict
    group: str | None
    # Filters on trashed fields are kept as they are, but hidden from the agent.
    hidden: bool = False


@dataclass(frozen=True)
class StateGroup:
    id: str
    filter_type: str
    parent_group: str | None


@dataclass(frozen=True)
class FilterState:
    filter_type: str
    filters: tuple[StateFilter, ...]
    groups: tuple[StateGroup, ...]

    @classmethod
    def from_service(cls, service: Any) -> "FilterState":
        """
        Reads the persisted filters of a filterable Local Baserow service.

        :param service: The specific service.
        :return: Its filter state.
        """

        filters = (
            LocalBaserowTableServiceFilter.objects.filter(service=service)
            .select_related("field")
            .order_by("order", "id")
        )
        return cls(
            filter_type=service.filter_type,
            filters=tuple(
                StateFilter(
                    id=str(f.id),
                    field_id=f.field_id,
                    type=f.type,
                    value=dict(BaserowFormulaObject.to_formula(f.value)),
                    group=str(f.group_id) if f.group_id is not None else None,
                    hidden=f.field.trashed,
                )
                for f in filters
            ),
            groups=tuple(
                StateGroup(
                    id=str(g.id),
                    filter_type=g.filter_type,
                    parent_group=(
                        str(g.parent_group_id)
                        if g.parent_group_id is not None
                        else None
                    ),
                )
                for g in service.service_filter_groups.order_by("id")
            ),
        )

    def to_service_values(self) -> dict[str, Any]:
        """
        Returns the values the filterable service mixin's `after_update` replaces
        the filters and groups with. Group ids are correlation keys: existing ids
        keep their group, new references create one.
        """

        return {
            "filter_type": self.filter_type,
            "service_filter_groups": [
                {
                    "id": group.id,
                    "filter_type": group.filter_type,
                    "parent_group_id": group.parent_group,
                }
                for group in self.groups
            ],
            "service_filters": [
                {
                    "field_id": f.field_id,
                    "type": f.type,
                    "value": f.value,
                    "group_id": f.group,
                }
                for f in self.filters
            ],
        }


# ---------------------------------------------------------------------------
# Validation context
# ---------------------------------------------------------------------------


def is_deprecated_filter_type(filter_type: Any) -> bool:
    """
    The old single step date filters are superseded by the multi step ones and are
    no longer offered in the filter form.
    """

    return isinstance(filter_type, TimezoneAwareDateViewFilterType) and not isinstance(
        filter_type, DateEqualsDayOfMonthViewFilterType
    )


def get_compatible_filter_types(field: DatabaseField) -> list[str]:
    """
    Returns the filter types the filter form offers for the given field.

    :param field: The specific field.
    :return: The compatible, non deprecated, filter type names.
    """

    return [
        filter_type.type
        for filter_type in view_filter_type_registry.get_all()
        if not is_deprecated_filter_type(filter_type)
        and filter_type.field_is_compatible(field)
    ]


@dataclass
class FilterValidationContext:
    """Everything needed to validate filter changes, loaded before they're made."""

    fields: dict[int, DatabaseField]
    compatible_types: dict[int, list[str]]
    select_options: dict[int, dict[int, str]]
    check_formula: Callable[[str], str | None] | None
    """Returns why a formula value can't be used, or None when it can. None when
    filter values can only be raw values."""
    allow_filter_groups: bool = True


def _validate_raw_value(
    ctx: FilterValidationContext, field: DatabaseField, filter_type: str, value: str
) -> str | None:
    """
    Checks a raw value has the format the filter type expects.

    :return: An error message, or `None` when the value is fine.
    """

    if filter_type in VALUELESS_FILTER_TYPES:
        return None

    type_instance = view_filter_type_registry.get(filter_type)
    if isinstance(type_instance, BaseDateMultiStepViewFilterType):
        try:
            timezone, filter_value, operator = type_instance.split_combined_value(
                field, value
            )
            if not type_instance.is_empty_filter(operator, filter_value):
                type_instance.get_filter_date(operator, filter_value, timezone)
        except Exception as exc:
            return (
                f"invalid date filter value {value!r} ({exc}). Use "
                "'{timezone}?{value}?{operator}', e.g. 'Europe/London?2024-05-01?"
                "exact_date' or 'UTC?7?nr_days_ago' or 'UTC??today'."
            )
        return None

    if filter_type in SELECT_OPTION_FILTER_TYPES:
        options = ctx.select_options.get(field.id, {})
        ids = [part.strip() for part in value.split(",") if part.strip()]
        invalid = [
            part for part in ids if not part.isdigit() or int(part) not in options
        ]
        if not ids or invalid:
            return (
                f"invalid select option id(s) {invalid or value!r}. Use the option "
                f"ids of the field: {options}."
            )
        return None

    if filter_type in NUMBER_FILTER_TYPES:
        try:
            float(value)
        except ValueError:
            return f"{value!r} is not a number."
        return None

    if filter_type == "boolean" and value.lower() not in BOOLEAN_VALUES:
        return f"invalid boolean value {value!r}. Use '1' for true or '0' for false."

    return None


def _validate_formula_value(ctx: FilterValidationContext, formula: str) -> str | None:
    """
    Checks a formula is valid, and only reads data available to the filter.

    :return: An error message, or `None` when the formula is fine.
    """

    if ctx.check_formula is None:
        return "formula values can't be used here, use a raw value instead."
    error = ctx.check_formula(formula)
    return f"invalid formula {formula!r}: {error}" if error else None


def _check_filter(ctx: FilterValidationContext, state_filter: StateFilter) -> list[str]:
    """Validates a filter the agent added or changed."""

    label = f"Filter {state_filter.id}"
    field = ctx.fields.get(state_filter.field_id)
    if field is None:
        return [
            f"{label}: field {state_filter.field_id} doesn't exist in the table. "
            f"Use one of the field ids listed."
        ]

    compatible = ctx.compatible_types.get(field.id, [])
    if state_filter.type not in compatible:
        return [
            f"{label}: filter type {state_filter.type!r} can't be used on field "
            f"{field.name!r}. Compatible types: {', '.join(compatible)}."
        ]

    value = state_filter.value
    if value["mode"] == BASEROW_FORMULA_MODE_RAW:
        error = _validate_raw_value(ctx, field, state_filter.type, value["formula"])
    elif state_filter.type in VALUELESS_FILTER_TYPES:
        error = f"filter type {state_filter.type!r} doesn't take a value."
    else:
        error = _validate_formula_value(ctx, value["formula"])

    return [f"{label}: {error}"] if error else []


def _filter_value(value: str | None, value_is_formula: bool | None) -> dict:
    return dict(
        BaserowFormulaObject.create(
            formula=value or "",
            mode=(
                BASEROW_FORMULA_MODE_ADVANCED
                if value_is_formula
                else BASEROW_FORMULA_MODE_RAW
            ),
        )
    )


def _descendant_group_ids(groups: list[StateGroup], group_id: str) -> set[str]:
    removed = {group_id}
    changed = True
    while changed:
        changed = False
        for group in groups:
            if group.parent_group in removed and group.id not in removed:
                removed.add(group.id)
                changed = True
    return removed


def apply_operations(
    state: FilterState,
    operations: list[FilterOperation],
    ctx: FilterValidationContext,
) -> FilterState:
    """
    Applies the agent's operations to the state and validates the result.

    :param state: The current filter state.
    :param operations: The operations to apply, in order.
    :param ctx: The validation context.
    :raises ServiceFilterValidationError: With every problem found.
    :return: The new filter state.
    """

    errors: list[str] = []
    filter_type = state.filter_type
    filters = list(state.filters)
    groups = list(state.groups)
    touched: set[str] = set()
    new_filter_count = 0

    def visible_filter(filter_id: str) -> int | None:
        for index, f in enumerate(filters):
            if f.id == filter_id and not f.hidden:
                return index
        return None

    def group_index(group_id: str) -> int | None:
        return next((i for i, g in enumerate(groups) if g.id == group_id), None)

    def check_group_reference(group_id: str | None, position: int) -> bool:
        if group_id is None or group_index(group_id) is not None:
            return True
        errors.append(
            f"Operation {position}: group {group_id!r} doesn't exist. Use an existing "
            "group id or the reference of a group added by an earlier operation."
        )
        return False

    for position, operation in enumerate(operations, start=1):
        op = operation.op
        if op == "set_filter_type":
            filter_type = operation.filter_type

        elif op == "add_filter":
            if not check_group_reference(operation.group, position):
                continue
            new_filter_count += 1
            new_id = f"new_filter_{new_filter_count}"
            filters.append(
                StateFilter(
                    id=new_id,
                    field_id=operation.field_id,
                    type=operation.type,
                    value=_filter_value(operation.value, operation.value_is_formula),
                    group=operation.group,
                )
            )
            touched.add(new_id)

        elif op == "update_filter":
            index = visible_filter(operation.filter_id)
            if index is None:
                errors.append(
                    f"Operation {position}: filter {operation.filter_id!r} doesn't "
                    "exist."
                )
                continue
            current = filters[index]
            changes: dict[str, Any] = {}
            if operation.field_id is not None:
                changes["field_id"] = operation.field_id
            if operation.type is not None:
                changes["type"] = operation.type
            if operation.value is not None or operation.value_is_formula is not None:
                is_formula = (
                    operation.value_is_formula
                    if operation.value_is_formula is not None
                    else current.value["mode"] != BASEROW_FORMULA_MODE_RAW
                )
                value = (
                    operation.value
                    if operation.value is not None
                    else current.value["formula"]
                )
                changes["value"] = _filter_value(value, is_formula)
            if "group" in operation.model_fields_set:
                if not check_group_reference(operation.group, position):
                    continue
                changes["group"] = operation.group
            filters[index] = replace(current, **changes)
            touched.add(current.id)

        elif op == "delete_filter":
            index = visible_filter(operation.filter_id)
            if index is None:
                errors.append(
                    f"Operation {position}: filter {operation.filter_id!r} doesn't "
                    "exist."
                )
                continue
            touched.discard(filters[index].id)
            del filters[index]

        elif op == "add_group":
            if not ctx.allow_filter_groups:
                errors.append(
                    f"Operation {position}: filter groups can't be used here. Only "
                    "add filters at the top level."
                )
                continue
            if group_index(operation.group_id) is not None:
                errors.append(
                    f"Operation {position}: group reference {operation.group_id!r} is "
                    "already used. Choose a new unique reference."
                )
                continue
            if not check_group_reference(operation.parent_group, position):
                continue
            groups.append(
                StateGroup(
                    id=operation.group_id,
                    filter_type=operation.filter_type,
                    parent_group=operation.parent_group,
                )
            )

        elif op == "update_group":
            index = group_index(operation.group_id)
            if index is None:
                errors.append(
                    f"Operation {position}: group {operation.group_id!r} doesn't exist."
                )
                continue
            groups[index] = replace(groups[index], filter_type=operation.filter_type)

        elif op == "delete_group":
            if group_index(operation.group_id) is None:
                errors.append(
                    f"Operation {position}: group {operation.group_id!r} doesn't exist."
                )
                continue
            removed = _descendant_group_ids(groups, operation.group_id)
            groups = [g for g in groups if g.id not in removed]
            filters = [f for f in filters if f.group not in removed]
            touched = {i for i in touched if any(f.id == i for f in filters)}

    for state_filter in filters:
        if state_filter.id in touched:
            errors.extend(_check_filter(ctx, state_filter))

    # A group the agent created but left empty would show as an empty group.
    used_groups = {f.group for f in filters} | {g.parent_group for g in groups}
    existing_group_ids = {g.id for g in state.groups}
    for group in groups:
        if group.id not in existing_group_ids and group.id not in used_groups:
            errors.append(
                f"Group {group.id!r} was added without any filter. Add filters to it "
                "or don't create it."
            )

    if errors:
        raise ServiceFilterValidationError(errors)

    return FilterState(
        filter_type=filter_type or SERVICE_FILTER_TYPE_AND,
        filters=tuple(filters),
        groups=tuple(groups),
    )
