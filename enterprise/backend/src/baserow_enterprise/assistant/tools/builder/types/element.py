"""
Builder element type models.

Defines ``ElementItemCreate`` (flat) for creating UI elements and
``ElementItem`` for reading them back. Uses dispatch tables for
per-type ORM conversion and formula handling.

## Dispatch Tables (add entries when adding a new element type)

When adding support for a new element type, update these tables:

- ``_TO_ORM``: Convert ``ElementItemCreate`` → ORM kwargs for creation.
- ``_POST_CREATE``: Hook called after ORM creation (e.g. for child objects).
- ``_GET_FORMULAS``: Return ``{field: description}`` for LLM formula generation.
- ``_UPDATE_FORMULAS``: Apply generated formulas to the ORM element.
- ``_TO_ORM_UPDATE``: Convert ``ElementUpdate`` → ORM kwargs for updates.
- ``_GET_UPDATE_FORMULAS``: Return formulas needed for element updates.

Not all tables need entries — only add to those relevant for the new type.
"""

import uuid
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
    wrap_static_string,
)
from baserow_enterprise.assistant.types import BaseModel

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.contrib.builder.elements.models import Element
    from baserow.contrib.builder.pages.models import Page
    from baserow_enterprise.assistant.tools.builder.agents import BuilderFormulaContext

# ---------------------------------------------------------------------------
# Element type literal (excluding iframe)
# ---------------------------------------------------------------------------

ElementType = Literal[
    "heading",
    "text",
    "button",
    "link",
    "image",
    "column",
    "form_container",
    "simple_container",
    "input_text",
    "choice",
    "checkbox",
    "datetime_picker",
    "record_selector",
    "table",
    "repeat",
    "header",
    "footer",
    "menu",
    "auth_form",
]

CONTAINER_ELEMENT_TYPES = {
    "column",
    "form_container",
    "simple_container",
    "repeat",
    "header",
    "footer",
}

# Elements that live on the shared page (visible across all pages).
_SHARED_PAGE_TYPES = {"header", "footer"}


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ParameterMapping(BaseModel):
    """Key-value parameter mapping for page/query parameters on links."""

    name: str = Field(..., description="Parameter name.")
    value: str = Field(..., description="Parameter value formula.")


class ChoiceOption(BaseModel):
    """Option for choice element."""

    name: str
    value: str


class ItemsPerRow(BaseModel):
    """Responsive items-per-row for repeat elements."""

    desktop: int = Field(default=3)
    tablet: int = Field(default=2)
    smartphone: int = Field(default=1)


class MenuItemCreate(BaseModel):
    """A menu item linking to an internal page."""

    name: str = Field(..., description="Display text.")
    page_id: int = Field(..., description="Target page ID.")


class TableFieldConfig(BaseModel):
    """
    Column configuration for table elements.

    ``type`` is ``"text"`` (default) or ``"button"``.
    """

    name: str = Field(..., description="Column header name.")
    type: Literal["text", "button", "link", "tags"] = Field(
        default="text", description="Column type."
    )

    # text columns
    value: str | None = Field(
        default=None,
        description="(text) Cell value formula. Supports $formula: prefix.",
    )

    # button columns
    label: str | None = Field(default=None, description="(button) Button label.")


# ---------------------------------------------------------------------------
# ORM dispatch: element_type -> kwargs builder
# ---------------------------------------------------------------------------


def _heading_orm(el: "ElementItemCreate", user, page) -> dict:
    return {
        "value": BaserowFormulaObject.create(
            literal_or_placeholder(el.value)
            if needs_formula(el.value)
            else wrap_static_string(el.value or ""),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        ),
        "level": el.level or 1,
    }


def _text_orm(el: "ElementItemCreate", user, page) -> dict:
    return {
        "value": BaserowFormulaObject.create(
            literal_or_placeholder(el.value)
            if needs_formula(el.value)
            else wrap_static_string(el.value or ""),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        ),
        "format": el.format or "plain",
    }


def _button_orm(el: "ElementItemCreate", user, page) -> dict:
    text = el.value or el.label or ""
    return {
        "value": BaserowFormulaObject.create(
            literal_or_placeholder(text)
            if needs_formula(text)
            else wrap_static_string(text),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        ),
    }


def _link_orm(el: "ElementItemCreate", user, page) -> dict:
    kwargs: dict[str, Any] = {
        "value": BaserowFormulaObject.create(
            literal_or_placeholder(el.value)
            if needs_formula(el.value)
            else wrap_static_string(el.value or ""),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        ),
        "variant": el.link_variant or "link",
        "navigation_type": el.navigation_type or "page",
        "target": el.link_target or "self",
    }

    nav = el.navigation_type or "page"
    if nav == "page" and el.navigate_to_page_id:
        kwargs["navigate_to_page_id"] = el.navigate_to_page_id
        kwargs["page_parameters"] = [
            {
                "name": p.name,
                "value": BaserowFormulaObject.create(
                    p.value, mode=BASEROW_FORMULA_MODE_ADVANCED
                ),
            }
            for p in (el.link_page_parameters or [])
        ]
    elif nav == "custom" and el.navigate_to_url:
        kwargs["navigate_to_url"] = BaserowFormulaObject.create(
            literal_or_placeholder(el.navigate_to_url)
            if needs_formula(el.navigate_to_url)
            else wrap_static_string(el.navigate_to_url),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )

    return kwargs


def _image_orm(el: "ElementItemCreate", user, page) -> dict:
    image_url = el.image_url or ""
    alt_text = el.alt_text or ""
    return {
        "image_source_type": el.image_source_type or "url",
        "image_url": BaserowFormulaObject.create(
            literal_or_placeholder(image_url)
            if needs_formula(image_url)
            else wrap_static_string(image_url)
            if image_url
            else "''",
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        ),
        "alt_text": BaserowFormulaObject.create(
            literal_or_placeholder(alt_text)
            if needs_formula(alt_text)
            else wrap_static_string(alt_text)
            if alt_text
            else "''",
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        ),
    }


def _column_orm(el: "ElementItemCreate", user, page) -> dict:
    return {
        "column_amount": el.column_amount or 2,
        "column_gap": el.column_gap or 20,
        "alignment": el.column_alignment or "top",
    }


def _form_container_orm(el: "ElementItemCreate", user, page) -> dict:
    return {
        "submit_button_label": BaserowFormulaObject.create(
            f"'{el.submit_button_label or 'Submit'}'",
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        ),
        "reset_initial_values_post_submission": el.reset_initial_values_post_submission
        or False,
    }


def _input_text_orm(el: "ElementItemCreate", user, page) -> dict:
    default_value = el.default_value or ""
    return {
        "label": BaserowFormulaObject.create(
            f"'{el.label or ''}'", mode=BASEROW_FORMULA_MODE_ADVANCED
        ),
        "placeholder": BaserowFormulaObject.create(
            f"'{el.placeholder or ''}'", mode=BASEROW_FORMULA_MODE_ADVANCED
        ),
        "default_value": BaserowFormulaObject.create(
            literal_or_placeholder(default_value)
            if needs_formula(default_value)
            else (wrap_static_string(default_value) if default_value else "''"),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        ),
        "required": el.required or False,
        "validation_type": el.validation_type or "any",
        "is_multiline": el.is_multiline or False,
        "rows": el.rows or 3,
    }


def _choice_orm(el: "ElementItemCreate", user, page) -> dict:
    default_value = el.default_value or ""
    return {
        "label": BaserowFormulaObject.create(
            f"'{el.label or ''}'", mode=BASEROW_FORMULA_MODE_ADVANCED
        ),
        "placeholder": BaserowFormulaObject.create(
            f"'{el.placeholder or ''}'", mode=BASEROW_FORMULA_MODE_ADVANCED
        ),
        "default_value": BaserowFormulaObject.create(
            literal_or_placeholder(default_value)
            if needs_formula(default_value)
            else (wrap_static_string(default_value) if default_value else "''"),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        ),
        "required": el.required or False,
        "multiple": el.multiple or False,
        "show_as_dropdown": el.show_as_dropdown
        if el.show_as_dropdown is not None
        else True,
    }


def _checkbox_orm(el: "ElementItemCreate", user, page) -> dict:
    default_value = el.default_value or "false"
    return {
        "label": BaserowFormulaObject.create(
            f"'{el.label or ''}'", mode=BASEROW_FORMULA_MODE_ADVANCED
        ),
        "default_value": BaserowFormulaObject.create(
            literal_or_placeholder(default_value)
            if needs_formula(default_value)
            else default_value,
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        ),
        "required": el.required or False,
    }


