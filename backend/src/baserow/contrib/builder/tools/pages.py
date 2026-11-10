"""
Application builder page tools shared by the clients that act for a user.
"""

from dataclasses import replace
from typing import Annotated, Any

from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field

from baserow.core.exceptions import PermissionException
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import (
    PERMISSION_DENIED_MESSAGE,
    ToolInputError,
    raise_if_permission_denied,
)
from baserow.core.user_sources.service import UserSourceService

from . import BuilderWriteOptions, helpers
from .actions import create_actions_with_options
from .data_sources import create_data_sources_with_options
from .elements import create_elements_with_options
from .errors import client_item_error
from .lookups import get_builder_in_workspace, get_page_in_workspace
from .types import (
    ActionCreate,
    DataSourceCreate,
    ElementItemCreate,
    PageChanges,
    PageCreate,
    PageItem,
    PageUpdate,
)
from .types.limits import MAX_ITEMS_PER_CALL


def list_pages(
    ctx: ToolContext,
    builder_id: Annotated[
        int, Field(description="The ID of the application builder, from list_builders.")
    ],
) -> dict[str, Any]:
    """
    List the pages of an application builder: id, name, path, path and query
    parameters and visibility. Also returns the login page ID, the user sources
    people log in with, and the roles they can have. The shared page that holds
    headers and footers is not a page of its own and is not listed. Use
    list_elements to see them. shared_page_id is its ID, to give a header or footer a
    data source with create_data_sources.
    """

    builder = get_builder_in_workspace(ctx, builder_id)
    ctx.update_status(
        _("Listing pages in %(app_name)s...") % {"app_name": builder.name}
    )

    pages = helpers.list_pages(ctx.user, builder)

    try:
        user_sources = UserSourceService().get_user_sources(ctx.user, builder)
    except PermissionException:
        # Only application editors may list them.
        user_sources = []
    user_source_data = []
    roles: set[str] = set()
    for user_source in user_sources:
        roles.update(user_source.get_type().get_roles(user_source))
        entry = {"id": user_source.id, "name": user_source.name}
        specific = (
            user_source.specific if hasattr(user_source, "specific") else user_source
        )
        if hasattr(specific, "table_id"):
            entry["table_id"] = specific.table_id
        user_source_data.append(entry)

    return {
        "application_id": builder.id,
        "pages": [p.model_dump() for p in pages],
        "login_page_id": builder.login_page_id,
        "shared_page_id": builder.shared_page.id,
        "user_sources": user_source_data,
        "available_roles": sorted(roles),
    }


def create_pages_with_options(
    ctx: ToolContext,
    builder_id: int,
    pages: list[PageCreate],
    options: BuilderWriteOptions,
) -> dict[str, Any]:
    """``create_pages`` with what a client adds to it."""

    builder = get_builder_in_workspace(ctx, builder_id)
    created: list[dict] = []
    errors: list[str] = []
    with transaction.atomic():
        for page_create in pages:
            ctx.update_status(
                _("Creating page %(name)s...") % {"name": page_create.name}
            )
            try:
                with transaction.atomic():
                    page = helpers.create_page(ctx.user, builder, page_create)
            except Exception as exc:
                raise_if_permission_denied(exc)
                errors.append(f"{page_create.name}: {options.item_error(exc)}")
                continue
            created.append(PageItem.from_orm(page).model_dump())

    result: dict[str, Any] = {"created_pages": created}
    if errors:
        result["errors"] = errors
    return result


def create_pages(
    ctx: ToolContext,
    builder_id: Annotated[
        int, Field(description="The ID of the application builder, from list_builders.")
    ],
    pages: Annotated[
        list[PageCreate],
        Field(max_length=MAX_ITEMS_PER_CALL, description="The pages to create."),
    ],
) -> dict[str, Any]:
    """
    Create pages in an application builder. A parameter in a path, like :id in
    /products/:id, is added as text unless path_params says otherwise. A page whose
    path is already used is listed in errors and the others are created.
    """

    return create_pages_with_options(ctx, builder_id, pages, BuilderWriteOptions())


def update_page(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
    page: Annotated[
        PageChanges, Field(description="The changes. Set only what should change.")
    ],
) -> dict[str, Any]:
    """
    Update a page: its name, path, parameters or who can see it. A new path keeps the
    type of the parameters it still names, and adds new ones as text. When the
    parameters change, navigations_to_fix lists the links, menu items and click
    actions that go to the page with the old ones, and how to fix each: until then
    they show as errors, and publishing hides them.
    """

    before = get_page_in_workspace(ctx, page_id)
    old_names = [param["name"] for param in before.path_params or []]
    ctx.update_status(_("Updating page %(id)d...") % {"id": page_id})

    updated = helpers.update_page(
        ctx.user,
        ctx.workspace,
        PageUpdate(page_id=page_id, **page.model_dump(exclude={"page_id"})),
    )
    result: dict[str, Any] = {"updated_page": PageItem.from_orm(updated).model_dump()}
    if [param["name"] for param in updated.path_params or []] != old_names:
        to_fix = helpers.navigations_out_of_step(updated)
        if to_fix:
            result["navigations_to_fix"] = to_fix
    return result


