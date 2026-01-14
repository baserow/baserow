from typing import Annotated, Literal, Optional

from pydantic import Field

from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.core.formula.types import (
    BaserowFormulaObject,
)
from baserow_enterprise.assistant.types import BaseModel


class ElementBase(BaseModel):
    """Base properties for all elements."""

    parent_element_ref: Optional[str] = Field(
        default=None,
        description="Reference to parent container element (for nested elements)",
    )
    place_in_container: Optional[str] = Field(
        default=None,
        description="Position within parent container (e.g., '0', '1' for columns)",
    )
    visibility: Literal["all", "logged-in", "not-logged"] = Field(default="all")


class RefCreate(BaseModel):
    """Reference for element creation, used for linking elements."""

    ref: str = Field(
        ..., description="Unique reference for this element (used in linking)"
    )


# =============================================================================
# Layout Elements
# =============================================================================


class ColumnElementCreate(ElementBase, RefCreate):
    """Multi-column layout container."""

    type: Literal["column"] = "column"
    column_amount: int = Field(default=2, ge=1, le=6, description="Number of columns")
    column_gap: int = Field(default=20, description="Gap between columns in pixels")
    alignment: Literal["top", "center", "bottom"] = Field(
        default="top", description="Vertical alignment of column content"
    )

    def to_orm_kwargs(self, user, page) -> dict:
        return {
            "column_amount": self.column_amount,
            "column_gap": self.column_gap,
            "alignment": self.alignment,
        }


class FormContainerElementCreate(ElementBase, RefCreate):
    """Form container that wraps form input elements."""

    type: Literal["form_container"] = "form_container"
    submit_button_label: str = Field(default="Submit")
    reset_initial_values_post_submission: bool = Field(default=False)

    def to_orm_kwargs(self, user, page) -> dict:
        return {
            "submit_button_label": BaserowFormulaObject.create(
                f"'{self.submit_button_label}'"
            ),
            "reset_initial_values_post_submission": self.reset_initial_values_post_submission,
        }


class SimpleContainerElementCreate(ElementBase, RefCreate):
    """Simple container for grouping elements."""

    type: Literal["simple_container"] = "simple_container"

    def to_orm_kwargs(self, user, page) -> dict:
        return {}


# =============================================================================
# Display Elements
# =============================================================================


class HeadingElementCreate(ElementBase, RefCreate):
    """Heading text element."""

    type: Literal["heading"] = "heading"
    value: str = Field(
        ..., description="Heading text formula. Wrap simple strings in quotes."
    )
    level: Literal[1, 2, 3, 4, 5] = Field(
        default=1, description="Heading level (h1-h5)"
    )

    def to_orm_kwargs(self, user, page) -> dict:
        return {
            "value": BaserowFormulaObject.create(self.value),
            "level": self.level,
        }


class TextElementCreate(ElementBase, RefCreate):
    """Text/paragraph element."""

    type: Literal["text"] = "text"
    value: str = Field(..., description="Text formula. Wrap simple strings in quotes.")
    format: Literal["plain", "markdown"] = Field(default="plain")

    def to_orm_kwargs(self, user, page) -> dict:
        return {
            "value": BaserowFormulaObject.create(self.value),
            "format": self.format,
        }


class ButtonElementCreate(ElementBase, RefCreate):
    """Button element that triggers workflow actions."""

    type: Literal["button"] = "button"
    value: str = Field(
        ..., description="Button label formula. Wrap simple strings in quotes."
    )

    def to_orm_kwargs(self, user, page) -> dict:
        return {
            "value": BaserowFormulaObject.create(self.value),
        }


class LinkElementCreate(ElementBase, RefCreate):
    """Link or button-styled link element."""

    type: Literal["link"] = "link"
    value: str = Field(
        ..., description="Link text formula. Wrap simple strings in quotes."
    )
    variant: Literal["link", "button"] = Field(default="link")
    navigation_type: Literal["page", "custom"] = Field(default="page")
    navigate_to_page_id: Optional[int] = Field(default=None)
    navigate_to_url: Optional[str] = Field(default=None)
    page_parameters: list[dict] = Field(
        default_factory=list, description="List of {name, value} for page params"
    )
    target: Literal["self", "blank"] = Field(default="self")

    def to_orm_kwargs(self, user, page) -> dict:
        kwargs = {
            "value": BaserowFormulaObject.create(self.value),
            "variant": self.variant,
            "navigation_type": self.navigation_type,
            "target": self.target,
        }
        if self.navigation_type == "page" and self.navigate_to_page_id:
            kwargs["navigate_to_page_id"] = self.navigate_to_page_id
            kwargs["page_parameters"] = [
                {"name": p["name"], "value": BaserowFormulaObject.create(p["value"])}
                for p in self.page_parameters
            ]
        elif self.navigation_type == "custom" and self.navigate_to_url:
            kwargs["navigate_to_url"] = BaserowFormulaObject.create(
                self.navigate_to_url
            )
        return kwargs