def _datetime_picker_orm(el: "ElementItemCreate", user, page) -> dict:
    return {
        "label": BaserowFormulaObject.create(
            f"'{el.label or ''}'", mode=BASEROW_FORMULA_MODE_ADVANCED
        ),
        "required": el.required or False,
        "include_time": el.include_time or False,
        "date_format": el.date_format or "EU",
    }


def _record_selector_orm(el: "ElementItemCreate", user, page) -> dict:
    return {
        "label": BaserowFormulaObject.create(
            f"'{el.label or ''}'", mode=BASEROW_FORMULA_MODE_ADVANCED
        ),
        "data_source_id": el.data_source,
        "required": el.required or False,
        "multiple": el.multiple or False,
        "placeholder": BaserowFormulaObject.create(
            f"'{el.placeholder or ''}'", mode=BASEROW_FORMULA_MODE_ADVANCED
        ),
    }


def _table_orm(el: "ElementItemCreate", user, page) -> dict:
    kwargs: dict[str, Any] = {
        "data_source_id": el.data_source,
        "items_per_page": el.items_per_page or 20,
        "button_load_more_label": BaserowFormulaObject.create(
            f"'{el.button_load_more_label or 'Load more'}'",
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        ),
    }

    if el.fields:
        kwargs["fields"] = _convert_table_fields(el)
    elif el.data_source:
        # Auto-generate default fields from data source
        from baserow.contrib.builder.data_sources.service import DataSourceService

        data_source = next(
            iter(
                DataSourceService()
                .get_data_sources(user, page, with_shared=True)
                .filter(id=el.data_source)
            ),
            None,
        )
        if data_source and hasattr(data_source.service, "table_id"):
            service = data_source.service
            kwargs["fields"] = service.get_type().get_default_collection_fields(service)

    return kwargs


def _repeat_orm(el: "ElementItemCreate", user, page) -> dict:
    items_per_row = (
        el.repeat_items_per_row.model_dump()
        if el.repeat_items_per_row
        else ItemsPerRow().model_dump()
    )
    return {
        "data_source_id": el.data_source,
        "orientation": el.orientation or "vertical",
        "items_per_page": el.items_per_page or 20,
        "items_per_row": items_per_row,
    }


def _header_orm(el: "ElementItemCreate", user, page) -> dict:
    return {"share_type": el.share_type or "all"}


def _footer_orm(el: "ElementItemCreate", user, page) -> dict:
    return {"share_type": el.share_type or "all"}


def _menu_orm(el: "ElementItemCreate", user, page) -> dict:
    kwargs: dict[str, Any] = {
        "orientation": el.menu_orientation or "horizontal",
        "alignment": el.menu_alignment or "left",
    }
    if el.menu_items:
        kwargs["menu_items"] = [
            {
                "uid": str(uuid.uuid4()),
                "type": "link",
                "variant": "link",
                "name": item.name,
                "navigation_type": "page",
                "navigate_to_page_id": item.page_id,
                "target": "self",
            }
            for item in el.menu_items
        ]
    return kwargs


_TO_ORM: dict[str, Any] = {
    "heading": _heading_orm,
    "text": _text_orm,
    "button": _button_orm,
    "link": _link_orm,
    "image": _image_orm,
    "column": _column_orm,
    "form_container": _form_container_orm,
    "simple_container": lambda el, u, p: {},
    "input_text": _input_text_orm,
    "choice": _choice_orm,
    "checkbox": _checkbox_orm,
    "datetime_picker": _datetime_picker_orm,
    "record_selector": _record_selector_orm,
    "table": _table_orm,
    "repeat": _repeat_orm,
    "header": _header_orm,
    "footer": _footer_orm,
    "menu": _menu_orm,
    "auth_form": lambda el, u, p: {
        k: v
        for k, v in {
            "user_source_id": el.user_source_id,
            "login_button_label": el.login_button_label or "",
        }.items()
        if v is not None
    },
}


# ---------------------------------------------------------------------------
# Post-create dispatch
# ---------------------------------------------------------------------------


def _choice_post_create(el: "ElementItemCreate", user, orm_element, page) -> None:
    """Create choice options after the element is created."""
    if el.choice_options:
        from baserow.contrib.builder.elements.models import ChoiceElementOption

        ChoiceElementOption.objects.bulk_create(
            [
                ChoiceElementOption(choice=orm_element, name=o.name, value=o.value)
                for o in el.choice_options
            ]
        )


def _header_footer_post_create(
    el: "ElementItemCreate", user, orm_element, page
) -> None:
    """Set page associations and auto-create a child menu for header/footer elements."""

    if el.page_ids:
        orm_element.pages.set(el.page_ids)

    # If menu_items were provided on the header/footer itself, create a child
    # menu element — headers are containers, not menus.
    if el.menu_items:
        from baserow.contrib.builder.elements.registries import element_type_registry
        from baserow.contrib.builder.elements.service import ElementService

        menu_items_orm = [
            {
                "uid": str(uuid.uuid4()),
                "type": "link",
                "variant": "link",
                "name": item.name,
                "navigation_type": "page",
                "navigate_to_page_id": item.page_id,
                "target": "self",
            }
            for item in el.menu_items
        ]
        menu_type = element_type_registry.get("menu")
        ElementService().create_element(
            user,
            menu_type,
            page,
            parent_element_id=orm_element.id,
            menu_items=menu_items_orm,
        )


def _table_post_create(el: "ElementItemCreate", user, orm_element, page) -> list:
    """Create button-column workflow actions and enable filter/sort/search.

    Returns a list of ``(orm_action, action_create)`` pairs for any
    button-column actions that were created (empty list if none).
    """

    if not el.fields:
        return []

    from baserow.contrib.builder.elements.models import CollectionElementPropertyOptions
    from baserow_enterprise.assistant.tools.builder.helpers import (
        create_table_button_actions,
        get_local_baserow_integration,
    )

    integration = get_local_baserow_integration(user, page.builder)
    action_pairs = create_table_button_actions(user, page, orm_element, el, integration)

    # Auto-enable filter/sort/search for text columns referencing real fields.
    table_fields = _resolve_table_fields(el.data_source)
    property_options = []
    for field_cfg in el.fields:
        if field_cfg.type != "text":
            continue
        match = table_fields.get(field_cfg.name.lower())
        if match:
            field_id, _ = match
            property_options.append(
                CollectionElementPropertyOptions(
                    element=orm_element,
                    schema_property=f"field_{field_id}",
                    filterable=True,
                    sortable=True,
                    searchable=True,
                )
            )
    if property_options:
        CollectionElementPropertyOptions.objects.bulk_create(
            property_options, ignore_conflicts=True
        )

    return action_pairs


_POST_CREATE: dict[str, Any] = {
    "choice": _choice_post_create,
    "header": _header_footer_post_create,
    "footer": _header_footer_post_create,
    "table": _table_post_create,
}


# ---------------------------------------------------------------------------
# Formula dispatch: get_formulas_to_create
# ---------------------------------------------------------------------------


def _value_formula(el: "ElementItemCreate", orm_element, context) -> dict[str, str]:
    """Get formulas for elements with a ``value`` field."""
    if el.value and needs_formula(el.value):
        return {"value": formula_desc(el.value)}
    return {}


def _link_formulas(el: "ElementItemCreate", orm_element, context) -> dict[str, str]:
    """Get formulas for link elements."""
    formulas: dict[str, str] = {}
    if el.value and needs_formula(el.value):
        formulas["value"] = formula_desc(el.value)
    if el.navigate_to_url and needs_formula(el.navigate_to_url):
        formulas["navigate_to_url"] = formula_desc(el.navigate_to_url)
    return formulas


def _image_formulas(el: "ElementItemCreate", orm_element, context) -> dict[str, str]:
    """Get formulas for image elements."""
    formulas: dict[str, str] = {}
    if el.image_url and needs_formula(el.image_url):
        formulas["image_url"] = formula_desc(el.image_url)
    if el.alt_text and needs_formula(el.alt_text):
        formulas["alt_text"] = formula_desc(el.alt_text)
    return formulas


def _default_value_formula(
    el: "ElementItemCreate", orm_element, context
) -> dict[str, str]:
    """Get formulas for form elements with a ``default_value`` field."""
    if el.default_value and needs_formula(el.default_value):
        return {"default_value": formula_desc(el.default_value)}
    return {}


