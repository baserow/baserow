"""
Application builder element tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from django.utils.translation import gettext as _

from pydantic import Field

from baserow.core.tools import ToolContext

from . import helpers
from .pages import get_page_in_workspace


def list_elements(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
) -> dict[str, Any]:
    """
    List the elements of a page of an application builder: id, type, parent
    element and whether it is a container. Elements of the shared page are
    included. Tables also show their data source
    and their columns in display order: uid, name, type, and value (text,
    boolean, rating) or label (button). A value or label is a formula: fixed
    text is quoted, and '' or "''" is an empty cell. Menus show their items in
    order: uid, name, type, page_id (or url, for a link to a custom address), and
    the sub-links of a top-level link as children.

    Elements with page_name "[shared]" are headers and footers shown on every
    page. They belong to the shared page, not to this one.
    """

    page = get_page_in_workspace(ctx, page_id)
    ctx.update_status(_("Listing elements on %(name)s...") % {"name": page.name})

    elements = helpers.list_elements(ctx.user, page)
    return {"elements": [el.model_dump() for el in elements]}
