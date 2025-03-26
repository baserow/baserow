import os
import requests
from typing import Any, Dict, List
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

BASEROW_DATABASE_TOKEN = os.getenv('BASEROW_DATABASE_TOKEN')
BASEROW_BASE_URL = os.getenv('BASEROW_BASE_URL', 'https://api.baserow.io')

headers = {
    "Authorization": f"Token {BASEROW_DATABASE_TOKEN}",
    "Content-Type": "application/json"
}

mcp = FastMCP("Baserow MCP", dependencies=["requests", ""])


class Row(BaseModel):
    id: int
    order: str


class Table(BaseModel):
    id: int
    order: int
    name: str
    database_id: int


class Field(BaseModel):
    id: int
    table_id: int
    name: str
    order: int
    type: str
    primary: bool
    read_only: bool
    description: str


@mcp.tool()
def list_tables() -> List[Table]:
    """List all tables the token has access to."""

    url = f"{BASEROW_BASE_URL}/api/database/tables/all-tables/"
    response = requests.get(
        url,
        headers=headers
    )
    return response.json()


@mcp.tool()
def list_rows(table_id: int, search: str = "") -> List[Row]:
    """List or search rows in a table"""

    url = f"{BASEROW_BASE_URL}/api/database/rows/table/{table_id}/"
    response = requests.get(
        url,
        params={
            "user_field_names": True,
            "search": search
        },
        headers=headers
    )
    return response.json().get("results", [])


@mcp.resource("tables://")
def get_tables() -> List[Table]:
    """Get all the tables that the token has access to."""

    url = f"{BASEROW_BASE_URL}/api/database/tables/all-tables/"
    return requests.get(
        url,
        headers=headers,
    ).json()


@mcp.resource("fields://table/{table_id}")
def get_fields(table_id: int) -> List[Field]:
    """Get all the fields of a table."""

    url = f"{BASEROW_BASE_URL}/api/database/fields/table/{table_id}/"
    return requests.get(
        url,
        headers=headers,
    ).json()


if __name__ == "__main__":
    mcp.run()
