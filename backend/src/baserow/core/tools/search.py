"""
Workspace search tool shared by the clients that act for a user.
"""

from typing import Annotated, Any

from pydantic import Field, StringConstraints

from baserow.core.handler import CoreHandler
from baserow.core.operations import ReadWorkspaceOperationType
from baserow.core.search.handler import WorkspaceSearchHandler
from baserow.core.search.registries import workspace_search_registry
from baserow.core.tools import ToolContext, tool_execution

MAX_PAGE_SIZE = 50

SearchQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    Field(description="The text to search for."),
]


def _result_id(result_id: str) -> int | str:
    # The search returns text ids. A client passes them to other tools as numbers,
    # except a row's, which is "<table id>_<row id>".
    return int(result_id) if str(result_id).isdigit() else result_id


@tool_execution
def search_workspace(
    ctx: ToolContext,
    query: SearchQuery,
    types: Annotated[
        list[str] | None,
        Field(
            description=(
                "Only return these types: database, database_table, database_field, "
                "database_row, builder, automation, dashboard, agent. Null for all."
            )
        ),
    ] = None,
    page: Annotated[int, Field(ge=1, description="The page to return.")] = 1,
    size: Annotated[
        int,
        Field(ge=1, le=MAX_PAGE_SIZE, description="The number of results a page."),
    ] = 20,
) -> dict[str, Any]:
    """
    Search the workspace for databases, tables, fields, rows, application builders,
    automations, dashboards and agents by name or content. Only returns what the
    user can access. A row's table_id and row_id are in its metadata.
    """

    CoreHandler().check_permissions(
        ctx.user,
        ReadWorkspaceOperationType.type,
        workspace=ctx.workspace,
        context=ctx.workspace,
    )
    for search_type in types or []:
        workspace_search_registry.get(search_type)

    found = WorkspaceSearchHandler().search_workspace(
        user=ctx.user,
        workspace=ctx.workspace,
        query=query,
        limit=size,
        offset=(page - 1) * size,
        types=types,
    )

    return {
        "results": [
            {
                "type": result["type"],
                "id": _result_id(result["id"]),
                "title": result["title"],
                "subtitle": result.get("subtitle"),
                "metadata": result.get("metadata"),
            }
            for result in found["results"]
        ],
        "has_more": found["has_more"],
    }
