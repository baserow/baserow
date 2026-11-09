import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import FieldDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Model
from django.utils.translation import gettext as _

from dateutil import parser as dateutil_parser
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_serializer,
    model_validator,
)

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import (
    DateField,
    FileField,
    SingleSelectField,
)
from baserow.contrib.database.fields.models import Field as BaserowField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.tools.fields import option_value_key
from baserow.contrib.database.views.actions import (
    CreateViewActionType,
    CreateViewFilterActionType,
    UpdateViewFieldOptionsActionType,
)
from baserow.contrib.database.views.exceptions import ViewFilterNotSupported
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import FormView, View, ViewFilter
from baserow.contrib.database.views.operations import CreateViewFilterOperationType
from baserow.contrib.database.views.registries import (
    view_ownership_type_registry,
    view_type_registry,
)
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import (
    ToolError,
    ToolErrorCode,
    ToolInputError,
    classify_item_error,
    finish_batch,
    item_error,
)


class FormFieldOption(BaseModel):
    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)

    field_id: int = Field(..., description="Field ID.")
    name: str = Field(..., description="Display name in form.")
    description: str = Field(..., description="Field description, or ''.")
    required: bool = Field(..., description="Required?")
    # The column is a smallint.
    order: int = Field(..., ge=-32768, le=32767, description="Sort order.")


def _form_field_option(fo) -> FormFieldOption:
    return FormFieldOption(
        field_id=fo.field_id,
        name=fo.name,
        description=fo.description,
        required=fo.required,
        order=fo.order,
    )


def _form_field_options_from_orm(orm_view):
    return [_form_field_option(fo) for fo in orm_view.active_field_options.all()]


def _form_field_options_by_view(views: list[View]) -> dict[int, list]:
    """The active field options of the form views among ``views``, in one query."""

    form_ids = [view.id for view in views if isinstance(view, FormView)]
    if not form_ids:
        return {}
    by_view = defaultdict(list)
    options = (
        FormView.active_field_options_in(views[0].table.database.workspace)
        .filter(form_view_id__in=form_ids)
        .order_by("order")
    )
    for fo in options:
        by_view[fo.form_view_id].append(_form_field_option(fo))
    return by_view


@dataclass(frozen=True)
class ViewFieldOptions:
    """Where a type of view stores its field options."""

    model: type[Model]
    view_column: str
    hidden_field: Any
    """The option's ``hidden`` model field, None for a view that doesn't have it."""


def field_options_of(view: View) -> ViewFieldOptions:
    relation = view.specific_class._meta.get_field("field_options")
    model = relation.remote_field.through
    try:
        hidden_field = model._meta.get_field("hidden")
    except FieldDoesNotExist:
        hidden_field = None
    return ViewFieldOptions(model, relation.m2m_column_name(), hidden_field)


def _hidden_field_ids_by_view(views: list[View], table: Table) -> dict[int, list[int]]:
    """
    The hidden fields of the views, with one query per type of view. A field with no
    stored option has its option's default, which hides it in some types of view.
    """

    views_by_options = defaultdict(list)
    for view in views:
        options = field_options_of(view)
        if options.hidden_field is not None:
            views_by_options[options].append(view.id)
    if not views_by_options:
        return {}

    field_ids = sorted(table.field_set.values_list("id", flat=True))
    hidden_by_view = {}
    for options, view_ids in views_by_options.items():
        stored = defaultdict(dict)
        rows = options.model.objects.filter(
            **{f"{options.view_column}__in": view_ids}
        ).values_list(options.view_column, "field_id", "hidden")
        for view_id, field_id, hidden in rows:
            stored[view_id][field_id] = hidden
        default = options.hidden_field.default
        for view_id in view_ids:
            hidden_by_view[view_id] = [
                field_id
                for field_id in field_ids
                if stored[view_id].get(field_id, default)
            ]
    return hidden_by_view


def _view_config(view: View, hidden_field_ids: list[int] | None) -> dict[str, Any]:
    """The sorts, filters, row colours and hidden fields of a listed view."""

    config = {
        "sorts": [
            {"id": sort.id, "field_id": sort.field_id, "order": sort.order}
            for sort in view.viewsort_set.all()
        ],
        "filters": [
            {
                "id": view_filter.id,
                "field_id": view_filter.field_id,
                "type": view_filter.type,
                "value": view_filter.value,
                "group_id": view_filter.group_id,
            }
            for view_filter in view.viewfilter_set.all()
        ],
        "filter_type": view.filter_type,
        "filters_disabled": view.filters_disabled,
        "filter_groups": [
            {
                "id": group.id,
                "filter_type": group.filter_type,
                "parent_group_id": group.parent_group_id,
            }
            for group in view.filter_groups.all()
        ],
        "row_colours": [
            {
                "id": decoration.id,
                "style": decoration.type,
                "by": decoration.value_provider_type,
                "conf": decoration.value_provider_conf,
            }
            for decoration in view.viewdecoration_set.all()
        ],
    }
    if hidden_field_ids is not None:
        config["hidden_field_ids"] = hidden_field_ids
    return config


