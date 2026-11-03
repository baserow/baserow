"""
Application builder element tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field, ValidationError

from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.pages.models import Page
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import (
    ToolInputError,
    format_validation_error,
    raise_if_permission_denied,
)

from . import BuilderWriteOptions, helpers
from .errors import client_item_error
from .formulas import BuilderFormulaError, apply_builder_formulas
from .pages import get_page_in_workspace
from .types import (
    CollectionElementCreate,
    DisplayElementCreate,
    ElementChanges,
    ElementItem,
    ElementItemCreate,
    ElementMove,
    ElementStyleChanges,
    ElementStyleUpdate,
    ElementUpdate,
    FormElementCreate,
    LayoutElementCreate,
)


def list_elements(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
) -> dict[str, Any]:
    """
    List the elements of a page of an application builder: id, type, parent
    element and whether it is a container. Elements of the shared page are
    included. Tables also show their data source and their columns in display
    order: uid, name, type, and value (text, boolean, rating) or label (button).
    A value or label is a formula: fixed text is quoted, and '' or "''" is an
    empty cell. Menus show their items in order: uid, name, type, page_id (or
    url, for a link to a custom address), and the sub-links of a top-level link
    as children.

    Elements with page_name "[shared]" are headers and footers shown on every
    page. They belong to the shared page, not to this one.
    """

    page = get_page_in_workspace(ctx, page_id)
    ctx.update_status(_("Listing elements on %(name)s...") % {"name": page.name})

    elements = helpers.list_elements(ctx.user, page)
    return {"elements": [el.model_dump() for el in elements]}


def _element_in_workspace(ctx: ToolContext, element_id: int) -> Element:
    """
    Get an element of the context's workspace.

    :raises ElementDoesNotExist: When the element is missing, or its application is
        trashed or in another workspace.
    """

    return ElementHandler().get_element(
        element_id,
        base_queryset=Element.objects.filter(
            page__builder__workspace=ctx.workspace, page__builder__trashed=False
        ),
    )


def _is_empty_container(element: Element) -> bool:
    return (
        element.get_type().is_container
        and not element.page.get_graph().get_children(element)
    )


def create_elements_with_options(
    ctx: ToolContext,
    page_id: int,
    elements: list[ElementItemCreate],
    before_element_id: int | None,
    options: BuilderWriteOptions,
) -> dict[str, Any]:
    """``create_elements`` with what a client adds to it."""

    page = get_page_in_workspace(ctx, page_id)
    status = _("Creating %(count)d elements on %(name)s...") % {
        "count": len(elements),
        "name": page.name,
    }

    refs = dict(options.known_refs)
    data_source_refs = dict(options.known_data_source_refs)
    new_refs: dict[str, int] = {}
    created: list[dict] = []
    pairs: list[tuple[Any, ElementItemCreate]] = []
    action_pairs: list[tuple[Any, Any]] = []
    errors: list[str] = []
    with transaction.atomic():
        for el_create in elements:
            ctx.update_status(status)
            el_create._column_name_beats_formula = options.column_name_beats_formula
            try:
                with transaction.atomic():
                    element, el_id, new_action_pairs = helpers.create_element(
                        ctx.user,
                        page,
                        el_create,
                        refs,
                        data_source_refs,
                        options.known_shared_page_refs,
                        before_element_id,
                    )
            except Exception as exc:
                raise_if_permission_denied(exc)
                helpers.forget_page_graphs(page)
                errors.append(f"{el_create.ref}: {options.item_error(exc)}")
                continue
            refs[el_create.ref] = el_id
            new_refs[el_create.ref] = el_id
            pairs.append((element, el_create))
            action_pairs.extend(new_action_pairs)
            created.append({"id": el_id, "ref": el_create.ref, "type": el_create.type})

    formula_errors: list[BuilderFormulaError] = [
        *apply_builder_formulas(ctx, page, pairs, "element"),
        *apply_builder_formulas(ctx, page, action_pairs, "action"),
    ]

    result: dict[str, Any] = {"created_elements": created, "ref_to_id_map": new_refs}
    if action_pairs:
        result["created_actions"] = [
            {"id": action.id, "element_id": action.element_id, "event": action.event}
            for action, _action_create in action_pairs
        ]

    # Read from the saved graph after the whole batch, so a container whose content
    # came later in the batch isn't listed.
    created_by_id = {element.id: element for element, _el_create in pairs}
    empty_containers = [
        item for item in created if _is_empty_container(created_by_id[item["id"]])
    ]
    if empty_containers:
        result["empty_containers"] = empty_containers
    if formula_errors:
        result["formula_errors"] = formula_errors
    if errors:
        result["errors"] = errors
    return result


def create_elements(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
    elements: Annotated[
        list[ElementItemCreate], Field(description="The elements to create.")
    ],
    before_element_id: Annotated[
        int | None,
        Field(description="Insert before this element, from list_elements."),
    ] = None,
) -> dict[str, Any]:
    """
    Create elements of any type on a page. ref_to_id_map gives the ID of each ref. A
    ref only works inside the call that creates it; afterwards use the element's ID.
    A header or footer, and anything inside one, goes on the shared page and shows
    on every page. empty_containers lists the new containers with nothing in them.
    Give dynamic values as formulas in Baserow formula syntax, like
    get('page_parameter.id'). Descriptions are not turned into formulas: a value
    that isn't a valid formula is left empty and listed in formula_errors, so it can
    be set with update_element.
    """

    return create_elements_with_options(
        ctx,
        page_id,
        elements,
        before_element_id,
        BuilderWriteOptions(item_error=client_item_error),
    )


def create_display_elements(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
    elements: Annotated[
        list[DisplayElementCreate], Field(description="The elements to create.")
    ],
    before_element_id: Annotated[
        int | None,
        Field(description="Insert before this element, from list_elements."),
    ] = None,
) -> dict[str, Any]:
    """
    Create display elements on a page: heading, text, button, link and image.
    ref_to_id_map gives the ID of each ref. A ref works as parent_element inside the
    call that creates it; afterwards use the element's ID. Plain text is stored as
    fixed text.

    Give dynamic values as formulas in Baserow formula syntax, like
    get('page_parameter.id'). Inside a repeat or a table,
    get('current_record.field_<id>') reads the row. Descriptions are not turned into
    formulas: a value that isn't a valid formula is left empty and listed in
    formula_errors, so it can be set with update_element.

    A button does nothing until it has a click action. A link has its target on the
    element.
    """

    return create_elements(
        ctx,
        page_id,
        [element.to_element_item_create() for element in elements],
        before_element_id,
    )


def create_layout_elements(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
    elements: Annotated[
        list[LayoutElementCreate], Field(description="The elements to create.")
    ],
    before_element_id: Annotated[
        int | None,
        Field(description="Insert before this element, from list_elements."),
    ] = None,
) -> dict[str, Any]:
    """
    Create layout elements on a page: column, simple_container, header, footer and
    menu. Other elements go inside them with parent_element; in a column,
    place_in_container says which one, from "0". ref_to_id_map gives the ID of each
    ref. A ref works as parent_element inside the call that creates it; afterwards
    use the element's ID. empty_containers lists the new containers with nothing in
    them.

    A header or footer, and anything inside one, goes on the shared page and shows on
    every page, or on the pages in page_ids with share_type "only". Pass any page of
    the application as page_id. Elements on the shared page can't read what only one
    page has, like its parameters or data sources.
    """

    return create_elements(
        ctx,
        page_id,
        [element.to_element_item_create() for element in elements],
        before_element_id,
    )


def create_form_elements(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
    elements: Annotated[
        list[FormElementCreate], Field(description="The elements to create.")
    ],
    before_element_id: Annotated[
        int | None,
        Field(description="Insert before this element, from list_elements."),
    ] = None,
) -> dict[str, Any]:
    """
    Create form elements on a page: form_container, input_text, choice, checkbox,
    datetime_picker and record_selector. Inputs go inside a form_container with
    parent_element. ref_to_id_map gives the ID of each ref. A ref works as
    parent_element inside the call that creates it; afterwards use the element's ID.
    A form_container needs a submit action to do anything.

    Give a dynamic default_value as a formula in Baserow formula syntax, like
    get('page_parameter.id'). Descriptions are not turned into formulas: a value
    that isn't a valid formula is left empty and listed in formula_errors, so it can
    be set with update_element. Labels and placeholders are fixed text.
    """

    return create_elements(
        ctx,
        page_id,
        [element.to_element_item_create() for element in elements],
        before_element_id,
    )


def create_collection_elements(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
    elements: Annotated[
        list[CollectionElementCreate], Field(description="The elements to create.")
    ],
    before_element_id: Annotated[
        int | None,
        Field(description="Insert before this element, from list_elements."),
    ] = None,
) -> dict[str, Any]:
    """
    Create collection elements on a page: table and repeat, which show the rows of a
    data source. data_source is a data source ID from list_data_sources. Elements go
    inside a repeat with parent_element. ref_to_id_map gives the ID of each ref. A
    ref works inside the call that creates it; afterwards use the element's ID.

    A table text column shows its value, or without one the field of the data source
    named like the column. Give a dynamic value or a button label as a formula, like
    get('current_record.field_<id>'). Descriptions are not turned into formulas: a
    value that isn't a valid formula is left empty and listed in formula_errors, with
    the column's position in field, like fields.0.value, so it can be set with
    update_element and update_table_columns.
    """

    return create_elements(
        ctx,
        page_id,
        [element.to_element_item_create() for element in elements],
        before_element_id,
    )


def _full_update(model: type, element_id: int, changes: Any) -> Any:
    """Build an update model, whose checks the changes model doesn't run."""

    try:
        return model(
            element_id=element_id, **changes.model_dump(exclude={"element_id"})
        )
    except ValidationError as exc:
        raise ToolInputError(format_validation_error(exc)) from exc


