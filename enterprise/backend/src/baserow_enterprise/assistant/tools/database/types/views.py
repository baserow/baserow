from typing import Annotated, Literal, Type

from baserow_premium.permission_manager import Table
from baserow_premium.views.models import CalendarView, KanbanView, TimelineView
from pydantic import Field

from baserow.contrib.database.fields.models import (
    DateField,
    FileField,
    SingleSelectField,
)
from baserow.contrib.database.views.models import FormView, GalleryView, GridView
from baserow.contrib.database.views.models import View as BaserowView
from baserow.contrib.database.views.registries import view_type_registry
from baserow_enterprise.assistant.types import BaseModel


class ViewItemCreate(BaseModel):
    name: str = Field(
        ...,
        description="A sensible name for the view (i.e. 'Pending payments', 'Completed tasks', etc.).",
    )
    public: bool = Field(
        default=False,
        description="Whether the view is publicly accessible. False unless specified.",
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        return {
            "name": self.name,
            "public": self.public,
        }

    def field_options_to_django_orm(self) -> dict[str, any]:
        return {}


class ViewItem(BaseModel):
    id: int = Field(...)

    @classmethod
    def from_django_orm(cls, orm_view: Type[BaserowView]) -> "ViewItem":
        return cls(
            id=orm_view.id,
            name=orm_view.name,
            public=orm_view.public,
        )


class GridFieldOption(BaseModel):
    field_id: int = Field(...)
    width: int = Field(
        default=200,
        description="The width of the field in the grid view. Default is 200.",
    )
    hidden: bool = Field(
        default=False,
        description="Whether the field is hidden in the grid view. Default is False.",
    )


class GridViewItemCreate(ViewItemCreate):
    type: Literal["grid"] = Field(..., description="A grid view.")
    row_height: Literal["small", "medium", "large"] = Field(
        default="small",
        description=(
            "The height of the rows in the view. Can be 'small', 'medium' or 'large'. Default is 'small'."
        ),
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        return {
            **super().to_django_orm_kwargs(table),
            "row_height": self.row_height,
        }


class GridViewItem(GridViewItemCreate, ViewItem):
    @classmethod
    def from_django_orm(cls, orm_view: GridView) -> "GridViewItem":
        return cls(
            id=orm_view.id,
            name=orm_view.name,
            type="grid",
            row_height="small",
            public=orm_view.public,
        )


class KanbanViewItemCreate(ViewItemCreate):
    type: Literal["kanban"] = Field(..., description="A kanban view.")
    column_field_id: int | None = Field(
        ...,
        description="The ID of the field to use for the kanban columns. Must be a single select field. None if no single select field is available.",
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        model = table.get_model()
        column_field = model.get_field_object_by_id(self.column_field_id)["field"]
        if not isinstance(column_field, SingleSelectField):
            raise ValueError("The column_field_id must be a Single Select field.")

        return {
            **super().to_django_orm_kwargs(table),
            "single_select_field": column_field,
        }


class KanbanViewItem(KanbanViewItemCreate, ViewItem):
    @classmethod
    def from_django_orm(cls, orm_view: KanbanView) -> "KanbanViewItem":
        return cls(
            id=orm_view.id,
            name=orm_view.name,
            type="kanban",
            column_field_id=orm_view.single_select_field_id,
            public=orm_view.public,
        )


class CalendarViewItemCreate(ViewItemCreate):
    type: Literal["calendar"] = Field(..., description="A calendar view.")
    date_field_id: int | None = Field(
        ...,
        description="The ID of the field to use for the calendar dates. Must be a date field. None if no date field is available.",
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        model = table.get_model()
        date_field = model.get_field_object_by_id(self.date_field_id)["field"]
        if not isinstance(date_field, DateField):
            raise ValueError("The date_field_id must be a Date field.")

        return {
            **super().to_django_orm_kwargs(table),
            "date_field": date_field,
        }


class CalendarViewItem(CalendarViewItemCreate, ViewItem):
    @classmethod
    def from_django_orm(cls, orm_view: CalendarView) -> "CalendarViewItem":
        return cls(
            id=orm_view.id,
            name=orm_view.name,
            type="calendar",
            date_field_id=orm_view.date_field_id,
            public=orm_view.public,
        )


class BaseGalleryViewItem(ViewItemCreate):
    type: Literal["gallery"] = Field(..., description="A gallery view.")
    cover_field_id: int | None = Field(
        default=None,
        description=(
            "The ID of the field to use for the gallery cover image. Must be a file field. None if no file field is available."
        ),
    )


class GalleryViewItemCreate(BaseGalleryViewItem):
    def to_django_orm_kwargs(self, table):
        model = table.get_model()
        cover_field = model.get_field_object_by_id(self.cover_field_id)["field"]
        if not isinstance(cover_field, FileField):
            raise ValueError("The cover_field_id must be a File field.")

        return {
            **super().to_django_orm_kwargs(table),
            "card_cover_image_field_id": self.cover_field_id,
        }


class GalleryViewItem(BaseGalleryViewItem, ViewItem):
    @classmethod
    def from_django_orm(cls, orm_view: GalleryView) -> "GalleryViewItem":
        return cls(
            id=orm_view.id,
            name=orm_view.name,
            type="gallery",
            cover_field_id=orm_view.card_cover_image_field_id,
            public=orm_view.public,
        )


class BaseTimelineViewItem(ViewItemCreate):
    type: Literal["timeline"] = Field(..., description="A timeline view.")
    start_date_field_id: int | None = Field(
        ...,
        description="The ID of the field to use for the timeline dates. Must be a date field. None if no date field is available.",
    )
    end_date_field_id: int | None = Field(
        ...,
        description=(
            "The ID of the field to use for the timeline end dates. Must be a date field. None if no date field is available."
        ),
    )


class TimelineViewItemCreate(BaseTimelineViewItem):
    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
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

        return {
            **super().to_django_orm_kwargs(table),
            "start_date_field": start_field,
            "end_date_field": end_field,
        }


class TimelineViewItem(BaseTimelineViewItem, ViewItem):
    @classmethod
    def from_django_orm(cls, orm_view: TimelineView) -> "TimelineViewItem":
        return cls(
            id=orm_view.id,
            name=orm_view.name,
            type="timeline",
            start_date_field_id=orm_view.start_date_field_id,
            end_date_field_id=orm_view.end_date_field_id,
            public=orm_view.public,
        )


class FormFieldOption(BaseModel):
    field_id: int = Field(..., description="The ID of the field.")
    name: str = Field(..., description="The name to show for the field in the form.")
    description: str = Field(
        default="", description="The description to show for the field in the form."
    )
    required: bool = Field(
        default=True,
        description="Whether the field is required in the form. Default is True.",
    )
    order: int = Field(..., description="The order of the field in the form.")


class BaseFormViewItem(ViewItemCreate):
    type: Literal["form"] = Field(..., description="A form view.")
    title: str = Field(..., description="The title of the form.")
    description: str = Field(..., description="The description of the form.")
    submit_button_label: str = Field(
        default="Submit", description="The label of the submit button."
    )
    receive_notification_on_submit: bool = Field(
        default=False,
        description=(
            "Whether to receive an email notification when the form is submitted."
        ),
    )
    submit_action: Literal["MESSAGE", "REDIRECT"] = Field(
        default="MESSAGE",
        description="The action to perform when the form is submitted.",
    )
    submit_action_message: str = Field(
        default="",
        description=(
            "The message to display when the form is submitted and the action is 'MESSAGE'."
        ),
    )
    submit_action_redirect_url: str = Field(
        default="",
        description=(
            "The URL to redirect to when the form is submitted and the action is 'REDIRECT'."
        ),
    )

    field_options: list[FormFieldOption] = Field(
        ...,
        description=(
            "The list of fields to show in the form, along with their options. The fields must be part of the table."
        ),
    )


class FormViewItemCreate(BaseFormViewItem):
    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        return {
            **super().to_django_orm_kwargs(table),
            "title": self.title,
            "description": self.description,
        }

    def field_options_to_django_orm(self):
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


class FormViewItem(FormViewItemCreate, ViewItem):
    @classmethod
    def from_django_orm(cls, orm_view: FormView) -> "FormViewItem":
        return cls(
            id=orm_view.id,
            name=orm_view.name,
            type="form",
            public=orm_view.public,
            title=orm_view.title,
            description=orm_view.description,
            field_options=[
                FormFieldOption(
                    field_id=fo.field_id,
                    name=fo.name,
                    description=fo.description,
                    required=fo.required,
                    order=fo.order,
                )
                for fo in orm_view.active_field_options.all()
            ],
        )


AnyViewItemCreate = Annotated[
    GridViewItemCreate
    | KanbanViewItemCreate
    | CalendarViewItemCreate
    | GalleryViewItemCreate
    | TimelineViewItemCreate
    | FormViewItemCreate,
    Field(discriminator="type"),
]

AnyViewItem = Annotated[
    GridViewItem
    | KanbanViewItem
    | CalendarViewItem
    | GalleryViewItem
    | TimelineViewItem
    | FormViewItem,
    Field(discriminator="type"),
]


class ViewItemsRegistry:
    _registry = {
        "grid": GridViewItem,
        "kanban": KanbanViewItem,
        "calendar": CalendarViewItem,
        "gallery": GalleryViewItem,
        "timeline": TimelineViewItem,
        "form": FormViewItem,
    }

    def from_django_orm(self, orm_view: Type[BaserowView]) -> ViewItem:
        view_type = view_type_registry.get_by_model(orm_view).type
        view_class: ViewItem = self._registry.get(view_type, ViewItem)
        return view_class.from_django_orm(orm_view)


view_item_registry = ViewItemsRegistry()