_FROM_DJANGO_ORM: dict[str, Any] = {
    "grid": lambda v: {"row_height": v.row_height_size},
    "kanban": lambda v: {"column_field_id": v.single_select_field_id},
    "calendar": lambda v: {"date_field_id": v.date_field_id},
    "gallery": lambda v: {"cover_field_id": v.card_cover_image_field_id},
    "timeline": lambda v: {
        "start_date_field_id": v.start_date_field_id,
        "end_date_field_id": v.end_date_field_id,
    },
}


class ViewItem(BaseModel):
    """An existing view, with the settings of its type."""

    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)

    id: int = Field(...)
    name: str = Field(...)
    public: bool = Field(...)
    type: str = Field(...)

    # Type-specific (populated per type, others excluded via serializer)
    row_height: str | None = None
    column_field_id: int | None = None
    date_field_id: int | None = None
    cover_field_id: int | None = None
    start_date_field_id: int | None = None
    end_date_field_id: int | None = None
    title: str | None = None
    description: str | None = None
    field_options: list[FormFieldOption] | None = None

    @model_serializer(mode="wrap")
    def _exclude_none(self, handler):
        return {k: v for k, v in handler(self).items() if v is not None}

    @classmethod
    def from_django_orm(
        cls, orm_view: View, form_field_options: list | None = None
    ) -> "ViewItem":
        """
        :param form_field_options: The field options of a form view, when the caller
            loaded them for several views at once. Otherwise they are queried.
        """

        view_type = view_type_registry.get_by_model(orm_view).type
        kwargs: dict[str, Any] = {
            "id": orm_view.id,
            "name": orm_view.name,
            "public": orm_view.public,
            "type": view_type,
        }
        builder = _FROM_DJANGO_ORM.get(view_type)
        if builder:
            kwargs.update(builder(orm_view))
        if view_type == "form":
            if form_field_options is None:
                form_field_options = _form_field_options_from_orm(orm_view)
            kwargs.update(
                title=orm_view.title,
                description=orm_view.description,
                field_options=form_field_options,
            )
        return cls(**kwargs)


def list_views(
    ctx: ToolContext,
    table_id: Annotated[
        int, Field(description="The ID of the table to list views for.")
    ],
) -> dict[str, Any]:
    """
    List the views of a table, at most 100, with their id, name, type, the settings
    of their type, and their sorts, filters, row colours and hidden fields.
    """

    table = (
        TableHandler().list_workspace_tables(ctx.user, ctx.workspace).get(id=table_id)
    )
    ctx.update_status(
        _("Listing views in %(table_name)s...") % {"table_name": table.name}
    )
    views = ViewHandler().list_views(
        ctx.user,
        table,
        filters=True,
        sortings=True,
        decorations=True,
        group_bys=False,
        limit=100,
        prefetch_field_options=False,
    )
    # The same redaction as the views API: what a view's ownership type hides from
    # this user, like the filters and hidden fields of a restricted view.
    views = view_ownership_type_registry.prepare_views_of_different_types_for_user(
        ctx.user, list(views), includes={"filters", "sortings", "decorations"}
    )
    form_options = _form_field_options_by_view(views)
    hidden_field_ids = _hidden_field_ids_by_view(
        [view for view in views if getattr(view, "_hidden_field_ids", None) is None],
        table,
    )
    return {
        "views": [
            {
                **ViewItem.from_django_orm(
                    view, form_options.get(view.id, [])
                ).model_dump(),
                **_view_config(view, hidden_field_ids.get(view.id)),
            }
            for view in views
        ]
    }


# ---------------------------------------------------------------------------
# View creation
# ---------------------------------------------------------------------------

ViewType = Literal["grid", "kanban", "calendar", "gallery", "timeline", "form"]

_VIEW_EXAMPLES: dict[str, dict] = {
    "grid": {"name": "All Items", "type": "grid", "row_height": "small"},
    "kanban": {"name": "Board", "type": "kanban", "column_field_id": 123},
    "calendar": {"name": "Schedule", "type": "calendar", "date_field_id": 456},
    "gallery": {"name": "Photos", "type": "gallery", "cover_field_id": 789},
    "timeline": {
        "name": "Project Timeline",
        "type": "timeline",
        "start_date_field_id": 111,
        "end_date_field_id": 222,
    },
    "form": {
        "name": "Contact Form",
        "type": "form",
        "title": "Contact Us",
        "description": "",
        "submit_button_label": "Submit",
        "receive_notification_on_submit": False,
        "submit_action": "MESSAGE",
        "submit_action_message": "Thank you!",
        "submit_action_redirect_url": "",
        "field_options": [
            {
                "field_id": 1,
                "name": "Name",
                "description": "",
                "required": True,
                "order": 1,
            }
        ],
    },
}


