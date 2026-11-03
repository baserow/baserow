"""
Application builder page tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field

from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.operations import ReadPageOperationType
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import raise_if_permission_denied
from baserow.core.user_sources.service import UserSourceService

from . import BuilderWriteOptions, helpers
from .applications import get_builder_in_workspace
from .types import PageChanges, PageCreate, PageItem, PageUpdate


def get_page_in_workspace(ctx: ToolContext, page_id: int) -> Page:
    """
    Get a page of the context's workspace the user can read.

    :raises PageDoesNotExist: When the page is missing, or its application is
        trashed or in another workspace.
    :raises PermissionException: When the user can't read the page.
    """

    page = PageHandler().get_page(
        page_id, base_queryset=helpers.workspace_pages(ctx.workspace)
    )
    CoreHandler().check_permissions(
        ctx.user, ReadPageOperationType.type, workspace=ctx.workspace, context=page
    )
    return page


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
    list_elements to see them.
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
    pages: Annotated[list[PageCreate], Field(description="The pages to create.")],
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
    type of the parameters it still names, and adds new ones as text.
    """

    get_page_in_workspace(ctx, page_id)
    ctx.update_status(_("Updating page %(id)d...") % {"id": page_id})

    updated = helpers.update_page(
        ctx.user,
        ctx.workspace,
        PageUpdate(page_id=page_id, **page.model_dump(exclude={"page_id"})),
    )
    return {"updated_page": PageItem.from_orm(updated).model_dump()}