def _table_formulas(el: "ElementItemCreate", orm_element, context) -> dict[str, str]:
    """Get formulas for table collection fields."""
    if not el.fields:
        return {}

    formulas: dict[str, str] = {}
    collection_fields = list(orm_element.fields.order_by("order"))

    for i, field_cfg in enumerate(el.fields):
        existing_config = (
            collection_fields[i].config if i < len(collection_fields) else None
        )

        if field_cfg.type == "text":
            value = field_cfg.value or ""
            existing = ""
            if existing_config:
                existing = existing_config.get("value", {}).get("formula", "")

            if value and needs_formula(value):
                if not existing or existing == "''":
                    formulas[f"fields.{i}.value"] = formula_desc(value)
            elif not value and el.data_source:
                if not existing or existing == "''":
                    formulas[f"fields.{i}.value"] = (
                        f"the {field_cfg.name} value from the current record"
                    )

        elif field_cfg.type == "button" and field_cfg.label:
            if needs_formula(field_cfg.label):
                formulas[f"fields.{i}.label"] = formula_desc(field_cfg.label)

    return formulas


_GET_FORMULAS: dict[str, Any] = {
    "heading": _value_formula,
    "text": _value_formula,
    "button": _value_formula,
    "link": _link_formulas,
    "image": _image_formulas,
    "input_text": _default_value_formula,
    "choice": _default_value_formula,
    "checkbox": _default_value_formula,
    "datetime_picker": _default_value_formula,
    "table": _table_formulas,
}


# ---------------------------------------------------------------------------
# Formula dispatch: update_element_with_formulas
# ---------------------------------------------------------------------------


def _update_simple_formulas(
    el: "ElementItemCreate",
    user: "AbstractUser",
    orm_element: "Element",
    formulas: dict[str, str],
) -> None:
    """Default formula updater — sets fields directly on the element."""
    from baserow.contrib.builder.elements.service import ElementService

    kwargs = {}
    for field_name, formula in formulas.items():
        if "." in field_name:
            continue
        if hasattr(orm_element, field_name):
            kwargs[field_name] = BaserowFormulaObject.create(
                formula, mode=BASEROW_FORMULA_MODE_ADVANCED
            )

    if kwargs:
        ElementService().update_element(user, orm_element, **kwargs)


def _update_table_formulas(
    el: "ElementItemCreate",
    user: "AbstractUser",
    orm_element: "Element",
    formulas: dict[str, str],
) -> None:
    """Update collection field configs for table elements."""
    if not formulas:
        return

    collection_fields = list(orm_element.fields.order_by("order"))
    for key, formula in formulas.items():
        parts = key.split(".")
        if len(parts) != 3 or parts[0] != "fields":
            continue
        index = int(parts[1])
        config_key = parts[2]
        if 0 <= index < len(collection_fields):
            cf = collection_fields[index]
            cf.config[config_key] = BaserowFormulaObject.create(
                formula, mode=BASEROW_FORMULA_MODE_ADVANCED
            )
            cf.save(update_fields=["config"])


_UPDATE_FORMULAS: dict[str, Any] = {
    "table": _update_table_formulas,
}


# ---------------------------------------------------------------------------
# Table field helpers
# ---------------------------------------------------------------------------

# Formula path suffixes by field type — mirrors the mapping in
# LocalBaserowListRowsUserServiceType.get_default_collection_fields().
_FORMULA_PATH_SUFFIX: dict[str, str] = {
    "last_modified_by": ".name",
    "created_by": ".name",
    "single_select": ".value",
    "multiple_collaborators": ".*.name",
}
_ARRAY_FIELD_TYPES = {"multiple_select", "link_row"}


def _resolve_table_fields(data_source_id: int | None) -> dict[str, tuple[int, str]]:
    """
    Look up the data source's table and return a case-insensitive mapping
    of field name -> (field_id, field_type_str).
    """

    if not data_source_id:
        return {}
    try:
        from baserow.contrib.builder.data_sources.models import DataSource

        ds = DataSource.objects.select_related("service").get(id=data_source_id)
        table = ds.service.specific.table
        if table is None:
            return {}
        return {
            f.name.lower(): (f.id, f.get_type().type)
            for f in table.field_set.select_related("content_type").all()
        }
    except Exception:
        return {}


def _field_formula(field_id: int, field_type: str) -> str:
    """Build ``get('current_record.field_<id><suffix>')`` formula."""

    suffix = _FORMULA_PATH_SUFFIX.get(field_type, "")
    if not suffix and field_type in _ARRAY_FIELD_TYPES:
        suffix = ".*.value"
    return f"get('current_record.field_{field_id}{suffix}')"


def _convert_table_fields(
    el: "ElementItemCreate | None" = None,
    *,
    data_source_id: int | None = None,
    fields: list | None = None,
) -> list[dict]:
    """Convert TableFieldConfig list to ORM collection field format.

    Can be called with an ``ElementItemCreate`` (creation path) or with
    explicit ``data_source_id`` + ``fields`` (update path).
    """

    if el is not None:
        data_source_id = el.data_source  # type: ignore[assignment]
        fields = el.fields

    table_fields = _resolve_table_fields(data_source_id)
    result = []
    for field_cfg in fields or []:
        if field_cfg.type == "text":
            value = field_cfg.value or ""
            if value and not needs_formula(value):
                value_formula = wrap_static_string(value)
            else:
                match = table_fields.get(field_cfg.name.lower())
                value_formula = _field_formula(*match) if match else "''"
            result.append(
                {
                    "name": field_cfg.name,
                    "type": "text",
                    "config": {
                        "value": BaserowFormulaObject.create(
                            value_formula, mode=BASEROW_FORMULA_MODE_ADVANCED
                        )
                    },
                }
            )
        elif field_cfg.type == "button":
            label = field_cfg.label or field_cfg.name
            if needs_formula(label):
                label_formula = "''"
            else:
                label_formula = wrap_static_string(label)
            result.append(
                {
                    "name": field_cfg.name,
                    "type": "button",
                    "config": {
                        "label": BaserowFormulaObject.create(
                            label_formula, mode=BASEROW_FORMULA_MODE_ADVANCED
                        )
                    },
                }
            )
        elif field_cfg.type == "link":
            result.append({"name": field_cfg.name, "type": "link", "config": {}})
        elif field_cfg.type == "tags":
            result.append({"name": field_cfg.name, "type": "tags", "config": {}})

    return result


# ---------------------------------------------------------------------------
# ElementItemCreate (flat)
# ---------------------------------------------------------------------------


