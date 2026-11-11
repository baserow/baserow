"""
Database application tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from django.utils.translation import gettext as _

from pydantic import Field

from baserow.contrib.database.tools.tables import get_database
from baserow.core.tools import ToolContext
from baserow.core.tools.applications import (
    MAX_PAGE_SIZE,
    ApplicationName,
    create_application,
    list_applications,
    rename_application,
)


def list_databases(
    ctx: ToolContext,
    page: Annotated[int, Field(ge=1, description="The page to return.")] = 1,
    size: Annotated[
        int,
        Field(ge=1, le=MAX_PAGE_SIZE, description="The number of databases a page."),
    ] = 20,
) -> dict[str, Any]:
    """
    List the databases in the workspace, with their id and name, in sidebar order.
    Returns one page, the total count, and whether more pages follow. Use the IDs
    to create tables or rename a database.
    """

    result = list_applications(ctx, types=["database"], page=page, size=size)
    return {
        "databases": [
            {"id": database["id"], "name": database["name"]}
            for database in result["applications"]
        ],
        "total": result["total"],
        "page": result["page"],
        "has_more": result["has_more"],
    }


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
        int,
        Field(
            description="The ID of the database, from list_databases, "
            "list_applications or create_database."
        ),
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
