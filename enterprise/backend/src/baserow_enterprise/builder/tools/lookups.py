"""
Look up the builders and pages a tool works on. Every builder tool module imports
these, so this module imports none of them.
"""

from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.operations import ReadPageOperationType
from baserow.core.handler import CoreHandler
from baserow.core.tools import ToolContext
from baserow.core.tools import applications as shared_applications

from . import helpers


def get_builder_in_workspace(ctx: ToolContext, builder_id: int) -> Builder:
    """
    Get an application builder of the context's workspace.

    :raises ApplicationDoesNotExist: When the application is missing, trashed, not
        a builder, in another workspace or hidden from the user.
    """

    return shared_applications.get_application_in_workspace(ctx, builder_id, Builder)


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