class ElementItemCreate(BaseModel):
    """
    Flat model for creating any builder UI element.

    Type-specific fields are optional. Dispatch tables route ORM conversion,
    post-creation hooks, and formula handling based on the ``type`` field.
    """

    ref: str = Field(..., description="Unique reference for this element.")
    type: ElementType = Field(..., description="Element type.")

    # -- Common fields ------------------------------------------------------

    parent_element: int | str | None = Field(
        default=None,
        description="Parent container: int ID (existing) or string ref (same batch).",
    )
    place_in_container: str | None = Field(
        default=None, description="Position in parent container (e.g. '0', '1')."
    )
    visibility: Literal["all", "logged-in", "not-logged"] = Field(default="all")
    role_type: Literal["allow_all", "allow_all_except", "disallow_all_except"] = Field(
        default="allow_all",
        description="Role access strategy. Only relevant when visibility='logged-in'.",
    )
    roles: list[str] = Field(
        default_factory=list,
        description="Role names for the access strategy.",
    )

    data_source: int | str | None = Field(
        default=None,
        description="Data source: int ID (existing) or string ref (same batch).",
    )

    # -- Display fields (heading, text, button, link) -----------------------

    value: str | None = Field(
        default=None,
        description="Display text (heading, text, button label, link text). Supports $formula: prefix.",
    )
    level: int | None = Field(default=None, description="(heading) Level 1-5.")
    format: str | None = Field(
        default=None, description="(text) 'plain' or 'markdown'."
    )

    # -- Link fields --------------------------------------------------------

    link_variant: Literal["link", "button"] | None = Field(
        default=None, description="(link) Display variant."
    )
    navigation_type: Literal["page", "custom"] | None = Field(
        default=None, description="(link) Navigation type."
    )
    navigate_to_page_id: int | None = Field(
        default=None, description="(link, open_page) Target page ID."
    )
    navigate_to_url: str | None = Field(
        default=None,
        description="(link) Custom URL. Supports $formula: prefix.",
    )
    link_page_parameters: list[ParameterMapping] | None = Field(
        default=None, description="(link) Page parameter mappings."
    )
    link_target: Literal["self", "blank"] | None = Field(
        default=None, description="(link) Navigation target."
    )

    # -- Image fields -------------------------------------------------------

    image_source_type: Literal["upload", "url"] | None = Field(
        default=None, description="(image) Source type."
    )
    image_url: str | None = Field(
        default=None,
        description="(image) Image URL. Supports $formula: prefix.",
    )
    alt_text: str | None = Field(
        default=None,
        description="(image) Alt text. Supports $formula: prefix.",
    )

    # -- Column fields ------------------------------------------------------

    column_amount: int | None = Field(
        default=None, description="(column) Number of columns (1-6)."
    )
    column_gap: int | None = Field(
        default=None, description="(column) Gap between columns in px."
    )
    column_alignment: Literal["top", "center", "bottom"] | None = Field(
        default=None, description="(column) Vertical alignment."
    )

    # -- Form container fields ----------------------------------------------

    submit_button_label: str | None = Field(
        default=None, description="(form_container) Submit button label."
    )
    reset_initial_values_post_submission: bool | None = Field(
        default=None, description="(form_container) Reset form after submit."
    )

    # -- Form input fields --------------------------------------------------

    label: str | None = Field(
        default=None,
        description="(form inputs) Field label.",
    )
    placeholder: str | None = Field(
        default=None, description="(form inputs) Placeholder text."
    )
    default_value: str | None = Field(
        default=None,
        description="(form inputs) Default value. Supports $formula: prefix.",
    )
    required: bool | None = Field(
        default=None, description="(form inputs) Required field."
    )

    # input_text specific
    validation_type: Literal["any", "email", "integer"] | None = Field(
        default=None, description="(input_text) Validation type."
    )
    is_multiline: bool | None = Field(
        default=None, description="(input_text) Multiline mode."
    )
    rows: int | None = Field(
        default=None, description="(input_text) Rows for multiline."
    )

    # choice specific
    multiple: bool | None = Field(
        default=None, description="(choice, record_selector) Allow multiple."
    )
    show_as_dropdown: bool | None = Field(
        default=None, description="(choice) Show as dropdown."
    )
    choice_options: list[ChoiceOption] | None = Field(
        default=None, description="(choice) List of options."
    )

    # datetime_picker specific
    include_time: bool | None = Field(
        default=None, description="(datetime_picker) Include time."
    )
    date_format: Literal["EU", "US", "ISO"] | None = Field(
        default=None, description="(datetime_picker) Date format."
    )

    # -- Collection fields (table, repeat) ----------------------------------

    items_per_page: int | None = Field(
        default=None, description="(table, repeat) Items per page."
    )
    button_load_more_label: str | None = Field(
        default=None, description="(table) Load more button label."
    )
    fields: list[TableFieldConfig] | None = Field(
        default=None, description="(table) Column configurations."
    )
    orientation: Literal["vertical", "horizontal"] | None = Field(
        default=None, description="(repeat, menu) Orientation."
    )
    repeat_items_per_row: ItemsPerRow | None = Field(
        default=None, description="(repeat) Items per row config."
    )

    # -- Navigation fields (header, footer, menu) ---------------------------

    share_type: Literal["all", "only", "except"] | None = Field(
        default=None, description="(header, footer) Page sharing."
    )
    page_ids: list[int] | None = Field(
        default=None, description="(header, footer) Page IDs for sharing."
    )
    menu_orientation: Literal["horizontal", "vertical"] | None = Field(
        default=None, description="(menu) Menu orientation."
    )
    menu_alignment: Literal["left", "center", "right", "justify"] | None = Field(
        default=None, description="(menu) Menu alignment."
    )
    menu_items: list[MenuItemCreate] | None = Field(
        default=None, description="(menu) Menu item configurations."
    )

    # -- Auth form fields ---------------------------------------------------

    user_source_id: int | None = Field(
        default=None,
        description="(auth_form) ID of the user source. Get it from setup_user_source.",
    )
    login_button_label: str | None = Field(
        default=None, description="(auth_form) Label for the login button."
    )

    # -- Properties ---------------------------------------------------------

    @property
    def use_shared_page(self) -> bool:
        """Whether this element should be created on the builder's shared page."""
        return self.type in _SHARED_PAGE_TYPES

    # -- ORM dispatch -------------------------------------------------------

    def to_orm_kwargs(self, user: "AbstractUser", page: "Page") -> dict:
        """Return kwargs for ``ElementService.create_element()``."""
        fn = _TO_ORM.get(self.type)
        kwargs = fn(self, user, page) if fn else {}

        if self.visibility != "all":
            kwargs["visibility"] = self.visibility
        if self.role_type != "allow_all":
            kwargs["role_type"] = self.role_type
        if self.roles:
            kwargs["roles"] = self.roles

        return kwargs

    def post_create(
        self,
        user: "AbstractUser",
        orm_element: "Element",
        page: "Page",
    ) -> list:
        """Hook called after ORM element creation.

        Returns a list of ``(orm_action, action_create)`` pairs for any
        workflow actions created as part of the element setup (e.g. button
        columns in table elements). Empty list if none.
        """

        fn = _POST_CREATE.get(self.type)
        if fn:
            return fn(self, user, orm_element, page) or []
        return []

    def get_formulas_to_create(
        self,
        orm_element: "Element",
        context: "BuilderFormulaContext",
    ) -> dict[str, str]:
        """Return ``{field_path: description}`` for LLM formula generation."""
        fn = _GET_FORMULAS.get(self.type)
        return fn(self, orm_element, context) if fn else {}

    def update_with_formulas(
        self,
        user: "AbstractUser",
        orm_element: "Element",
        formulas: dict[str, str],
    ) -> None:
        """Apply LLM-generated formulas to this element."""
        fn = _UPDATE_FORMULAS.get(self.type)
        if fn:
            fn(self, user, orm_element, formulas)
        else:
            _update_simple_formulas(self, user, orm_element, formulas)


# ---------------------------------------------------------------------------
# ElementItem (for listing)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Category-specific create models
# ---------------------------------------------------------------------------


class _ElementBase(BaseModel):
    """Shared fields for all category-specific element create models."""

    ref: str = Field(..., description="Unique reference for this element.")
    parent_element: int | str | None = Field(
        default=None,
        description="Parent container: int ID (existing) or string ref (same batch).",
    )
    place_in_container: str | None = Field(
        default=None, description="Position in parent container (e.g. '0', '1')."
    )


class DisplayElementCreate(_ElementBase):
    """
    Create display elements: heading, text, button, link, image.

    Use ``$formula:`` prefix for dynamic values (e.g. ``"$formula: the product name"``).
    Static strings are auto-wrapped.
    """

    type: Literal["heading", "text", "button", "link", "image"] = Field(
        ..., description="Element type."
    )
    value: str | None = Field(
        default=None,
        description="Display text (heading, text, button label, link text). Supports $formula: prefix.",
    )
    level: int | None = Field(default=None, description="(heading) Level 1-5.")
    format: str | None = Field(
        default=None, description="(text) 'plain' or 'markdown'."
    )
    navigation_type: Literal["page", "custom"] | None = Field(
        default=None, description="(link) Navigation type."
    )
    navigate_to_page_id: int | None = Field(
        default=None, description="(link) Target page ID."
    )
    navigate_to_url: str | None = Field(
        default=None,
        description="(link) Custom URL. Supports $formula: prefix.",
    )
    link_variant: Literal["link", "button"] | None = Field(
        default=None, description="(link) Display variant."
    )
    image_url: str | None = Field(
        default=None,
        description="(image) Image URL. Supports $formula: prefix.",
    )
    alt_text: str | None = Field(
        default=None,
        description="(image) Alt text. Supports $formula: prefix.",
    )

    def to_element_item_create(self) -> "ElementItemCreate":
        return ElementItemCreate(
            ref=self.ref,
            type=self.type,
            parent_element=self.parent_element,
            place_in_container=self.place_in_container,
            value=self.value,
            level=self.level,
            format=self.format,
            navigation_type=self.navigation_type,
            navigate_to_page_id=self.navigate_to_page_id,
            navigate_to_url=self.navigate_to_url,
            link_variant=self.link_variant,
            image_url=self.image_url,
            alt_text=self.alt_text,
        )