def update_element_on_page(
    ctx: ToolContext, page: Page, element: ElementUpdate
) -> tuple[helpers.ElementUpdateOutcome, list[BuilderFormulaError]]:
    """
    Update an element of a page or of its builder's shared page.

    :return: What the update did, and the ``formula_errors``.
    """

    outcome = helpers.update_element(ctx.user, page, element)
    formula_errors = apply_builder_formulas(
        ctx, page, [(outcome.element, element)], "element"
    )
    return outcome, formula_errors


def update_element(
    ctx: ToolContext,
    element_id: Annotated[
        int, Field(description="The ID of the element, from list_elements.")
    ],
    element: Annotated[
        ElementChanges, Field(description="The changes. Set only what should change.")
    ],
) -> dict[str, Any]:
    """
    Update an element: its text, settings, table columns or menu items. Properties the
    element's type doesn't have refuse the whole update. A button has no target of its
    own: give it a click action. To move an element or change its style use
    move_elements or update_element_style.

    Give dynamic values as formulas in Baserow formula syntax, like
    get('page_parameter.id'). A value that isn't a valid formula keeps its previous
    value and is listed in formula_errors.

    Table columns: list_elements shows each column's uid. Change them with
    add_table_columns, update_table_columns, reorder_table_columns and
    remove_table_columns; columns you don't list stay as they are. Only text and
    button columns can be created. Undo doesn't revert column changes, and a removed
    column and its click actions are gone for good. A column's formula must parse; what
    it reads isn't checked, so it isn't listed in formula_errors.

    Menu items: list_elements shows each item's uid. Change them with add_menu_items,
    update_menu_items, reorder_menu_items and remove_menu_items; items you don't list
    stay as they are. On a header or footer they change the menu inside it. Undo
    doesn't restore removed items, and a removed button's click actions are gone for
    good.
    """

    page = get_page_in_workspace(ctx, _element_in_workspace(ctx, element_id).page_id)
    ctx.update_status(_("Updating element %(id)d...") % {"id": element_id})

    outcome, formula_errors = update_element_on_page(
        ctx, page, _full_update(ElementUpdate, element_id, element)
    )

    updated = ElementHandler().get_element(element_id)
    result: dict[str, Any] = {
        "updated_element": ElementItem.from_orm(updated).model_dump(),
        **outcome.result,
    }
    if formula_errors:
        result["formula_errors"] = formula_errors
    return result