def setup_page_with_options(
    ctx: ToolContext,
    page_id: int,
    data_sources: list[DataSourceCreate] | None,
    elements: list[ElementItemCreate] | None,
    actions: list[ActionCreate] | None,
    options: BuilderWriteOptions,
) -> dict[str, Any]:
    """
    ``setup_page`` with what a client adds to it. Data sources, then elements, then
    actions, each saved before the next starts.

    :return: As ``setup_page``. When the user was refused a write the phases after it
        don't run, and ``permission_denied`` holds the refusal.
    """

    data_source_refs = dict(options.known_data_source_refs)
    element_refs = dict(options.known_refs)
    result: dict[str, Any] = {
        "created_data_sources": [],
        "created_elements": [],
        "created_actions": [],
    }
    formula_errors: list = []
    errors: list[str] = []

    def finish_phase(kind: str, phase: dict[str, Any], error_prefix: str) -> None:
        errors.extend(f"{error_prefix}{error}" for error in phase.get("errors", []))
        formula_errors.extend(options.after_phase(kind, phase))

    try:
        if data_sources:
            phase = create_data_sources_with_options(
                ctx, page_id, data_sources, options
            )
            result["created_data_sources"] = phase["created_data_sources"]
            data_source_refs.update(phase["ref_to_id_map"])
            finish_phase("data_source", phase, "data_source ")
        if elements:
            phase = create_elements_with_options(
                ctx,
                page_id,
                elements,
                None,
                replace(
                    options,
                    known_refs=element_refs,
                    known_data_source_refs=data_source_refs,
                ),
            )
            result["created_elements"] = phase["created_elements"]
            element_refs.update(phase["ref_to_id_map"])
            finish_phase("element", phase, "element ")
        if actions:
            phase = create_actions_with_options(
                ctx,
                page_id,
                actions,
                replace(
                    options,
                    known_refs=element_refs,
                    known_data_source_refs=data_source_refs,
                ),
            )
            result["created_actions"].extend(phase["created_actions"])
            finish_phase("action", phase, "action ")
    except PermissionException as exc:
        result["permission_denied"] = exc

    if formula_errors:
        result["formula_errors"] = formula_errors
    if errors:
        result["errors"] = errors
    return result


def setup_page(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
    data_sources: Annotated[
        list[DataSourceCreate] | None,
        Field(max_length=MAX_ITEMS_PER_CALL, description="The data sources to create."),
    ] = None,
    elements: Annotated[
        list[ElementItemCreate] | None,
        Field(
            max_length=MAX_ITEMS_PER_CALL,
            description="The elements to create, parents before children.",
        ),
    ] = None,
    actions: Annotated[
        list[ActionCreate] | None,
        Field(
            max_length=MAX_ITEMS_PER_CALL, description="The workflow actions to create."
        ),
    ] = None,
) -> dict[str, Any]:
    """
    Add content to an existing page in one call: data sources, then elements, then
    workflow actions. Each of the three is saved before the next starts and each item
    on its own, so an item that fails is listed in errors, as "element <ref>:
    <message>", and the others are kept. Give at least one of the three. A call made
    twice creates everything twice, so after errors resend only the failed items.

    Refs link items inside this call: an element's data_source and parent_element, an
    action's element and data_source. Elements of every type can be created here,
    including auth_form, with a user_source_id from setup_user_source. A header or
    footer, and anything inside one, goes on the shared page and shows on every page.

    Give dynamic values as formulas in Baserow formula syntax. A formula needs real
    IDs, like get('form_data.<element id>'), which a ref can't give: to read an input
    or data source made in this call, add the action or element in a second call with
    the IDs from this one. Plain text in a title, description, parameter or action
    field value is stored as fixed text. A whole value that is a function call, like
    upper('abc'), is a formula, and so is a number or true or false as a field value.
    Sums like 3/4 are fixed text. Descriptions are not turned into formulas: a
    value that isn't a valid formula is left empty and listed in formula_errors. A
    get_row or row action can't run without its row_id, so one that isn't a valid
    formula is listed in errors and isn't created. So is an open_page action whose
    page_parameters don't have exactly the names of the path parameters of the page it
    opens.

    If you may not do something, what was saved before it is returned with the refusal
    in errors, and the rest isn't attempted.
    """

    if not data_sources and not elements and not actions:
        raise ToolInputError(
            "There is nothing to do: give data_sources, elements or actions."
        )
    result = setup_page_with_options(
        ctx,
        page_id,
        data_sources,
        elements,
        actions,
        BuilderWriteOptions(item_error=client_item_error),
    )
    denied = result.pop("permission_denied", None)
    if denied:
        if not any(
            result[key]
            for key in ("created_data_sources", "created_elements", "created_actions")
        ):
            raise denied
        result.setdefault("errors", []).append(PERMISSION_DENIED_MESSAGE)
    return result