class LayoutElementCreate(_ElementBase):
    """
    Create layout/navigation elements: column, simple_container, header, footer, menu.

    Layout elements are containers — other elements go inside them via ``parent_element``.
    """

    type: Literal["column", "simple_container", "header", "footer", "menu"] = Field(
        ..., description="Element type."
    )
    column_amount: int | None = Field(
        default=None, description="(column) Number of columns (1-6)."
    )
    menu_items: list[MenuItemCreate] | None = Field(
        default=None, description="(menu) Menu item configurations."
    )
    share_type: Literal["all", "only", "except"] | None = Field(
        default=None,
        description="(header, footer) Page sharing: 'all' (default), 'only' (show on page_ids only), 'except' (hide on page_ids).",
    )
    page_ids: list[int] | None = Field(
        default=None,
        description="(header, footer) Page IDs for share_type='only' or 'except'.",
    )

    def to_element_item_create(self) -> "ElementItemCreate":
        return ElementItemCreate(
            ref=self.ref,
            type=self.type,
            parent_element=self.parent_element,
            place_in_container=self.place_in_container,
            column_amount=self.column_amount,
            menu_items=self.menu_items,
            share_type=self.share_type,
            page_ids=self.page_ids,
        )


class FormElementCreate(_ElementBase):
    """
    Create form elements: form_container, input_text, choice, checkbox, datetime_picker, record_selector.

    Form inputs go inside a ``form_container`` (set ``parent_element`` to the form ref).
    Use ``$formula:`` prefix for dynamic default values.
    """

    type: Literal[
        "form_container",
        "input_text",
        "choice",
        "checkbox",
        "datetime_picker",
        "record_selector",
    ] = Field(..., description="Element type.")
    label: str | None = Field(default=None, description="(form inputs) Field label.")
    placeholder: str | None = Field(
        default=None, description="(form inputs) Placeholder text."
    )
    default_value: str | None = Field(
        default=None,
        description="(form inputs) Default value. Supports $formula: prefix.",
    )
    required: bool | None = Field(
        default=None, description="(form inputs) Required field."
    )
    validation_type: Literal["any", "email", "integer"] | None = Field(
        default=None, description="(input_text) Validation type."
    )
    is_multiline: bool | None = Field(
        default=None, description="(input_text) Multiline mode."
    )
    multiple: bool | None = Field(
        default=None, description="(choice, record_selector) Allow multiple."
    )
    choice_options: list[ChoiceOption] | None = Field(
        default=None, description="(choice) List of options."
    )
    include_time: bool | None = Field(
        default=None, description="(datetime_picker) Include time."
    )
    date_format: Literal["EU", "US", "ISO"] | None = Field(
        default=None, description="(datetime_picker) Date format."
    )
    submit_button_label: str | None = Field(
        default=None, description="(form_container) Submit button label."
    )
    data_source: int | str | None = Field(
        default=None,
        description="(record_selector) Data source: int ID or string ref.",
    )

    def to_element_item_create(self) -> "ElementItemCreate":
        return ElementItemCreate(
            ref=self.ref,
            type=self.type,
            parent_element=self.parent_element,
            place_in_container=self.place_in_container,
            label=self.label,
            placeholder=self.placeholder,
            default_value=self.default_value,
            required=self.required,
            validation_type=self.validation_type,
            is_multiline=self.is_multiline,
            multiple=self.multiple,
            choice_options=self.choice_options,
            include_time=self.include_time,
            date_format=self.date_format,
            submit_button_label=self.submit_button_label,
            data_source=self.data_source,
        )


class CollectionElementCreate(_ElementBase):
    """
    Create collection elements: table, repeat.

    These display data from a data source. Create data sources first, then reference them here.
    """

    type: Literal["table", "repeat"] = Field(..., description="Element type.")
    data_source: int | str | None = Field(
        default=None,
        description="Data source: int ID (existing) or string ref (same batch).",
    )
    fields: list[TableFieldConfig] | None = Field(
        default=None, description="(table) Column configurations."
    )
    orientation: Literal["vertical", "horizontal"] | None = Field(
        default=None, description="(repeat) Orientation."
    )

    def to_element_item_create(self) -> "ElementItemCreate":
        return ElementItemCreate(
            ref=self.ref,
            type=self.type,
            parent_element=self.parent_element,
            place_in_container=self.place_in_container,
            data_source=self.data_source,
            fields=self.fields,
            orientation=self.orientation,
        )


# ---------------------------------------------------------------------------
# ElementUpdate (flat, for updating existing elements)
# ---------------------------------------------------------------------------


def _heading_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    if el.value is not None:
        kwargs["value"] = BaserowFormulaObject.create(
            literal_or_placeholder(el.value)
            if needs_formula(el.value)
            else wrap_static_string(el.value),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )
    if el.level is not None:
        kwargs["level"] = el.level
    return kwargs


def _text_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    if el.value is not None:
        kwargs["value"] = BaserowFormulaObject.create(
            literal_or_placeholder(el.value)
            if needs_formula(el.value)
            else wrap_static_string(el.value),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )
    if el.format is not None:
        kwargs["format"] = el.format
    return kwargs


def _button_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    text = el.value or el.label
    if text is not None:
        kwargs["value"] = BaserowFormulaObject.create(
            literal_or_placeholder(text)
            if needs_formula(text)
            else wrap_static_string(text),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )
    return kwargs


def _link_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    if el.value is not None:
        kwargs["value"] = BaserowFormulaObject.create(
            literal_or_placeholder(el.value)
            if needs_formula(el.value)
            else wrap_static_string(el.value),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )
    if el.link_variant is not None:
        kwargs["variant"] = el.link_variant
    if el.navigation_type is not None:
        kwargs["navigation_type"] = el.navigation_type
    if el.link_target is not None:
        kwargs["target"] = el.link_target
    if el.navigate_to_page_id is not None:
        kwargs["navigate_to_page_id"] = el.navigate_to_page_id
    if el.navigate_to_url is not None:
        kwargs["navigate_to_url"] = BaserowFormulaObject.create(
            literal_or_placeholder(el.navigate_to_url)
            if needs_formula(el.navigate_to_url)
            else wrap_static_string(el.navigate_to_url),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )
    return kwargs


def _image_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    if el.image_source_type is not None:
        kwargs["image_source_type"] = el.image_source_type
    if el.image_url is not None:
        kwargs["image_url"] = BaserowFormulaObject.create(
            literal_or_placeholder(el.image_url)
            if needs_formula(el.image_url)
            else wrap_static_string(el.image_url),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )
    if el.alt_text is not None:
        kwargs["alt_text"] = BaserowFormulaObject.create(
            literal_or_placeholder(el.alt_text)
            if needs_formula(el.alt_text)
            else wrap_static_string(el.alt_text),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )
    return kwargs


def _column_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    if el.column_amount is not None:
        kwargs["column_amount"] = el.column_amount
    if el.column_gap is not None:
        kwargs["column_gap"] = el.column_gap
    if el.column_alignment is not None:
        kwargs["alignment"] = el.column_alignment
    return kwargs


def _form_container_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    if el.submit_button_label is not None:
        kwargs["submit_button_label"] = BaserowFormulaObject.create(
            f"'{el.submit_button_label}'",
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )
    return kwargs


def _input_text_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    if el.label is not None:
        kwargs["label"] = BaserowFormulaObject.create(
            f"'{el.label}'", mode=BASEROW_FORMULA_MODE_ADVANCED
        )
    if el.placeholder is not None:
        kwargs["placeholder"] = BaserowFormulaObject.create(
            f"'{el.placeholder}'", mode=BASEROW_FORMULA_MODE_ADVANCED
        )
    if el.default_value is not None:
        kwargs["default_value"] = BaserowFormulaObject.create(
            literal_or_placeholder(el.default_value)
            if needs_formula(el.default_value)
            else (wrap_static_string(el.default_value) if el.default_value else "''"),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )
    if el.required is not None:
        kwargs["required"] = el.required
    if el.validation_type is not None:
        kwargs["validation_type"] = el.validation_type
    if el.is_multiline is not None:
        kwargs["is_multiline"] = el.is_multiline
    if el.rows is not None:
        kwargs["rows"] = el.rows
    return kwargs


def _choice_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    if el.label is not None:
        kwargs["label"] = BaserowFormulaObject.create(
            f"'{el.label}'", mode=BASEROW_FORMULA_MODE_ADVANCED
        )
    if el.placeholder is not None:
        kwargs["placeholder"] = BaserowFormulaObject.create(
            f"'{el.placeholder}'", mode=BASEROW_FORMULA_MODE_ADVANCED
        )
    if el.default_value is not None:
        kwargs["default_value"] = BaserowFormulaObject.create(
            literal_or_placeholder(el.default_value)
            if needs_formula(el.default_value)
            else (wrap_static_string(el.default_value) if el.default_value else "''"),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )
    if el.required is not None:
        kwargs["required"] = el.required
    if el.multiple is not None:
        kwargs["multiple"] = el.multiple
    if el.show_as_dropdown is not None:
        kwargs["show_as_dropdown"] = el.show_as_dropdown
    return kwargs