def _grid_to_orm(v, table):
    return {"row_height_size": v.row_height}


def _table_field(table: Table, field_id: int) -> BaserowField:
    """
    A field of the table a view is created in.

    :param table: The table.
    :param field_id: The ID of the field.
    :return: The specific field.
    :raises ToolInputError: When the table has no such field.
    """

    try:
        return table.get_model().get_field_object_by_id(field_id)["field"]
    except ValueError:
        raise ToolInputError(f"Field {field_id} is not in this table.") from None


def _kanban_to_orm(v, table):
    column_field = _table_field(table, v.column_field_id)
    if not isinstance(column_field, SingleSelectField):
        raise ToolInputError("The column_field_id must be a Single Select field.")
    return {"single_select_field": column_field}


def _calendar_to_orm(v, table):
    date_field = _table_field(table, v.date_field_id)
    if not isinstance(date_field, DateField):
        raise ToolInputError("The date_field_id must be a Date field.")
    return {"date_field": date_field}


def _gallery_to_orm(v, table):
    """
    Build gallery view ORM kwargs.

    :raises ToolInputError: When cover_field_id is not a File field.
    """

    cover_field = _table_field(table, v.cover_field_id)
    if not isinstance(cover_field, FileField):
        raise ToolInputError("The cover_field_id must be a File field.")
    return {"card_cover_image_field": cover_field}


def _timeline_to_orm(v, table):
    start_field = _table_field(table, v.start_date_field_id)
    end_field = _table_field(table, v.end_date_field_id)
    if (
        not isinstance(start_field, DateField)
        or not isinstance(end_field, DateField)
        or start_field.id == end_field.id
        or start_field.date_include_time != end_field.date_include_time
    ):
        raise ToolInputError(
            "A timeline view needs two different date fields that both include "
            "the time, or both don't."
        )
    return {"start_date_field": start_field, "end_date_field": end_field}


def _form_to_orm(v, table):
    # receive_notification_on_submit is set once the view exists.
    return {
        "title": v.title,
        "description": v.description,
        "submit_text": v.submit_button_label,
        "submit_action": v.submit_action,
        "submit_action_message": v.submit_action_message,
        "submit_action_redirect_url": v.submit_action_redirect_url,
    }


_TO_DJANGO_ORM = {
    "grid": _grid_to_orm,
    "kanban": _kanban_to_orm,
    "calendar": _calendar_to_orm,
    "gallery": _gallery_to_orm,
    "timeline": _timeline_to_orm,
    "form": _form_to_orm,
}