class ImageElementCreate(ElementBase, RefCreate):
    """Image display element."""

    type: Literal["image"] = "image"
    image_source_type: Literal["upload", "url"] = Field(default="url")
    image_url: str = Field(default="", description="URL or formula for image source")
    alt_text: str = Field(default="")

    def to_orm_kwargs(self, user, page) -> dict:
        return {
            "image_source_type": self.image_source_type,
            "image_url": BaserowFormulaObject.create(self.image_url)
            if self.image_url
            else BaserowFormulaObject.create("''"),
            "alt_text": BaserowFormulaObject.create(self.alt_text)
            if self.alt_text
            else BaserowFormulaObject.create("''"),
        }


# =============================================================================
# Form Input Elements
# =============================================================================


class InputTextElementCreate(ElementBase, RefCreate):
    """Text input form element."""

    type: Literal["input_text"] = "input_text"
    label: str = Field(..., description="Input label")
    placeholder: str = Field(default="")
    default_value: str = Field(default="")
    required: bool = Field(default=False)
    validation_type: Literal["any", "email", "integer"] = Field(default="any")
    is_multiline: bool = Field(default=False)
    rows: int = Field(default=3, description="Rows for multiline input")

    def to_orm_kwargs(self, user, page) -> dict:
        return {
            "label": BaserowFormulaObject.create(f"'{self.label}'"),
            "placeholder": BaserowFormulaObject.create(f"'{self.placeholder}'"),
            "default_value": BaserowFormulaObject.create(
                self.default_value if self.default_value else "''"
            ),
            "required": self.required,
            "validation_type": self.validation_type,
            "is_multiline": self.is_multiline,
            "rows": self.rows,
        }


class ChoiceOption(BaseModel):
    """Option for choice element."""

    name: str
    value: str


class ChoiceElementCreate(ElementBase, RefCreate):
    """Dropdown or radio/checkbox choice element."""

    type: Literal["choice"] = "choice"
    label: str = Field(...)
    placeholder: str = Field(default="")
    required: bool = Field(default=False)
    multiple: bool = Field(default=False)
    show_as_dropdown: bool = Field(default=True)
    options: list[ChoiceOption] = Field(
        default_factory=list, description="List of options"
    )

    def to_orm_kwargs(self, user, page) -> dict:
        return {
            "label": BaserowFormulaObject.create(f"'{self.label}'"),
            "placeholder": BaserowFormulaObject.create(f"'{self.placeholder}'"),
            "required": self.required,
            "multiple": self.multiple,
            "show_as_dropdown": self.show_as_dropdown,
        }

    def get_options(self) -> list[dict]:
        """Get options in format for ORM."""

        return [{"name": o.name, "value": o.value} for o in self.options]


class CheckboxElementCreate(ElementBase, RefCreate):
    """Checkbox form element."""

    type: Literal["checkbox"] = "checkbox"
    label: str = Field(...)
    default_value: str = Field(default="false")
    required: bool = Field(default=False)

    def to_orm_kwargs(self, user, page) -> dict:
        return {
            "label": BaserowFormulaObject.create(f"'{self.label}'"),
            "default_value": BaserowFormulaObject.create(self.default_value),
            "required": self.required,
        }


class DateTimePickerElementCreate(ElementBase, RefCreate):
    """Date/time picker form element."""

    type: Literal["datetime_picker"] = "datetime_picker"
    label: str = Field(...)
    required: bool = Field(default=False)
    include_time: bool = Field(default=False)
    date_format: Literal["EU", "US", "ISO"] = Field(default="EU")

    def to_orm_kwargs(self, user, page) -> dict:
        return {
            "label": BaserowFormulaObject.create(f"'{self.label}'"),
            "required": self.required,
            "include_time": self.include_time,
            "date_format": self.date_format,
        }


class RecordSelectorElementCreate(ElementBase, RefCreate):
    """Record selector dropdown linked to a data source."""

    type: Literal["record_selector"] = "record_selector"
    label: str = Field(...)
    data_source_id: Optional[int] = Field(
        default=None, description="Data source ID (resolved from data_source_ref)"
    )
    required: bool = Field(default=False)
    multiple: bool = Field(default=False)
    placeholder: str = Field(default="")

    def to_orm_kwargs(self, user, page) -> dict:
        return {
            "label": BaserowFormulaObject.create(f"'{self.label}'"),
            "data_source_id": self.data_source_id,
            "required": self.required,
            "multiple": self.multiple,
            "placeholder": BaserowFormulaObject.create(f"'{self.placeholder}'"),
        }