def _checkbox_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    if el.label is not None:
        kwargs["label"] = BaserowFormulaObject.create(
            f"'{el.label}'", mode=BASEROW_FORMULA_MODE_ADVANCED
        )
    if el.default_value is not None:
        kwargs["default_value"] = BaserowFormulaObject.create(
            literal_or_placeholder(el.default_value)
            if needs_formula(el.default_value)
            else el.default_value,
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )
    if el.required is not None:
        kwargs["required"] = el.required
    return kwargs


def _datetime_picker_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    if el.label is not None:
        kwargs["label"] = BaserowFormulaObject.create(
            f"'{el.label}'", mode=BASEROW_FORMULA_MODE_ADVANCED
        )
    if el.default_value is not None:
        kwargs["default_value"] = BaserowFormulaObject.create(
            literal_or_placeholder(el.default_value)
            if needs_formula(el.default_value)
            else (wrap_static_string(el.default_value) if el.default_value else "''"),
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )
    if el.required is not None:
        kwargs["required"] = el.required
    if el.include_time is not None:
        kwargs["include_time"] = el.include_time
    if el.date_format is not None:
        kwargs["date_format"] = el.date_format
    return kwargs


def _repeat_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    if el.orientation is not None:
        kwargs["orientation"] = el.orientation
    if el.items_per_page is not None:
        kwargs["items_per_page"] = el.items_per_page
    return kwargs


def _table_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    if el.items_per_page is not None:
        kwargs["items_per_page"] = el.items_per_page
    if el.button_load_more_label is not None:
        kwargs["button_load_more_label"] = BaserowFormulaObject.create(
            f"'{el.button_load_more_label}'",
            mode=BASEROW_FORMULA_MODE_ADVANCED,
        )
    has_field_change = (
        el.fields is not None
        or el.add_fields is not None
        or el.remove_fields is not None
    )
    if has_field_change:
        from baserow.contrib.builder.elements.service import ElementHandler

        try:
            element = ElementHandler().get_element(el.element_id).specific
            ds_id = getattr(element, "data_source_id", None)
        except Exception:
            element = None
            ds_id = None

        if el.fields is not None:
            # Full replace
            kwargs["fields"] = _convert_table_fields(
                data_source_id=ds_id, fields=el.fields
            )
        else:
            # Incremental: start from existing fields
            existing = []
            if element is not None and hasattr(element, "fields"):
                for f in element.fields.order_by("order"):
                    existing.append(
                        {
                            "name": f.name,
                            "type": f.type,
                            "config": f.config,
                            "uid": str(f.uid),
                        }
                    )

            # Remove by name (case-insensitive)
            if el.remove_fields:
                remove_set = {n.lower() for n in el.remove_fields}
                existing = [f for f in existing if f["name"].lower() not in remove_set]

            # Append new columns
            if el.add_fields:
                new_fields = _convert_table_fields(
                    data_source_id=ds_id, fields=el.add_fields
                )
                existing.extend(new_fields)

            kwargs["fields"] = existing
    return kwargs


def _header_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    if el.share_type is not None:
        kwargs["share_type"] = el.share_type
    return kwargs


def _menu_update(el: "ElementUpdate") -> dict:
    kwargs: dict[str, Any] = {}
    if el.menu_orientation is not None:
        kwargs["orientation"] = el.menu_orientation
    if el.menu_alignment is not None:
        kwargs["alignment"] = el.menu_alignment
    if el.menu_items is not None:
        kwargs["menu_items"] = [
            {
                "uid": str(uuid.uuid4()),
                "type": "link",
                "variant": "link",
                "name": item.name,
                "navigation_type": "page",
                "navigate_to_page_id": item.page_id,
                "target": "self",
            }
            for item in el.menu_items
        ]
    return kwargs


_TO_ORM_UPDATE: dict[str, Any] = {
    "heading": _heading_update,
    "text": _text_update,
    "button": _button_update,
    "link": _link_update,
    "image": _image_update,
    "column": _column_update,
    "form_container": _form_container_update,
    "simple_container": lambda el: {},
    "input_text": _input_text_update,
    "choice": _choice_update,
    "checkbox": _checkbox_update,
    "datetime_picker": _datetime_picker_update,
    "record_selector": _input_text_update,
    "table": _table_update,
    "repeat": _repeat_update,
    "header": _header_update,
    "footer": _header_update,
    "menu": _menu_update,
}


def _update_value_formula(el: "ElementUpdate", orm_element, context) -> dict[str, str]:
    if el.value and needs_formula(el.value):
        return {"value": formula_desc(el.value)}
    return {}


def _update_link_formulas(el: "ElementUpdate", orm_element, context) -> dict[str, str]:
    formulas: dict[str, str] = {}
    if el.value and needs_formula(el.value):
        formulas["value"] = formula_desc(el.value)
    if el.navigate_to_url and needs_formula(el.navigate_to_url):
        formulas["navigate_to_url"] = formula_desc(el.navigate_to_url)
    return formulas


def _update_image_formulas(el: "ElementUpdate", orm_element, context) -> dict[str, str]:
    formulas: dict[str, str] = {}
    if el.image_url and needs_formula(el.image_url):
        formulas["image_url"] = formula_desc(el.image_url)
    if el.alt_text and needs_formula(el.alt_text):
        formulas["alt_text"] = formula_desc(el.alt_text)
    return formulas


def _update_default_value_formula(
    el: "ElementUpdate", orm_element, context
) -> dict[str, str]:
    if el.default_value and needs_formula(el.default_value):
        return {"default_value": formula_desc(el.default_value)}
    return {}


_GET_UPDATE_FORMULAS: dict[str, Any] = {
    "heading": _update_value_formula,
    "text": _update_value_formula,
    "button": _update_value_formula,
    "link": _update_link_formulas,
    "image": _update_image_formulas,
    "input_text": _update_default_value_formula,
    "choice": _update_default_value_formula,
    "checkbox": _update_default_value_formula,
    "datetime_picker": _update_default_value_formula,
}