class ViewItemCreate(BaseModel):
    """Flat model for creating a view: name + type + type-specific options."""

    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)

    name: str = Field(..., max_length=255, description="Descriptive view name.")
    public: bool = Field(False, description="Publicly accessible? Default false.")
    type: ViewType = Field(..., description="View type.")

    # -- grid --
    row_height: Literal["small", "medium", "large"] = Field(
        "small", description="(grid) Row height."
    )
    # -- kanban --
    column_field_id: int | None = Field(
        None, description="(kanban) Single-select field ID for columns."
    )
    # -- calendar --
    date_field_id: int | None = Field(None, description="(calendar) Date field ID.")
    # -- gallery --
    cover_field_id: int | None = Field(
        None, description="(gallery) File field ID for covers."
    )
    # -- timeline --
    start_date_field_id: int | None = Field(
        None, description="(timeline) Start date field ID."
    )
    end_date_field_id: int | None = Field(
        None, description="(timeline) End date field ID."
    )
    # -- form --
    title: str = Field("", description="(form) Title, or ''.")
    description: str = Field("", description="(form) Description, or ''.")
    submit_button_label: str = Field("Submit", description="(form) Button label.")
    receive_notification_on_submit: bool = Field(
        False, description="(form) Email on submit."
    )
    submit_action: Literal["MESSAGE", "REDIRECT"] = Field(
        "MESSAGE", description="(form) 'MESSAGE' or 'REDIRECT'."
    )
    submit_action_message: str = Field("", description="(form) Message after submit.")
    submit_action_redirect_url: str = Field(
        "",
        max_length=2000,
        description="(form) Redirect URL after submit, an http(s) URL, or ''.",
    )
    field_options: list[FormFieldOption] | None = Field(
        None,
        description="(form) Fields to show (OPT-IN: include all you want visible).",
    )

    @field_validator("submit_action_redirect_url")
    @classmethod
    def _validate_redirect_url(cls, value: str) -> str:
        # Validated like the REST API: the public form page navigates to it, so a
        # javascript: URL would run in Baserow's origin.
        if value:
            try:
                URLValidator()(value)
            except DjangoValidationError:
                raise ValueError(f"'{value}' is not a valid URL.") from None
        return value

    # Required fields per type: {type: [(attr_name, display_name), ...]}
    _REQUIRED_FIELDS: dict[str, list[tuple[str, str]]] = {
        "kanban": [("column_field_id", "column_field_id")],
        "calendar": [("date_field_id", "date_field_id")],
        "gallery": [("cover_field_id", "cover_field_id")],
        "timeline": [
            ("start_date_field_id", "start_date_field_id"),
            ("end_date_field_id", "end_date_field_id"),
        ],
        "form": [("field_options", "field_options")],
    }

    @model_validator(mode="after")
    def _validate_required_for_type(self):
        required = self._REQUIRED_FIELDS.get(self.type)
        if required:
            missing = [name for attr, name in required if getattr(self, attr) is None]
            if missing:
                raise ValueError(
                    f"{self.type} requires {', '.join(missing)}. "
                    f"Example: {json.dumps(_VIEW_EXAMPLES[self.type])}"
                )
        return self

    def to_django_orm_kwargs(self, table: Table) -> dict[str, Any]:
        base = {"name": self.name, "public": self.public}
        builder = _TO_DJANGO_ORM.get(self.type)
        if builder:
            base.update(builder(self, table))
        return base

    def field_options_to_django_orm(self) -> dict[str, Any]:
        if self.type != "form" or not self.field_options:
            return {}
        return {
            fo.field_id: {
                "enabled": True,
                "name": fo.name,
                "description": fo.description,
                "required": fo.required,
                "order": fo.order,
            }
            for fo in self.field_options
        }


def _describe_fields(table: Table) -> str:
    """List a table's fields as ``id (name, type)`` for error messages."""

    fields = FieldHandler().get_base_fields_queryset().filter(table=table)
    return (
        ", ".join(f"{f.id} ({f.name}, {f.get_type().type})" for f in fields) or "none"
    )


def _drop_form_incompatible_fields(
    table: Table, field_options: dict
) -> tuple[dict, list[str]]:
    """
    Split form field_options into the ones the form view accepts and the names
    it rejects.

    A form view refuses read-only fields and field types that cannot be a form
    input (e.g. formula); enabling one raises and would roll the whole
    create_views call back, so they are skipped and reported instead.
    """

    fields = {f.id: f for f in table.field_set.all()}
    kept: dict = {}
    skipped: list[str] = []
    for field_id, options in field_options.items():
        field = fields.get(int(field_id))
        if field is None:
            kept[field_id] = options
            continue
        field_type = field_type_registry.get_by_model(field.specific_class)
        if field.read_only or not field_type.can_be_in_form_view:
            skipped.append(field.name)
        else:
            kept[field_id] = options
    return kept, skipped


# ---------------------------------------------------------------------------
# View filters
# ---------------------------------------------------------------------------

FilterType = Literal[
    "text", "number", "date", "single_select", "multiple_select", "link_row", "boolean"
]

_OPERATORS: dict[str, tuple[str, ...]] = {
    "text": ("equal", "not_equal", "contains", "contains_not", "empty", "not_empty"),
    "number": ("equal", "not_equal", "higher_than", "lower_than", "empty", "not_empty"),
    "date": ("equal", "not_equal", "after", "before"),
    "single_select": ("is_any_of", "is_none_of"),
    "multiple_select": ("is_any_of", "is_none_of"),
    "link_row": ("has", "has_not"),
    "boolean": ("equal",),
}

# Operator aliases: normalize natural names to Baserow names before validation.
_OPERATOR_ALIASES: dict[str, str] = {
    "equals": "equal",
    "is": "equal",
    "not_equals": "not_equal",
    "is_not": "not_equal",
    "greater_than": "higher_than",
    "greater_than_or_equal": "higher_than",  # or_equal flag handles the rest
    "less_than": "lower_than",
    "less_than_or_equal": "lower_than",  # or_equal flag handles the rest
    "gte": "higher_than",
    "lte": "lower_than",
    "gt": "higher_than",
    "lt": "lower_than",
    "neq": "not_equal",
    "ne": "not_equal",
    "eq": "equal",
}