# =============================================================================
# Collection Elements
# =============================================================================


class TableFieldConfig(BaseModel):
    """Configuration for a table column."""

    name: str = Field(..., description="Column header name")
    type: Literal["text", "link", "button", "tags"] = Field(default="text")


class TableElementCreate(ElementBase, RefCreate):
    """Table element to display data from a data source."""

    type: Literal["table"] = "table"
    data_source_id: Optional[int] = Field(
        default=None, description="Data source ID (resolved from data_source_ref)"
    )
    items_per_page: int = Field(default=20)
    button_load_more_label: str = Field(default="Load more")
    fields: list[TableFieldConfig] = Field(
        default_factory=list, description="Table column configurations"
    )

    def to_orm_kwargs(self, user, page) -> dict:
        orm_kwargs = {
            "data_source_id": self.data_source_id,
            "items_per_page": self.items_per_page,
            "button_load_more_label": BaserowFormulaObject.create(
                f"'{self.button_load_more_label}'"
            ),
        }

        if self.data_source_id and not self.fields:
            data_source = next(
                iter(
                    DataSourceHandler().get_data_sources(
                        page,
                        base_queryset=DataSource.objects.filter(id=self.data_source_id),
                        with_shared=True,
                    )
                ),
                None,
            )

            if data_source and hasattr(data_source.service, "table_id"):
                service = data_source.service
                orm_kwargs["fields"] = service.get_type().get_default_collection_fields(
                    service
                )
        return orm_kwargs


class RepeatElementCreate(ElementBase, RefCreate):
    """Repeater element that duplicates children for each data source item."""

    type: Literal["repeat"] = "repeat"
    data_source_id: Optional[int] = Field(
        default=None, description="Data source ID (resolved from data_source_ref)"
    )
    orientation: Literal["vertical", "horizontal"] = Field(default="vertical")
    items_per_page: int = Field(default=20)
    items_per_row: dict = Field(
        default_factory=lambda: {"desktop": 3, "tablet": 2, "smartphone": 1}
    )

    def to_orm_kwargs(self, user, page) -> dict:
        return {
            "data_source_id": self.data_source_id,
            "orientation": self.orientation,
            "items_per_page": self.items_per_page,
            "items_per_row": self.items_per_row,
        }


# =============================================================================
# Discriminated Union
# =============================================================================

AnyElementCreate = Annotated[
    ColumnElementCreate
    | FormContainerElementCreate
    | SimpleContainerElementCreate
    | HeadingElementCreate
    | TextElementCreate
    | ButtonElementCreate
    | LinkElementCreate
    | ImageElementCreate
    | InputTextElementCreate
    | ChoiceElementCreate
    | CheckboxElementCreate
    | DateTimePickerElementCreate
    | RecordSelectorElementCreate
    | TableElementCreate
    | RepeatElementCreate,
    Field(discriminator="type"),
]


# =============================================================================
# Element Type Registry
# =============================================================================


class ElementTypeMapping:
    """Maps element type strings to their ORM element type names."""

    _mapping = {
        "column": "column",
        "form_container": "form_container",
        "simple_container": "simple_container",
        "heading": "heading",
        "text": "text",
        "button": "button",
        "link": "link",
        "image": "image",
        "input_text": "input_text",
        "choice": "choice",
        "checkbox": "checkbox",
        "datetime_picker": "datetime_picker",
        "record_selector": "record_selector",
        "table": "table",
        "repeat": "repeat",
    }

    @classmethod
    def get_orm_type(cls, element_type: str) -> str:
        """Get the ORM element type name for a given element type."""

        return cls._mapping.get(element_type, element_type)


element_type_mapping = ElementTypeMapping()


# =============================================================================
# Element Item (for listing)
# =============================================================================


class ElementItem(BaseModel):
    """Existing element with ID."""

    id: int
    type: str
    order: str
    parent_element_id: Optional[int] = None
    place_in_container: Optional[str] = None

    @classmethod
    def from_orm(cls, element) -> "ElementItem":
        """Create ElementItem from ORM Element instance."""

        return cls(
            id=element.id,
            type=element.get_type().type,
            order=str(element.order),
            parent_element_id=element.parent_element_id,
            place_in_container=element.place_in_container,
        )