class ElementUpdate(BaseModel):
    """
    Flat model for updating an existing builder UI element.

    All fields are optional. Only non-None fields are sent to the service layer.
    The element type is read from the database, not passed by the LLM.
    """

    element_id: int = Field(..., description="ID of the element to update.")

    # -- Common ---------------------------------------------------------------
    visibility: Literal["all", "logged-in", "not-logged"] | None = Field(
        default=None, description="Element visibility."
    )
    role_type: (
        Literal["allow_all", "allow_all_except", "disallow_all_except"] | None
    ) = Field(default=None, description="Role access strategy.")
    roles: list[str] | None = Field(
        default=None, description="Role names for the access strategy."
    )

    # -- Display fields -------------------------------------------------------
    value: str | None = Field(
        default=None,
        description="Display text (heading, text, button, link). Supports $formula: prefix.",
    )
    level: int | None = Field(default=None, description="(heading) Level 1-5.")
    format: str | None = Field(
        default=None, description="(text) 'plain' or 'markdown'."
    )

    # -- Link fields ----------------------------------------------------------
    link_variant: Literal["link", "button"] | None = Field(
        default=None, description="(link) Display variant."
    )
    navigation_type: Literal["page", "custom"] | None = Field(
        default=None, description="(link) Navigation type."
    )
    navigate_to_page_id: int | None = Field(
        default=None, description="(link) Target page ID."
    )
    navigate_to_url: str | None = Field(
        default=None,
        description="(link) Custom URL. Supports $formula: prefix.",
    )
    link_target: Literal["self", "blank"] | None = Field(
        default=None, description="(link) Navigation target."
    )

    # -- Image fields ---------------------------------------------------------
    image_source_type: Literal["upload", "url"] | None = Field(
        default=None, description="(image) Source type."
    )
    image_url: str | None = Field(
        default=None,
        description="(image) Image URL. Supports $formula: prefix.",
    )
    alt_text: str | None = Field(
        default=None,
        description="(image) Alt text. Supports $formula: prefix.",
    )

    # -- Column fields --------------------------------------------------------
    column_amount: int | None = Field(
        default=None, description="(column) Number of columns (1-6)."
    )
    column_gap: int | None = Field(
        default=None, description="(column) Gap between columns in px."
    )
    column_alignment: Literal["top", "center", "bottom"] | None = Field(
        default=None, description="(column) Vertical alignment."
    )

    # -- Form container fields ------------------------------------------------
    submit_button_label: str | None = Field(
        default=None, description="(form_container) Submit button label."
    )

    # -- Form input fields ----------------------------------------------------
    label: str | None = Field(default=None, description="(form inputs) Field label.")
    placeholder: str | None = Field(
        default=None, description="(form inputs) Placeholder text."
    )
    default_value: str | None = Field(
        default=None,
        description="(form inputs) Default value. Supports $formula: prefix.",
    )
    required: bool | None = Field(
        default=None, description="(form inputs) Required field."
    )
    validation_type: Literal["any", "email", "integer"] | None = Field(
        default=None, description="(input_text) Validation type."
    )
    is_multiline: bool | None = Field(
        default=None, description="(input_text) Multiline mode."
    )
    rows: int | None = Field(
        default=None, description="(input_text) Rows for multiline."
    )
    multiple: bool | None = Field(
        default=None, description="(choice, record_selector) Allow multiple."
    )
    show_as_dropdown: bool | None = Field(
        default=None, description="(choice) Show as dropdown."
    )
    include_time: bool | None = Field(
        default=None, description="(datetime_picker) Include time."
    )
    date_format: Literal["EU", "US", "ISO"] | None = Field(
        default=None, description="(datetime_picker) Date format."
    )

    # -- Collection fields ----------------------------------------------------
    items_per_page: int | None = Field(
        default=None, description="(table, repeat) Items per page."
    )
    button_load_more_label: str | None = Field(
        default=None, description="(table) Load more button label."
    )
    fields: list[TableFieldConfig] | None = Field(
        default=None,
        description="(table) Replace ALL columns — use only when you want to redefine the entire column list. Prefer add_fields/remove_fields for incremental changes.",
    )
    add_fields: list[TableFieldConfig] | None = Field(
        default=None,
        description="(table) Append columns to the existing table. Existing columns are preserved.",
    )
    remove_fields: list[str] | None = Field(
        default=None,
        description="(table) Remove columns by name (case-insensitive). Remaining columns are preserved.",
    )
    orientation: Literal["vertical", "horizontal"] | None = Field(
        default=None, description="(repeat) Orientation."
    )

    # -- Navigation fields ----------------------------------------------------
    share_type: Literal["all", "only", "except"] | None = Field(
        default=None, description="(header, footer) Page sharing."
    )
    menu_orientation: Literal["horizontal", "vertical"] | None = Field(
        default=None, description="(menu) Menu orientation."
    )
    menu_alignment: Literal["left", "center", "right", "justify"] | None = Field(
        default=None, description="(menu) Menu alignment."
    )
    menu_items: list[MenuItemCreate] | None = Field(
        default=None,
        description="(menu) Replace all menu items. Each item has name + page_id.",
    )

    # -- Dispatch -------------------------------------------------------------

    def to_update_kwargs(self, element_type: str) -> dict:
        """Return kwargs for ``ElementService.update_element()``."""

        fn = _TO_ORM_UPDATE.get(element_type)
        kwargs = fn(self) if fn else {}

        # Handle visibility (common to all types)
        if self.visibility is not None:
            kwargs["visibility"] = self.visibility
        if self.role_type is not None:
            kwargs["role_type"] = self.role_type
        if self.roles is not None:
            kwargs["roles"] = self.roles

        return kwargs

    def get_formulas_to_update(
        self,
        orm_element: "Element",
        context: "BuilderFormulaContext",
        element_type: str,
    ) -> dict[str, str]:
        """Return ``{field_path: description}`` for LLM formula generation."""

        fn = _GET_UPDATE_FORMULAS.get(element_type)
        return fn(self, orm_element, context) if fn else {}

    def get_updated_field_names(self) -> list[str]:
        """Return names of fields that were explicitly set (non-None)."""

        skip = {"element_id"}
        return [
            name
            for name, field_info in self.__class__.model_fields.items()
            if name not in skip and getattr(self, name) is not None
        ]


class ElementItem(BaseModel):
    """Existing element with ID."""

    id: int
    type: str
    order: str
    parent_element_id: int | None = None
    place_in_container: str | None = None
    is_container: bool = Field(
        default=False,
        description="True if this element can contain child elements.",
    )
    label: str | None = Field(
        default=None,
        description="Short content preview (text value, label, or name).",
    )
    page_name: str | None = Field(
        default=None,
        description="Page name. '[shared]' for elements on the shared page (headers/footers).",
    )
    menu_items: list[dict] | None = Field(
        default=None,
        description="(menu) Current menu items with name and page_id.",
    )

    @classmethod
    def from_orm(cls, element) -> "ElementItem":
        """Create ElementItem from ORM Element instance."""
        element_type = element.get_type().type
        page = element.page
        page_name = "[shared]" if page.shared else page.name
        menu_items = None
        if element_type == "menu":
            specific = element.specific
            menu_items = [
                {
                    "name": item.name,
                    "page_id": item.navigate_to_page_id,
                    "type": item.type,
                }
                for item in specific.menu_items.all().order_by("menu_item_order")
            ]
        return cls(
            id=element.id,
            type=element_type,
            order=str(element.order),
            parent_element_id=element.parent_element_id,
            place_in_container=element.place_in_container,
            is_container=element_type in CONTAINER_ELEMENT_TYPES,
            label=cls._extract_label(element),
            page_name=page_name,
            menu_items=menu_items,
        )

    @staticmethod
    def _extract_label(element) -> str | None:
        """Extract a short content preview from the element's ORM fields.

        FormulaField values are ``BaserowFormulaObject`` dicts with a
        ``formula`` key; plain strings are also possible for legacy data.
        """

        # Display elements (heading, text, button, link) use ``value``
        # Form inputs (input_text, choice, checkbox) use ``label``
        raw = getattr(element, "value", None) or getattr(element, "label", None)
        if not raw:
            return None
        # FormulaField returns a dict like {"formula": "...", "mode": ..., "version": ...}
        if isinstance(raw, dict):
            raw = raw.get("formula", "") or raw.get("f", "")
        if not isinstance(raw, str) or not raw.strip():
            return None
        preview = raw.strip()
        if len(preview) > 80:
            preview = preview[:77] + "..."
        return preview


# ---------------------------------------------------------------------------
# Element move model
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Style override block types
# ---------------------------------------------------------------------------


class ButtonStyleOverride(BaseModel):
    """Per-element button style overrides."""

    model_config = {"extra": "forbid"}

    background_color: str | None = Field(default=None, description="Button bg color.")
    text_color: str | None = Field(default=None, description="Button text color.")
    border_color: str | None = Field(default=None, description="Button border color.")
    border_size: int | None = Field(default=None)
    border_radius: int | None = Field(default=None)
    hover_background_color: str | None = Field(default=None)
    hover_text_color: str | None = Field(default=None)
    font_size: int | None = Field(default=None)
    width: Literal["auto", "full"] | None = Field(default=None)
    alignment: Literal["left", "center", "right"] | None = Field(default=None)

    def to_styles_dict(self) -> dict:
        return {f"button_{k}": v for k, v in self.model_dump(exclude_none=True).items()}


class LinkStyleOverride(BaseModel):
    """Per-element link style overrides."""

    model_config = {"extra": "forbid"}

    text_color: str | None = Field(default=None)
    hover_text_color: str | None = Field(default=None)
    font_size: int | None = Field(default=None)
    font_weight: str | None = Field(default=None)

    def to_styles_dict(self) -> dict:
        return {f"link_{k}": v for k, v in self.model_dump(exclude_none=True).items()}


class TypographyStyleOverride(BaseModel):
    """Per-element typography overrides (heading/text elements)."""

    model_config = {"extra": "forbid"}

    heading_1_text_color: str | None = Field(default=None)
    heading_1_font_size: int | None = Field(default=None)
    heading_1_font_weight: str | None = Field(default=None)
    heading_1_text_alignment: Literal["left", "center", "right"] | None = Field(
        default=None
    )
    body_text_color: str | None = Field(default=None)
    body_font_size: int | None = Field(default=None)
    body_font_weight: str | None = Field(default=None)
    body_text_alignment: Literal["left", "center", "right"] | None = Field(default=None)

    def to_styles_dict(self) -> dict:
        return self.model_dump(exclude_none=True)