DateFilterMode = Literal[
    "today",
    "yesterday",
    "tomorrow",
    "this_week",
    "last_week",
    "next_week",
    "this_month",
    "last_month",
    "next_month",
    "this_year",
    "last_year",
    "next_year",
    "nr_days_ago",
    "nr_days_from_now",
    "nr_weeks_ago",
    "nr_weeks_from_now",
    "nr_months_ago",
    "nr_months_from_now",
    "nr_years_ago",
    "nr_years_from_now",
    "exact_date",
]

_NUMBER_OR_EQUAL = {
    "higher_than": "higher_than_or_equal",
    "lower_than": "lower_than_or_equal",
}

_DATE_ORM_TYPE = {
    "equal": "date_is",
    "not_equal": "date_is_not",
    "after": "date_is_after",
    "before": "date_is_before",
}

_DATE_OR_EQUAL = {
    "after": "date_is_on_or_after",
    "before": "date_is_on_or_before",
}

_SINGLE_SELECT_ORM_TYPE = {
    "is_any_of": "single_select_is_any_of",
    "is_none_of": "single_select_is_none_of",
}

_MULTIPLE_SELECT_ORM_TYPE = {
    "is_any_of": "multiple_select_has",
    "is_none_of": "multiple_select_has_not",
}

_LINK_ROW_ORM_TYPE = {
    "has": "link_row_has",
    "has_not": "link_row_has_not",
}

_GET_ORM_TYPE = {
    "text": lambda f, field, **kw: f.operator,
    "number": lambda f, field, **kw: (
        _NUMBER_OR_EQUAL.get(f.operator, f.operator) if f.or_equal else f.operator
    ),
    "date": lambda f, field, **kw: (
        _DATE_OR_EQUAL[f.operator]
        if f.or_equal and f.operator in _DATE_OR_EQUAL
        else _DATE_ORM_TYPE[f.operator]
    ),
    "single_select": lambda f, field, **kw: _SINGLE_SELECT_ORM_TYPE[f.operator],
    "multiple_select": lambda f, field, **kw: _MULTIPLE_SELECT_ORM_TYPE[f.operator],
    "link_row": lambda f, field, **kw: _LINK_ROW_ORM_TYPE[f.operator],
    "boolean": lambda f, field, **kw: "equal",
}


def _parse_date(value: str) -> date:
    """Parse ISO 8601 first, then fuzzy formats like ``Jan 5, 2023``."""

    try:
        return date.fromisoformat(value.replace("/", "-").strip())
    except ValueError:
        pass
    try:
        return dateutil_parser.parse(value).date()
    except (ValueError, OverflowError):
        raise ToolInputError(
            f"'{value}' is not a date.", hint="Use an ISO date, like 2024-01-31."
        ) from None


def _select_orm_value(f, field, **kwargs):
    """
    Match the labels to the field's options, ignoring case and outer spaces.

    :raises ToolInputError: When a label matches no option, as the filter would
        then match other rows than asked.
    """

    options = list(field.select_options.all())
    ids_by_key: dict[str, int] = {}
    for option in options:
        ids_by_key.setdefault(option_value_key(option.value), option.id)
    unmatched = [
        label for label in f.value if option_value_key(label) not in ids_by_key
    ]
    if unmatched:
        labels = ", ".join(option.value for option in options) or "none"
        raise ToolInputError(
            f"{unmatched} are not options of field '{field.name}'. Options: {labels}."
        )
    option_ids = dict.fromkeys(ids_by_key[option_value_key(v)] for v in f.value)
    return ",".join(str(option_id) for option_id in option_ids)


def _date_count(f) -> str:
    """The number of days, weeks, months or years of an ``nr_*`` mode."""

    value = f.value
    if isinstance(value, str) and value.strip().isdigit():
        return str(int(value))
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return str(value)
    raise ToolInputError(
        f"Mode '{f.mode}' needs a whole number as value, not {value!r}."
    )


def _date_mode_takes_value(mode: str) -> bool:
    """today, this_week and the other relative modes without a count take none."""

    return mode == "exact_date" or mode.startswith("nr_")


def _created_filter(orm_filter: ViewFilter, item: "ViewFilterItemCreate") -> dict:
    """The created filter as stored, with a note when a value was ignored."""

    created = {"id": orm_filter.id, **item.model_dump()}
    if item.type == "date" and not _date_mode_takes_value(item.mode):
        if item.value not in (None, ""):
            created["note"] = f"The value was ignored: mode '{item.mode}' takes none."
        created["value"] = None
    return created


def _date_orm_value(f, field, **kwargs):
    """
    :raises ToolInputError: When an exact date can't be parsed, or an ``nr_*``
        mode has no whole number.
    """

    # A profile can have no timezone.
    timezone = f.timezone or kwargs.get("timezone") or "UTC"
    if not _date_mode_takes_value(f.mode):
        return f"{timezone}??{f.mode}"
    if f.mode == "exact_date":
        if not isinstance(f.value, str):
            raise ToolInputError("Mode 'exact_date' needs a date string as value.")
        value = _parse_date(f.value).isoformat()
    else:
        value = _date_count(f)
    return f"{timezone}?{value}?{f.mode}"


