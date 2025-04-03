from typing import Any, Dict, List
from mcp.server.fastmcp import FastMCP

from server.utils import make_request
from server.models import Row, Table, Field

mcp = FastMCP("Baserow MCP", dependencies=["requests"])



@mcp.tool()
def list_tables() -> List[Table]:
    """List all tables the token has access to."""

    return make_request("get", "/api/database/tables/all-tables/")


@mcp.tool()
def list_fields(table_id: int) -> List[Field]:
    """List all fields in the provided table."""

    return make_request("get", f"/api/database/fields/table/{table_id}/")


@mcp.tool()
def list_rows(table_id: int, search: str = "", page: int = 1) -> List[Row]:
    """
    List 100 rows of the given table. Optionally accepts a search parameter and
    the page that must be requested.
    """

    return make_request(
        "get",
        "/api/database/rows/table/{table_id}/",
        params={
            "user_field_names": True,
            "search": search,
            "size": 100,
            "page": page,
        },
    )


@mcp.tool()
def get_id(table_id: int, row_id: int) -> List[Row]:
    """
    Returns the row with the given row ID in the provided table.
    """

    return make_request(
        "get",
        f"/api/database/rows/table/{table_id}/{row_id}/",
        params={
            "user_field_names": True,
        },
    )


@mcp.tool()
def get_id(table_id: int, row_id: int) -> List[Row]:
    """
    Returns the row with the given row ID in the provided table.
    """

    return make_request(
        "get",
        f"/api/database/rows/table/{table_id}/{row_id}/",
        params={
            "user_field_names": True,
        },
    )


if __name__ == "__main__":
    mcp.run()
