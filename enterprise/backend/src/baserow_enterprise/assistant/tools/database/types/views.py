from typing import Any, Callable, Literal

from pydantic import Field

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
    field_id: int = Field(..., description="The ID of the field.")
    name: str = Field(..., description="The name to show for the field in the form.")
    description: str = Field(
        ...,
        description="The description to show for the field in the form, or '' for none.",
    )
    required: bool = Field(
        ...,
        description="Whether the field is required in the form.",
    )
    order: int = Field(..., description="The order of the field in the form.")


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
# Type-specific config models
# ---------------------------------------------------------------------------


class GridConfig(BaseModel):
    type: Literal["grid"] = Field(..., description="Must be 'grid'.")
    row_height: Literal["small", "medium", "large"] = Field(
        ...,
        description="Row height: 'small', 'medium', or 'large'.",
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, Any]:
        return {"row_height": self.row_height}


class KanbanConfig(BaseModel):
    type: Literal["kanban"] = Field(..., description="Must be 'kanban'.")
    column_field_id: int = Field(
        ...,
        description="ID of the single select field for columns.",
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, Any]:
        model = table.get_model()
        column_field = model.get_field_object_by_id(self.column_field_id)["field"]
        if not isinstance(column_field, SingleSelectField):
            raise ValueError("The column_field_id must be a Single Select field.")
        return {"single_select_field": column_field}


class CalendarConfig(BaseModel):
    type: Literal["calendar"] = Field(..., description="Must be 'calendar'.")
    date_field_id: int = Field(
        ...,
        description="ID of the date field for calendar dates.",
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, Any]:
        model = table.get_model()
        date_field = model.get_field_object_by_id(self.date_field_id)["field"]
        if not isinstance(date_field, DateField):
            raise ValueError("The date_field_id must be a Date field.")
        return {"date_field": date_field}


class GalleryConfig(BaseModel):
    type: Literal["gallery"] = Field(..., description="Must be 'gallery'.")
    cover_field_id: int = Field(
        ...,
        description="ID of the file field for cover images.",
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, Any]:
        model = table.get_model()
        cover_field = model.get_field_object_by_id(self.cover_field_id)["field"]
        if not isinstance(cover_field, FileField):
            raise ValueError("The cover_field_id must be a File field.")
        return {"card_cover_image_field_id": self.cover_field_id}


class TimelineConfig(BaseModel):
    type: Literal["timeline"] = Field(..., description="Must be 'timeline'.")
    start_date_field_id: int = Field(
        ...,
        description="ID of the date field for start dates.",
    )
    end_date_field_id: int = Field(
        ...,
        description="ID of the date field for end dates.",
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, Any]:
        model = table.get_model()
        start_field = model.get_field_object_by_id(self.start_date_field_id)["field"]
        end_field = model.get_field_object_by_id(self.end_date_field_id)["field"]
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


class FormConfig(BaseModel):
    type: Literal["form"] = Field(..., description="Must be 'form'.")
    title: str = Field(..., description="The form title, or '' for none.")
    description: str = Field(..., description="The form description, or '' for none.")
    submit_button_label: str = Field(
        ..., description="The submit button label (e.g. 'Submit')."
    )
    receive_notification_on_submit: bool = Field(
        ..., description="Email notification on submit."
    )
    submit_action: Literal["MESSAGE", "REDIRECT"] = Field(
        ..., description="Action on submit: 'MESSAGE' or 'REDIRECT'."
    )
    submit_action_message: str = Field(
        ...,
        description="Message shown after submit (MESSAGE action), or '' if not applicable.",
    )
    submit_action_redirect_url: str = Field(
        ...,
        description="Redirect URL after submit (REDIRECT action), or '' if not applicable.",
    )
    field_options: list[FormFieldOption] = Field(
        ...,
        description=(
            "Fields to show in the form with their options. "
            "Fields are OPT-IN, so ALWAYS include all fields you want to show in the form. "
        ),
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, Any]:
        return {"title": self.title, "description": self.description}