def update_element_style(
    ctx: ToolContext,
    element_id: Annotated[
        int, Field(description="The ID of the element, from list_elements.")
    ],
    style: Annotated[
        ElementStyleChanges,
        Field(description="The changes. Set only what should change."),
    ],
) -> dict[str, Any]:
    """
    Update how an element looks: borders, padding, margin, background, width, and the
    theme settings of its type, like a button's colors. Theme settings its type
    doesn't have are ignored; updated_fields lists what was applied. Set reset to go
    back to the defaults first.
    """

    page = get_page_in_workspace(ctx, _element_in_workspace(ctx, element_id).page_id)
    ctx.update_status(_("Styling element %(id)d...") % {"id": element_id})

    full_style = _full_update(ElementStyleUpdate, element_id, style)
    with transaction.atomic():
        _element, element_type = helpers.update_element_style(
            ctx.user, page, full_style
        )

    updated = ElementHandler().get_element(element_id)
    return {
        "updated_element": ElementItem.from_orm(updated).model_dump(),
        "updated_fields": list(full_style.to_update_kwargs(element_type, {})),
    }


def move_elements(
    ctx: ToolContext,
    moves: Annotated[list[ElementMove], Field(description="The moves to make.")],
) -> dict[str, Any]:
    """
    Move elements within their page: before another element, into a container, or to
    the end. An element can't move to another page, and elements on the shared page
    stay on it. A move that fails is listed in errors, as "<element id>: <message>",
    and the others are kept.
    """

    moved: list[dict] = []
    errors: list[str] = []
    with transaction.atomic():
        for element_move in moves:
            ctx.update_status(
                _("Moving element %(id)d...") % {"id": element_move.element_id}
            )
            page = None
            try:
                with transaction.atomic():
                    page = get_page_in_workspace(
                        ctx, _element_in_workspace(ctx, element_move.element_id).page_id
                    )
                    element = helpers.move_element(ctx.user, page, element_move)
            except Exception as exc:
                raise_if_permission_denied(exc)
                errors.append(f"{element_move.element_id}: {client_item_error(exc)}")
            else:
                moved.append(
                    {
                        "element_id": element.id,
                        "parent_element_id": element.parent_element_id,
                        "place_in_container": element.place_in_container,
                    }
                )
            finally:
                if page is not None:
                    helpers.forget_page_graphs(page)

    result: dict[str, Any] = {"moved_elements": moved}
    if errors:
        result["errors"] = errors
    return result