class InputStyleOverride(BaseModel):
    """Per-element input style overrides."""

    model_config = {"extra": "forbid"}

    input_background_color: str | None = Field(default=None)
    input_border_color: str | None = Field(default=None)
    input_text_color: str | None = Field(default=None)
    input_border_size: int | None = Field(default=None)
    input_border_radius: int | None = Field(default=None)
    label_text_color: str | None = Field(default=None)

    def to_styles_dict(self) -> dict:
        return self.model_dump(exclude_none=True)


class TableStyleOverride(BaseModel):
    """Per-element table style overrides."""

    model_config = {"extra": "forbid"}

    table_header_background_color: str | None = Field(default=None)
    table_header_text_color: str | None = Field(default=None)
    table_cell_background_color: str | None = Field(default=None)
    table_border_color: str | None = Field(default=None)
    table_border_size: int | None = Field(default=None)

    def to_styles_dict(self) -> dict:
        return self.model_dump(exclude_none=True)


class ImageStyleOverride(BaseModel):
    """Per-element image style overrides."""

    model_config = {"extra": "forbid"}

    image_alignment: Literal["left", "center", "right"] | None = Field(default=None)
    image_max_width: int | None = Field(default=None)
    image_max_height: int | None = Field(default=None)
    image_border_radius: int | None = Field(default=None)

    def to_styles_dict(self) -> dict:
        return self.model_dump(exclude_none=True)


# ---------------------------------------------------------------------------
# Style update model
# ---------------------------------------------------------------------------

_STYLE_DEFAULTS: dict[str, Any] = {
    "style_border_top_color": "border",
    "style_border_top_size": 0,
    "style_border_bottom_color": "border",
    "style_border_bottom_size": 0,
    "style_border_left_color": "border",
    "style_border_left_size": 0,
    "style_border_right_color": "border",
    "style_border_right_size": 0,
    "style_padding_top": 10,
    "style_padding_bottom": 10,
    "style_padding_left": 20,
    "style_padding_right": 20,
    "style_margin_top": 0,
    "style_margin_bottom": 0,
    "style_margin_left": 0,
    "style_margin_right": 0,
    "style_border_radius": 0,
    "style_background_radius": 0,
    "style_background": "none",
    "style_background_color": "#ffffffff",
    "style_background_mode": "fill",
    "style_width": "normal",
}

# Maps (element_type, tool_block_name) → styles JSON key.
# The styles JSON key is the serializer's `property_name`, which varies per
# element type.  E.g. for "menu", both button and link props go under "menu".
_BLOCK_TO_STYLES_KEY: dict[str, dict[str, str]] = {
    "heading": {"typography": "typography"},
    "text": {"typography": "typography"},
    "button": {"button": "button"},
    "link": {"button": "button", "link": "link"},
    "image": {"image": "image"},
    "input_text": {"input": "input"},
    "choice": {"input": "input"},
    "checkbox": {"input": "input"},
    "table": {"button": "button", "table": "table"},
    "repeat": {"button": "button"},
    "menu": {"button": "menu", "link": "menu"},
    "form_container": {"button": "button"},
}


class ElementStyleUpdate(BaseModel):
    """
    Compact model for updating element visual styles.

    All fields optional — only non-None fields are applied.
    Set reset=true to restore all styles to defaults first.
    """

    element_id: int = Field(..., description="ID of the element to style.")
    reset: bool = Field(
        default=False, description="Reset all styles to defaults first."
    )

    # -- Box model: single value for all sides, or dict for per-side --
    border_color: str | dict[str, str] | None = Field(
        default=None,
        description='Border color: value for all sides, or {"left": "#ff0000", ...} for specific sides.',
    )
    border_size: int | dict[str, int] | None = Field(
        default=None,
        description='Border size in px: value for all sides, or {"top": 2, ...} for specific sides.',
    )
    padding: int | dict[str, int] | None = Field(
        default=None,
        description='Padding in px: value for all sides, or {"left": 0, ...} for specific sides.',
    )
    margin: int | dict[str, int] | None = Field(
        default=None,
        description='Margin in px: value for all sides, or {"top": 10, ...} for specific sides.',
    )

    @model_validator(mode="after")
    def _validate_box_sides(self) -> "ElementStyleUpdate":
        valid_sides = {"top", "bottom", "left", "right"}
        for field_name in ("padding", "margin", "border_size", "border_color"):
            val = getattr(self, field_name)
            if isinstance(val, dict):
                invalid = set(val.keys()) - valid_sides
                if invalid:
                    raise ValueError(f"{field_name}: invalid sides {invalid}")
        return self

    # -- Radii --
    border_radius: int | None = Field(default=None)
    background_radius: int | None = Field(default=None)

    # -- Background --
    background: Literal["none", "color"] | None = Field(default=None)
    background_color: str | None = Field(
        default=None, description="Background color (hex)."
    )

    # -- Width --
    width: Literal["full", "full-width", "normal", "medium", "small"] | None = Field(
        default=None
    )

    # -- Theme style overrides (per element type) --
    button: ButtonStyleOverride | None = Field(
        default=None, description="Button style overrides."
    )
    link: LinkStyleOverride | None = Field(
        default=None, description="Link style overrides."
    )
    typography: TypographyStyleOverride | None = Field(
        default=None, description="Typography overrides."
    )
    input: InputStyleOverride | None = Field(
        default=None, description="Input style overrides."
    )
    table: TableStyleOverride | None = Field(
        default=None, description="Table style overrides."
    )
    image: ImageStyleOverride | None = Field(
        default=None, description="Image style overrides."
    )

    def _apply_box(self, kwargs: dict, field_name: str, orm_template: str):
        val = getattr(self, field_name)
        if val is None:
            return
        if isinstance(val, dict):
            for side, side_val in val.items():
                kwargs[orm_template.format(side=side)] = side_val
        else:
            for side in ("top", "bottom", "left", "right"):
                kwargs[orm_template.format(side=side)] = val

    def to_update_kwargs(
        self, element_type: str, existing_styles: dict | None = None
    ) -> dict:
        """Convert to ORM kwargs for ElementService.update_element().

        :param element_type: The element's type string (e.g. "button").
        :param existing_styles: The element's current ``styles`` JSON dict.
            Used to merge theme overrides without wiping unrelated keys.
        """

        kwargs: dict[str, Any] = {}

        if self.reset:
            kwargs.update(_STYLE_DEFAULTS)
            kwargs["styles"] = {}

        # Box model — uniform or per-side
        self._apply_box(kwargs, "border_color", "style_border_{side}_color")
        self._apply_box(kwargs, "border_size", "style_border_{side}_size")
        self._apply_box(kwargs, "padding", "style_padding_{side}")
        self._apply_box(kwargs, "margin", "style_margin_{side}")

        # Simple style fields
        if self.border_radius is not None:
            kwargs["style_border_radius"] = self.border_radius
        if self.background_radius is not None:
            kwargs["style_background_radius"] = self.background_radius
        if self.background is not None:
            kwargs["style_background"] = self.background
        if self.background_color is not None:
            kwargs["style_background_color"] = self.background_color
        if self.width is not None:
            kwargs["style_width"] = self.width

        # Theme style overrides — merge into existing styles JSON.
        # Start from existing styles (or {} after reset) so we don't wipe
        # keys that weren't touched in this call.
        block_key_map = _BLOCK_TO_STYLES_KEY.get(element_type, {})
        if self.reset:
            styles: dict = {}
        else:
            styles = dict(existing_styles) if existing_styles else {}
            # Deep-copy block dicts so we don't mutate the original
            for k, v in styles.items():
                if isinstance(v, dict):
                    styles[k] = dict(v)
        styles_changed = False
        for block_name in ("button", "link", "typography", "input", "table", "image"):
            override = getattr(self, block_name)
            target_key = block_key_map.get(block_name)
            if override is not None and target_key is not None:
                block_dict = override.to_styles_dict()
                if block_dict:
                    styles[target_key] = {
                        **styles.get(target_key, {}),
                        **block_dict,
                    }
                    styles_changed = True
        if styles_changed or "styles" in kwargs:
            kwargs["styles"] = styles

        return kwargs


class ElementMove(BaseModel):
    """Describes a single element move operation."""

    element_id: int = Field(description="ID of the element to move.")
    before_id: int | None = Field(
        default=None,
        description="Place before this element ID. None = move to end.",
    )
    parent_element_id: int | None = Field(
        default=None,
        description="New parent element ID. None = move to root level.",
    )
    place_in_container: str | None = Field(
        default=None,
        description='Container slot (e.g. "0", "1" for columns). None = default.',
    )