# ---------------------------------------------------------------------------
# Config type unions
# ---------------------------------------------------------------------------

# Create config union (LLM-facing) — anyOf for broader LLM compatibility
AnyViewConfig = (
    GridConfig
    | KanbanConfig
    | CalendarConfig
    | GalleryConfig
    | TimelineConfig
    | FormConfig
)


# ---------------------------------------------------------------------------
# Read-back config variants (extend create configs where extras are needed)
# ---------------------------------------------------------------------------


class FormReadConfig(BaseModel):
    """Read-back variant with only the fields extractable from ORM."""

    type: Literal["form"] = "form"
    title: str
    description: str
    field_options: list[FormFieldOption]


class GenericViewConfig(BaseModel):
    """Fallback for view types not in our supported set."""

    type: str


# Read config union — includes read variants and a generic fallback
AnyViewReadConfig = (
    GridConfig
    | KanbanConfig
    | CalendarConfig
    | GalleryConfig
    | TimelineConfig
    | FormReadConfig
    | GenericViewConfig
)


# ---------------------------------------------------------------------------
# View item models (shared base, consistent structure)
# ---------------------------------------------------------------------------


class _ViewItemBase(BaseModel):
    """Shared base for create and read-back view models."""

    name: str = Field(
        ...,
        description="A sensible name for the view (i.e. 'Pending payments', 'Completed tasks', etc.).",
    )
    public: bool = Field(
        ...,
        description="Whether the view is publicly accessible. Use false unless specified.",
    )


class ViewItemCreate(_ViewItemBase):
    """Model for creating a view: name + public + config."""

    config: AnyViewConfig = Field(
        ...,
        description="Type and configuration of the view.",
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, Any]:
        base = {"name": self.name, "public": self.public}
        return {**base, **self.config.to_django_orm_kwargs(table)}

    def field_options_to_django_orm(self) -> dict[str, Any]:
        if not isinstance(self.config, FormConfig):
            return {}
        if not self.config.field_options:
            return {}
        return {
            fo.field_id: {
                "enabled": True,
                "name": fo.name,
                "description": fo.description,
                "required": fo.required,
                "order": fo.order,
            }
            for fo in self.config.field_options
        }


# ---------------------------------------------------------------------------
# Read-back model (config-based, consistent with ViewItemCreate)
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


_CONFIG_BUILDERS: dict[str, Callable] = {
    "grid": lambda v: GridConfig(type="grid", row_height="small"),
    "kanban": lambda v: KanbanConfig(
        type="kanban", column_field_id=v.single_select_field_id
    ),
    "calendar": lambda v: CalendarConfig(
        type="calendar", date_field_id=v.date_field_id
    ),
    "gallery": lambda v: GalleryConfig(
        type="gallery", cover_field_id=v.card_cover_image_field_id
    ),
    "timeline": lambda v: TimelineConfig(
        type="timeline",
        start_date_field_id=v.start_date_field_id,
        end_date_field_id=v.end_date_field_id,
    ),
    "form": lambda v: FormReadConfig(
        type="form",
        title=v.title,
        description=v.description,
        field_options=_form_field_options_from_orm(v),
    ),
}


def _config_from_orm(view_type: str, orm_view) -> AnyViewReadConfig:
    """Build the appropriate config object from a Django ORM view instance."""

    builder = _CONFIG_BUILDERS.get(view_type)
    if builder is None:
        return GenericViewConfig(type=view_type)
    return builder(orm_view)


class ViewItem(_ViewItemBase):
    """Existing view with ID. Config-based, consistent with ViewItemCreate."""

    id: int = Field(...)
    config: AnyViewReadConfig

    def model_dump(self, **kwargs):
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)

    @classmethod
    def from_django_orm(cls, orm_view: BaserowView) -> "ViewItem":
        view_type = view_type_registry.get_by_model(orm_view).type
        config = _config_from_orm(view_type, orm_view)
        return cls(
            id=orm_view.id,
            name=orm_view.name,
            public=orm_view.public,
            config=config,
        )
