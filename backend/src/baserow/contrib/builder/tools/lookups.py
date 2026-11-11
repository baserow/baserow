"""
Look up the builders and pages a tool works on. Every builder tool module and
`helpers` import these, so this module imports no builder tool module.
"""

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.operations import ReadPageOperationType
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.tools import ToolContext
from baserow.core.tools import applications as shared_applications


def workspace_pages(workspace: Workspace) -> QuerySet:
    """
    The pages of the workspace's builders that aren't trashed. Looking pages up
    through it makes an ID from another workspace the user belongs to look like a
    missing one.
    """

    return Page.objects.filter(builder__workspace=workspace, builder__trashed=False)


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

    return get_readable_page(ctx.user, ctx.workspace, page_id)


def get_readable_page(user: AbstractUser, workspace: Workspace, page_id: int) -> Page:
    """
    Get a page of the workspace the user can read. Raises like
    `get_page_in_workspace`.
    """

    page = PageHandler().get_page(page_id, base_queryset=workspace_pages(workspace))
    CoreHandler().check_permissions(
        user, ReadPageOperationType.type, workspace=workspace, context=page
    )
    return page
