from pydantic import Field

from baserow.contrib.database.tools.tables import (  # noqa: F401
    BaseTableItem,
    BaseTableItemCreate,
    TableItem,
    TableItemCreate,
)
from baserow_enterprise.assistant.types import BaseModel


class ListTablesFilterArg(BaseModel):
    database_id_or_name: int | str | None = Field(
        default=None,
        description="The ID or name of the database to filter. null to exclude this filter.",
    )
    table_ids_or_names: list[int | str] | None = Field(
        default=None,
        description="A list of table ids or names to filter in an OR fashion. null to exclude this filter.",
    )

    def to_tool_filters(self) -> dict:
        """The filters as the arguments of the shared ``list_tables`` tool."""

        ref = self.database_id_or_name
        items = self.table_ids_or_names or []
        return {
            "database_id": ref if isinstance(ref, int) else None,
            "database_name": ref if isinstance(ref, str) else None,
            "table_ids": [item for item in items if isinstance(item, int)],
            "table_names": [item for item in items if isinstance(item, str)],
        }
