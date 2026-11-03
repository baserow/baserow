"""
Application builder data source tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from django.utils.translation import gettext as _

from pydantic import Field

from baserow.core.tools import ToolContext

from . import helpers
from .pages import get_page_in_workspace


def list_data_sources(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
) -> dict[str, Any]:
    """
    List the data sources of a page of an application builder: id, name, type and
    table. Data sources connect the elements of the page to the rows of a table.
    """

    page = get_page_in_workspace(ctx, page_id)
    ctx.update_status(_("Listing data sources on %(name)s...") % {"name": page.name})

    data_sources = helpers.list_data_sources(ctx.user, page)
    return {"data_sources": [ds.model_dump() for ds in data_sources]}
