"""
Application builder workflow action tools shared by the clients that act for a
user.
"""

from typing import Annotated, Any

from django.utils.translation import gettext as _

from pydantic import Field

from baserow.core.tools import ToolContext

from . import helpers
from .pages import get_page_in_workspace


def list_actions(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
) -> dict[str, Any]:
    """
    List the workflow actions of a page of an application builder: id, type, the
    element they belong to, the event that runs them (like click or submit) and
    their field mappings. Actions run when a visitor uses an element, like
    opening a page, showing a notification or changing rows.
    """

    page = get_page_in_workspace(ctx, page_id)
    ctx.update_status(_("Listing actions on %(name)s...") % {"name": page.name})

    actions = helpers.list_workflow_actions(ctx.user, page)
    return {"workflow_actions": [a.model_dump() for a in actions]}
