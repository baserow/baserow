"""
Workspace-scoped table access for the MCP server and Kuma. ``filter_tables`` and
``get_table`` only check that the user may list a table, so a caller reading its
rows or fields must check that operation too, see
``baserow.contrib.database.tools.tables.get_table``.
"""

from contextlib import contextmanager

from django.contrib.auth.models import AbstractUser

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.tools.errors import user_error_message
from baserow.core.mcp.exceptions import MCPToolInputError
from baserow.core.models import Workspace

# ---------------------------------------------------------------------------
# Query helpers (shared with enterprise assistant)
# ---------------------------------------------------------------------------


def _formula_error_types() -> tuple[type[Exception], ...]:
    from baserow.core.formula.parser.exceptions import BaserowFormulaException

    return (BaserowFormulaException,)


@contextmanager
def input_errors():
    """
    Turns known Baserow user errors raised inside the block into
    ``MCPToolInputError`` so the client gets a readable message.
    """

    from baserow.contrib.database.rows.exceptions import (
        FieldsNotWritable,
        RowDoesNotExist,
    )

    try:
        yield
    except RowDoesNotExist as exc:
        ids = ", ".join(str(i) for i in exc.ids)
        raise MCPToolInputError(f"Rows not found in this table: {ids}.") from exc
    except _formula_error_types() as exc:
        raise MCPToolInputError(f"Invalid formula: {exc}") from exc
    except FieldsNotWritable as exc:
        names = ", ".join(field.name for field in exc.fields)
        raise MCPToolInputError(
            f"You don't have permission to change these fields: {names}."
        ) from exc
    except Exception as exc:
        message = user_error_message(exc)
        if message is None:
            raise
        raise MCPToolInputError(message) from exc


def filter_tables(user: AbstractUser, workspace: Workspace):
    """Return all tables visible to the user in the given workspace."""
    return TableHandler().list_workspace_tables(user, workspace)


def get_table(user: AbstractUser, workspace: Workspace, table_id: int) -> Table:
    """
    Return a single table by ID, verifying workspace access.

    :raises Table.DoesNotExist: if the table is not found or not accessible.
    """
    return filter_tables(user, workspace).get(id=table_id)


# ---------------------------------------------------------------------------
# Table operations
# ---------------------------------------------------------------------------


def update_table(
    user: AbstractUser, workspace: Workspace, table_id: int, name: str
) -> dict:
    """Rename a table."""
    from baserow.contrib.database.table.actions import UpdateTableActionType

    table = get_table(user, workspace, table_id)
    UpdateTableActionType.do(user, table, name=name)
    # UpdateTableActionType mutates table in-place via the handler
    return {"id": table.id, "name": table.name, "database_id": table.database_id}


def delete_table(user: AbstractUser, workspace: Workspace, table_id: int) -> None:
    """Delete (trash) a table."""
    from baserow.contrib.database.table.actions import DeleteTableActionType

    table = get_table(user, workspace, table_id)
    DeleteTableActionType.do(user, table)
