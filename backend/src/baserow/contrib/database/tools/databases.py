"""
Database application tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from django.utils.translation import gettext as _

from pydantic import Field

from baserow.contrib.database.tools.tables import get_database
from baserow.core.tools import ToolContext
from baserow.core.tools.applications import (
    ApplicationName,
    create_application,
    rename_application,
)


def create_database(
    ctx: ToolContext,
    name: Annotated[
        ApplicationName,
        Field(description="The name of the database, at most 160 characters."),
    ],
) -> dict[str, Any]:
    """
    Create one empty database in the workspace. Add tables to it with
    create_tables. Returns its id and name.
    """

    ctx.update_status(_("Creating database %(name)s...") % {"name": name})
    database = create_application(ctx, "database", name)
    return {"created_database": {"id": database.id, "name": database.name}}


def update_database(
    ctx: ToolContext,
    database_id: Annotated[
        int, Field(description="The ID of the database, from list_applications.")
    ],
    name: Annotated[
        ApplicationName,
        Field(description="The new name, at most 160 characters."),
    ],
) -> dict[str, Any]:
    """
    Rename a database. Returns its id and name, and changed, which is false when
    it already had that name.
    """

    database = get_database(ctx, database_id)
    return rename_application(ctx, database, name, "updated_database")