_BOOLEAN_VALUES = {
    "true": "1",
    "1": "1",
    "yes": "1",
    "false": "0",
    "0": "0",
    "no": "0",
    "": "0",
}


def _boolean_orm_value(f, field, **kwargs):
    """:raises ToolInputError: When the value is not a known true or false."""

    if isinstance(f.value, bool):
        return "1" if f.value else "0"
    if isinstance(f.value, (str, int, float)):
        value = _BOOLEAN_VALUES.get(str(f.value).strip().lower())
        if value is not None:
            return value
    raise ToolInputError(f"A boolean filter needs true or false, not {f.value!r}.")


def _number_orm_value(f, field, **kwargs):
    """
    :raises ToolInputError: When an operator that compares has no number, as the
        filter would then match no rows.
    """

    if f.operator in ("empty", "not_empty"):
        return ""
    if isinstance(f.value, (str, int, float)) and not isinstance(f.value, bool):
        value = str(f.value).strip()
        try:
            if Decimal(value).is_finite():
                return value
        except InvalidOperation:
            pass
    raise ToolInputError(f"A number filter needs a number, not {f.value!r}.")


def _link_row_orm_value(f, field, **kwargs):
    """
    :raises ToolInputError: When the value is not a row id, as the filter would
        then match every row.
    """

    if isinstance(f.value, str) and f.value.strip().isdigit():
        return str(int(f.value))
    if isinstance(f.value, int) and not isinstance(f.value, bool) and f.value >= 0:
        return str(f.value)
    raise ToolInputError(f"A link_row filter needs a row id, not {f.value!r}.")


_GET_ORM_VALUE = {
    "text": lambda f, field, **kw: (
        f.value if isinstance(f.value, str) else str(f.value or "")
    ),
    "number": _number_orm_value,
    "date": _date_orm_value,
    "single_select": _select_orm_value,
    "multiple_select": _select_orm_value,
    "link_row": _link_row_orm_value,
    "boolean": _boolean_orm_value,
}


class ViewFilterItemCreate(BaseModel):
    """Flat model for creating a view filter: field_id + type + operator + value."""

    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)

    field_id: int = Field(..., description="Field ID to filter on.")
    type: FilterType = Field(..., description="Must match field type.")
    operator: str = Field(
        ...,
        description=(
            "Filter operator. "
            "text: equal/not_equal/contains/contains_not/empty/not_empty. "
            "number: equal/not_equal/greater_than/less_than/empty/not_empty "
            "(use or_equal=true for ≥/≤). "
            "date: equal/not_equal/after/before (use or_equal=true for "
            "on_or_after/on_or_before). "
            "single_select/multiple_select: is_any_of/is_none_of. "
            "link_row: has/has_not. "
            "boolean: equal."
        ),
    )
    value: str | float | int | bool | list[str] | None = Field(
        None,
        description="Filter value (type-dependent).",
    )
    mode: DateFilterMode | None = Field(None, description="(date) Date filter mode.")
    or_equal: bool = Field(False, description="(number, date) Include equal values.")
    timezone: str | None = Field(
        None,
        description=(
            "(date) The user's IANA timezone, like Europe/Amsterdam, so a mode like "
            "today follows their day. UTC when unknown."
        ),
    )

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
                raise ValueError(f"Unknown timezone '{value}'.") from exc
        return value

    @model_validator(mode="before")
    @classmethod
    def _normalize_operator(cls, data):
        if isinstance(data, dict) and "operator" in data:
            op = data["operator"]
            normalized = _OPERATOR_ALIASES.get(op)
            if normalized:
                data = dict(data)
                data["operator"] = normalized
                # Auto-set or_equal for _or_equal variants
                if "or_equal" in op or op in ("gte", "lte"):
                    data.setdefault("or_equal", True)
        return data

    @model_validator(mode="after")
    def _validate_per_type(self):
        valid = _OPERATORS.get(self.type)
        if valid and self.operator not in valid:
            raise ValueError(
                f"Invalid operator '{self.operator}' for type '{self.type}'. "
                f"Valid operators: {', '.join(valid)}"
            )
        if self.type == "date" and self.mode is None:
            raise ValueError("date filter requires 'mode'.")
        if self.type in ("single_select", "multiple_select") and not (
            isinstance(self.value, list) and self.value
        ):
            raise ValueError(
                f"{self.type} filter requires 'value' as a list of option labels."
            )
        return self

    def get_django_orm_type(self, field, **kwargs) -> str:
        return _GET_ORM_TYPE[self.type](self, field, **kwargs)

    def get_django_orm_value(self, field, **kwargs) -> str:
        return _GET_ORM_VALUE[self.type](self, field, **kwargs)


class ViewFiltersArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)

    view_id: int = Field(..., description="The ID of the view to filter.")
    filters: list[ViewFilterItemCreate] = Field(
        ..., description="The filters to add to the view."
    )


def get_view(ctx: ToolContext, view_id: int) -> View:
    """
    Get a view of a table the user can see in the context's workspace.

    :raises ViewDoesNotExist: When the view is missing, trashed or outside the
        workspace.
    """

    tables = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    return ViewHandler().get_view_as_user(
        ctx.user, view_id, base_queryset=View.objects.filter(table__in=tables)
    )


def resolve_view_filter(
    table_fields: dict[int, Any],
    view_filter_item: ViewFilterItemCreate,
    timezone: str | None = None,
) -> tuple[Any, str, str]:
    """
    Turn a filter definition into the field, filter type and value to store.

    :param table_fields: Mapping of field ID → field instance for the table.
    :param view_filter_item: The filter definition.
    :param timezone: The timezone of a date filter's value, UTC when None.
    :raises ToolInputError: If the field is not found or its type doesn't match.
    """

    field = table_fields.get(view_filter_item.field_id)
    if field is None:
        raise ToolInputError(
            f"Field {view_filter_item.field_id} is not in this view's table.",
            f"Available field IDs: {sorted(table_fields.keys())}",
        )
    field_type = field_type_registry.get_by_model(field.specific_class)
    if field_type.type != view_filter_item.type:
        raise ToolInputError(
            f"Field '{field.name}' is a {field_type.type} field, not "
            f"{view_filter_item.type}.",
            f"Use type '{field_type.type}' for field {field.id}.",
        )

    return (
        field,
        view_filter_item.get_django_orm_type(field),
        view_filter_item.get_django_orm_value(field, timezone=timezone),
    )


