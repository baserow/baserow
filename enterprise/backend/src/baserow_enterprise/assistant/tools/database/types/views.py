import json
from typing import Any, Literal

from pydantic import Field, model_serializer, model_validator

from baserow.contrib.database.fields.models import (
    DateField,
    FileField,
    SingleSelectField,
)
from baserow.contrib.database.views.models import View as BaserowView
from baserow.contrib.database.views.registries import view_type_registry
from baserow_enterprise.assistant.types import BaseModel
from baserow_premium.permission_manager import Table

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------


class FormFieldOption(BaseModel):
    field_id: int = Field(..., description="Field ID.")
    name: str = Field(..., description="Display name in form.")
    description: str = Field(..., description="Field description, or ''.")
    required: bool = Field(..., description="Required?")
    order: int = Field(..., description="Sort order.")


class GridFieldOption(BaseModel):
    field_id: int = Field(...)
    width: int = Field(
        ...,
        description="The width of the field in the grid view (e.g. 200).",
    )
    hidden: bool = Field(
        ...,
        description="Whether the field is hidden in the grid view.",
    )


# ---------------------------------------------------------------------------
# Flat view types
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


# ---------------------------------------------------------------------------
# to_django_orm builders: (ViewItemCreate, Table) -> dict
# ---------------------------------------------------------------------------


def _grid_to_orm(v, table):
    return {"row_height": v.row_height}


def _kanban_to_orm(v, table):
    model = table.get_model()
    column_field = model.get_field_object_by_id(v.column_field_id)["field"]
    if not isinstance(column_field, SingleSelectField):
        raise ValueError("The column_field_id must be a Single Select field.")
    return {"single_select_field": column_field}


def _calendar_to_orm(v, table):
    model = table.get_model()
    date_field = model.get_field_object_by_id(v.date_field_id)["field"]
    if not isinstance(date_field, DateField):
        raise ValueError("The date_field_id must be a Date field.")
    return {"date_field": date_field}


def _gallery_to_orm(v, table):
    model = table.get_model()
    cover_field = model.get_field_object_by_id(v.cover_field_id)["field"]
    if not isinstance(cover_field, FileField):
        raise ValueError("The cover_field_id must be a File field.")
    return {"card_cover_image_field_id": v.cover_field_id}


def _timeline_to_orm(v, table):
    model = table.get_model()
    start_field = model.get_field_object_by_id(v.start_date_field_id)["field"]
    end_field = model.get_field_object_by_id(v.end_date_field_id)["field"]
    if (
        not isinstance(start_field, DateField)
        or not isinstance(end_field, DateField)
        or start_field.id == end_field.id
        or start_field.date_include_time != end_field.date_include_time
    ):
        raise ValueError(
            "Invalid timeline configuration: both start and end fields must be Date fields "
            "and they must have the same include_time setting (either both include time or "
            "both are date-only). "
        )
    return {"start_date_field": start_field, "end_date_field": end_field}


def _form_to_orm(v, table):
    return {"title": v.title, "description": v.description}


_TO_DJANGO_ORM = {
    "grid": _grid_to_orm,
    "kanban": _kanban_to_orm,
    "calendar": _calendar_to_orm,
    "gallery": _gallery_to_orm,
    "timeline": _timeline_to_orm,
    "form": _form_to_orm,
}


# ---------------------------------------------------------------------------
# from_django_orm builders: (orm_view) -> dict of extra kwargs
# ---------------------------------------------------------------------------


def _form_field_options_from_orm(orm_view):
    return [
        FormFieldOption(
            field_id=fo.field_id,
            name=fo.name,
            description=fo.description,
            required=fo.required,
            order=fo.order,
        )
        for fo in orm_view.active_field_options.all()
    ]


_FROM_DJANGO_ORM: dict[str, Any] = {
    "grid": lambda v: {"row_height": v.row_height_size},
    "kanban": lambda v: {"column_field_id": v.single_select_field_id},
    "calendar": lambda v: {"date_field_id": v.date_field_id},
    "gallery": lambda v: {"cover_field_id": v.card_cover_image_field_id},
    "timeline": lambda v: {
        "start_date_field_id": v.start_date_field_id,
        "end_date_field_id": v.end_date_field_id,
    },
    "form": lambda v: {
        "title": v.title,
        "description": v.description,
        "field_options": _form_field_options_from_orm(v),
    },
}


# ---------------------------------------------------------------------------
# ViewItemCreate
# ---------------------------------------------------------------------------


class ViewItemCreate(BaseModel):
    """Flat model for creating a view: name + type + type-specific options."""

    name: str = Field(..., description="Descriptive view name.")
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
        "", description="(form) Redirect URL after submit."
    )
    field_options: list[FormFieldOption] | None = Field(
        None,
        description="(form) Fields to show (OPT-IN: include all you want visible).",
    )

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


# ---------------------------------------------------------------------------
# ViewItem (read-back)
# ---------------------------------------------------------------------------


class ViewItem(BaseModel):
    """Existing view with ID — flat structure matching ViewItemCreate."""

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
    def from_django_orm(cls, orm_view: BaserowView) -> "ViewItem":
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
        return cls(**kwargs)
