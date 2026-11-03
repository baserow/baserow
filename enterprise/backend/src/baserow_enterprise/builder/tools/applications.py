"""
Application builder tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from pydantic import Field

from baserow.contrib.builder.models import Builder
from baserow.core.service import CoreService
from baserow.core.tools import ToolContext
from baserow.core.tools import applications as shared_applications


def get_builder_in_workspace(ctx: ToolContext, builder_id: int) -> Builder:
    """
    Get an application builder of the context's workspace.

    :raises ApplicationDoesNotExist: When the application is missing, trashed, not
        a builder or in another workspace.
    """

    return CoreService().get_application(
        ctx.user,
        builder_id,
        base_queryset=Builder.objects.filter(workspace=ctx.workspace),
    )


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