def create_view_filter(
    user: AbstractUser,
    orm_view: View,
    table_fields: dict[int, Any],
    view_filter_item: ViewFilterItemCreate,
    timezone: str | None = None,
) -> ViewFilter:
    """
    Create a single view filter after validating the field type matches.

    :param user: The acting user.
    :param orm_view: The view to add the filter to.
    :param table_fields: Mapping of field ID → field instance for the table.
    :param view_filter_item: The filter definition to create.
    :param timezone: The timezone of a date filter's value, UTC when None.
    :raises ToolInputError: If the field is not found or its type doesn't match.
    """

    field, filter_type, filter_value = resolve_view_filter(
        table_fields, view_filter_item, timezone
    )

    return CreateViewFilterActionType.do(
        user,
        orm_view,
        field,
        filter_type,
        filter_value,
        filter_group_id=None,
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def create_views(
    ctx: ToolContext,
    table_id: Annotated[
        int, Field(description="The ID of the table to create the views in.")
    ],
    views: Annotated[
        list[ViewItemCreate],
        Field(
            min_length=1,
            description="The views to create: grid, form, gallery, kanban, calendar "
            "or timeline, each with the settings of its type.",
        ),
    ],
) -> dict[str, Any]:
    """
    Create views in a table. A new table already has a grid view. A view whose
    name is already used in the table, or earlier in the call, is not created and
    is returned in errors. Each type needs its fields: a kanban view a single
    select field for its columns, a calendar view a date field, a timeline view a
    start and an end date field with the same include time setting, and a gallery
    view a file field for its covers. A form view shows only the fields listed in
    its field_options; fields that cannot be a form input are left out and named in
    skipped_fields. When a field setting is wrong, no view is created.
    """

    table = (
        TableHandler().list_workspace_tables(ctx.user, ctx.workspace).get(id=table_id)
    )
    view_list = ViewHandler().list_views(
        ctx.user,
        table,
        filters=False,
        sortings=False,
        decorations=False,
        group_bys=False,
        prefetch_field_options=False,
    )
    used_names = {view.name for view in view_list}

    created_views = []
    errors: list[dict[str, Any]] = []
    with transaction.atomic():
        for view in views:
            if view.name in used_names:
                errors.append(
                    item_error(
                        view.name,
                        ToolError(
                            ToolErrorCode.CONFLICT,
                            f"A view named '{view.name}' already exists in this table.",
                        ),
                    )
                )
                continue
            used_names.add(view.name)
            ctx.update_status(
                _("Creating %(view_type)s view %(view_name)s")
                % {"view_type": view.type, "view_name": view.name}
            )

            try:
                orm_kwargs = view.to_django_orm_kwargs(table)
            except ToolInputError as exc:
                raise ToolInputError(
                    f"Cannot create the '{view.name}' {view.type} view: {exc}",
                    hint=f"Fields in table '{table.name}': {_describe_fields(table)}",
                ) from exc

            orm_view = CreateViewActionType.do(ctx.user, table, view.type, **orm_kwargs)
            if view.type == "form" and view.receive_notification_on_submit:
                # Not an action of its own: undoing the creation removes the view.
                orm_view = (
                    ViewHandler()
                    .update_view(
                        ctx.user, orm_view, receive_notification_on_submit=True
                    )
                    .updated_view_instance
                )

            field_options = view.field_options_to_django_orm()
            skipped_fields: list[str] = []
            if field_options:
                field_options, skipped_fields = _drop_form_incompatible_fields(
                    table, field_options
                )
            if field_options:
                try:
                    # A savepoint, so the hint can still query the table.
                    with transaction.atomic():
                        UpdateViewFieldOptionsActionType.do(
                            ctx.user, orm_view, field_options
                        )
                except PermissionException:
                    raise
                except Exception as exc:
                    error = classify_item_error(exc)
                    if error.message is None:
                        raise
                    raise ToolInputError(
                        f"The field_options of the '{view.name}' {view.type} view "
                        f"were rejected and no views were created: {error.message}",
                        hint="Retry without the rejected fields. Fields in table "
                        f"'{table.name}': {_describe_fields(table)}",
                    ) from exc

            created = {"id": orm_view.id, **view.model_dump()}
            if view.type == "form":
                created["field_options"] = ViewItem.from_django_orm(
                    orm_view
                ).model_dump()["field_options"]
            if skipped_fields:
                created["skipped_fields"] = (
                    "Not shown on the form, these field types cannot be a form "
                    f"input: {', '.join(skipped_fields)}"
                )
            created_views.append(created)

    return finish_batch(
        {"created_views": created_views},
        bool(created_views),
        errors,
        "No view was created.",
    )


def create_view_filters(
    ctx: ToolContext,
    view_filters: Annotated[
        list[ViewFiltersArgs],
        Field(
            min_length=1,
            description="The filters to add, grouped by the view they apply to.",
        ),
    ],
) -> dict[str, Any]:
    """
    Add filters to views, so a view shows only the rows that match all of them.
    Each filter names a field, its type, which must match the field's type, an
    operator and a value. A filter whose field is missing from the view's table,
    has another type, has a value of the wrong format, has a label that matches no
    select option, or that the view refuses (a form view takes no filters) is not
    created and is returned in errors with the reason. When a view is not
    found, nothing is created.

    Value formats by type:
    - text: string
    - number: number
    - date: ISO date string (mode=exact_date), or a whole number (mode=nr_days_ago
      etc.). The other modes (today etc.) take none; a value given is ignored
      and noted.
    - single_select / multiple_select: list of option labels, matched ignoring
      case and outer spaces
    - link_row: row ID (integer)
    - boolean: true / false
    """

    # Every view is checked before anything is written, so a missing view fails
    # the call without leaving the filters of the other views behind.
    orm_views = [get_view(ctx, view_filter.view_id) for view_filter in view_filters]
    # Before reading the fields, as a failed filter's error names them.
    for orm_view in orm_views:
        CoreHandler().check_permissions(
            ctx.user,
            CreateViewFilterOperationType.type,
            workspace=ctx.workspace,
            context=orm_view,
        )

    created_view_filters = []
    errors: list[dict[str, Any]] = []
    # One transaction for every view, so an error on a later view doesn't leave
    # the filters of the earlier ones behind for a retry to duplicate.
    with transaction.atomic():
        for view_filter, orm_view in zip(view_filters, orm_views):
            ctx.update_status(
                _("Creating filters in %(view_name)s...") % {"view_name": orm_view.name}
            )

            fields = {f.id: f for f in orm_view.table.field_set.all()}
            created_filters = []
            for index, item in enumerate(view_filter.filters):
                try:
                    orm_filter = create_view_filter(
                        ctx.user, orm_view, fields, item, ctx.timezone
                    )
                # The handler raises ViewFilterNotSupported before it writes.
                except (ToolInputError, ViewFilterNotSupported) as exc:
                    errors.append(
                        item_error(
                            orm_view.name,
                            classify_item_error(exc),
                            view_id=view_filter.view_id,
                            index=index,
                            **item.model_dump(),
                        )
                    )
                    continue
                created_filters.append(_created_filter(orm_filter, item))

            created_view_filters.append(
                {"view_id": view_filter.view_id, "filters": created_filters}
            )

    return finish_batch(
        {"created_view_filters": created_view_filters},
        any(item["filters"] for item in created_view_filters),
        errors,
        "No filter was added.",
    )
