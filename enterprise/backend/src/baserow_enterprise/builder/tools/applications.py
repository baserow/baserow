"""
Application builder tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.builder.models import Builder
from baserow.core.actions import UpdateApplicationActionType
from baserow.core.exceptions import ApplicationDoesNotExist, PermissionException
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.service import CoreService
from baserow.core.tools import ToolContext
from baserow.core.tools import applications as shared_applications
from baserow.core.tools.errors import ToolInputError, validation_messages

from .themes import ThemeName, apply_theme


def get_builder_in_workspace(ctx: ToolContext, builder_id: int) -> Builder:
    """
    Get an application builder of the context's workspace.

    :raises ApplicationDoesNotExist: When the application is missing, trashed, not
        a builder, in another workspace or hidden from the user.
    """

    try:
        return CoreService().get_application(
            ctx.user,
            builder_id,
            base_queryset=Builder.objects.filter(workspace=ctx.workspace),
        )
    except PermissionException:
        # Not found, like a missing builder, so the result doesn't tell which.
        raise ApplicationDoesNotExist(builder_id)


def list_builders(
    ctx: ToolContext,
    page: Annotated[int, Field(ge=1, description="The page to return.")] = 1,
    size: Annotated[
        int,
        Field(
            ge=1,
            le=shared_applications.MAX_PAGE_SIZE,
            description="The number of application builders a page.",
        ),
    ] = shared_applications.MAX_PAGE_SIZE,
) -> dict[str, Any]:
    """
    List the application builders of the workspace with their id and name, in
    sidebar order. Returns one page, the total count, and whether more pages
    follow. Use list_pages to see the pages of an application builder.
    """

    return shared_applications.list_applications(ctx, ["builder"], page, size)


def create_builder(
    ctx: ToolContext,
    name: Annotated[
        shared_applications.ApplicationName,
        Field(
            description="The name of the application builder, at most 160 characters."
        ),
    ],
    theme: Annotated[
        ThemeName | None,
        Field(description="The theme to start with. The default is 'baserow'."),
    ] = None,
) -> dict[str, Any]:
    """
    Create one application builder in the workspace, with a theme and a connection
    to the workspace's data. A request for an application, app or website means this
    tool; use create_database, create_automation or create_dashboard only when the
    user names those. Use create_pages to add pages to it. Returns its id and name.
    """

    ctx.update_status(_("Creating application %(name)s...") % {"name": name})
    with transaction.atomic():
        builder = shared_applications.create_application(ctx, "builder", name)
        IntegrationService().create_integration(
            ctx.user,
            integration_type_registry.get("local_baserow"),
            builder,
            name="Local Baserow",
        )
        apply_theme(builder, theme or "baserow", ctx.user)
    return {"created_builder": {"id": builder.id, "name": builder.name}}


def update_builder(
    ctx: ToolContext,
    builder_id: Annotated[
        int, Field(description="The ID of the application builder, from list_builders.")
    ],
    name: Annotated[
        shared_applications.ApplicationName | None,
        Field(description="The new name, at most 160 characters."),
    ] = None,
    login_page_id: Annotated[
        int | None,
        Field(description="The ID of one of its pages, to use as the login page."),
    ] = None,
) -> dict[str, Any]:
    """
    Update an application builder: its name or its login page. Set only what should
    change. Returns its id, name and login page, and changed, which is false when
    there was nothing to change.
    """

    builder = get_builder_in_workspace(ctx, builder_id)
    ctx.update_status(_("Updating %(app_name)s...") % {"app_name": builder.name})

    requested = {"name": name, "login_page_id": login_page_id}
    changes = {
        field: value
        for field, value in requested.items()
        if value is not None and getattr(builder, field) != value
    }
    if changes:
        try:
            UpdateApplicationActionType.do(ctx.user, builder, **changes)
        except DRFValidationError as exc:
            # The builder refuses a login page it doesn't own.
            raise ToolInputError(
                f"{validation_messages(exc)} Use list_pages to find valid page IDs. "
                "No changes were applied."
            ) from exc
        builder.refresh_from_db()

    return {
        "updated_builder": {
            "id": builder.id,
            "name": builder.name,
            "login_page_id": builder.login_page_id,
        },
        "changed": bool(changes),
    }
