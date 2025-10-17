from typing import Annotated, Literal

from django.contrib.auth.models import AbstractUser

from pydantic import Field

from baserow.core.models import Workspace
from baserow_enterprise.assistant.tools.database.utils import filter_tables
from baserow_enterprise.assistant.types import (
    BaseModel,
    TableNavigationType,
    WorkspaceNavigationType,
)


class NavigationRequestType(BaseModel):
    type: str

    @classmethod
    def to_location(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        request: "NavigationRequestType",
    ) -> "LocationType":
        raise NotImplementedError()


class LocationType(BaseModel):
    type: str


class TableNavigationRequestType(NavigationRequestType):
    type: Literal["database-table"] = Field(..., description="A specific table")
    table_id: int = Field(..., description="The table to open")

    @classmethod
    def to_location(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        request: "TableNavigationRequestType",
    ) -> TableNavigationType:
        table = filter_tables(user, workspace).get(id=request.table_id)

        return TableNavigationType(
            type="database-table",
            database_id=table.database_id,
            table_id=request.table_id,
            table_name=table.name,
        )


class WorkspaceNavigationRequestType(NavigationRequestType):
    type: Literal["workspace"] = Field(
        ..., description="The home page of the workspace"
    )

    @classmethod
    def to_location(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        request: "WorkspaceNavigationRequestType",
    ) -> WorkspaceNavigationType:
        return WorkspaceNavigationType(type="workspace", id=workspace.id)


AnyNavigationRequestType = Annotated[
    TableNavigationRequestType | WorkspaceNavigationRequestType,
    Field(discriminator="type"),
]
