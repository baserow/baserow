from datetime import datetime
from typing import List, Dict, Any, Literal, Optional, Tuple
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from asgiref.sync import sync_to_async

from baserow.contrib.database.models import Database, Table
from baserow_enterprise.ai_assistant.tools.base import BaserowBaseTool, BaserowToolError
from baserow_enterprise.ai_assistant.utils.types import AssistantState
from django.contrib.auth.models import AbstractUser
from baserow.core.models import Workspace
from langchain_core.runnables import RunnableConfig
from baserow.contrib.database.table.handler import TableHandler
from django.db.models import Q, F


class NameFilter(BaseModel):
    """Filter for table names."""

    value: Optional[str] = Field(
        default=None, description="Name or partial name of the table to find"
    )
    operator: Literal["icontains", "istartswith", "iendswith"] = Field(
        default="icontains",
        description=(
            "Operator for name filtering. Always prefer 'icontains' for partial "
            "matches unless the user explicitly requests a different operator."
        ),
    )


class CreateOnFilter(BaseModel):
    """Filter for creation date."""

    value: Optional[str] = Field(
        default=None, description="Creation date of the table in ISO format"
    )
    operator: Literal["exact", "gt", "lt"] = Field(
        default="exact", description="Operator for creation date filtering"
    )


class TableFinderToolArgs(BaseModel):
    """Filter for tables."""

    name: NameFilter = Field(default_factory=NameFilter, help="Filter for table names")
    created_on: Optional[CreateOnFilter] = Field(
        default=None, description="Filter for creation date"
    )
    database_id: Optional[int] = Field(
        default=None, description="ID of the database to filter tables by"
    )


class TableFinderToolTableItem(BaseModel):
    id: int
    name: str
    created_on: datetime
    database_id: int
    database_name: str

    @property
    def url(self) -> str:
        return f"/database/{self.database_id}/table/{self.id}"


class TableFinderToolArtifact(BaseModel):
    tables: List[TableFinderToolTableItem]


class TableFinderTool(BaserowBaseTool):
    name: str = "table_finder"
    description: str = (
        "Find tables by name or creation date in the current workspace. "
        "Returns table information including ID and name for navigation."
    )
    args_schema: type = TableFinderToolArgs

    def _run_impl(
        self,
        name: NameFilter,
        created_on: Optional[CreateOnFilter] = None,
        database_id: Optional[int] = None,
    ) -> Tuple[str, TableFinderToolArtifact | BaserowToolError]:
        """Search for tables by name."""
        try:
            table_qs = (
                TableHandler()
                .list_workspace_tables(self._user, self._workspace)
                .filter(Q(**{f"name__{name.operator}": name.value}))
            )

            if created_on:
                table_qs = table_qs.filter(
                    **{f"created_on__{created_on.operator}": created_on.value}
                )

            if database_id:
                table_qs = table_qs.filter(database_id=database_id)

            tables = table_qs.annotate(database_name=F("database__name")).values(
                "id", "name", "created_on", "database_id", "database_name"
            )[:20]

            count = len(tables)
            return (
                f"Found {count} tables matching the criteria.",
                TableFinderToolArtifact(tables=tables),
            )

        except Exception as e:
            return "Error", BaserowToolError(
                status="error",
                args={
                    "name": name,
                    "created_on": created_on,
                    "database_id": database_id,
                },
                error=str(e),
            )


class TableURLToolArgs(BaseModel):
    table_id: int = Field(description="The ID of the table to get the URL for.")


class TableURLTool(BaserowBaseTool):
    name: str = "table_url"
    description: str = "Get the URL for a specific table, given its ID."
    args_schema: type = TableURLToolArgs

    def _run(
        self, *args, config: RunnableConfig, **kwargs
    ) -> Tuple[str, TableFinderToolArtifact | BaserowToolError]:
        self._init_run(config)
        return self._run_impl(*args, **kwargs)

    def _run_impl(self, table_id: int) -> Tuple[str, str]:
        """Get the URL for a specific table."""
        try:
            table = (
                TableHandler()
                .list_workspace_tables(self._user, self._workspace)
                .filter(id=table_id)
                .annotate(database_name=F("database__name"))
                .values("id", "name", "created_on", "database_id", "database_name")
                .first()
            )
            if not table:
                raise ValueError("Table not found")
            return ("Table found", TableFinderToolArtifact(tables=[table]))
        except Exception as e:
            return "Error", BaserowToolError(
                status="error",
                args={"table_id": table_id},
                error=str(e),
            )
