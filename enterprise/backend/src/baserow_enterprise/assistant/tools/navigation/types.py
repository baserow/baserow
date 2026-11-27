from typing import Annotated, Literal

from django.contrib.auth.models import AbstractUser

from pydantic import Field

from baserow.contrib.database.views.exceptions import ViewDoesNotExist
from baserow.contrib.database.views.operations import ListViewFilterOperationType
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow_enterprise.assistant.tools.database.helpers import filter_tables, get_view
from baserow_enterprise.assistant.types import (
    BaseModel,
    TableNavigationType,
    ViewFiltersNavigationType,
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


class ViewFiltersNavigationRequestType(NavigationRequestType):
    type: Literal["database-view-filters"]
    view_id: int = Field(..., description="The view whose filters to open")

    @classmethod
    def to_location(cls, user, workspace, request) -> ViewFiltersNavigationType:
        view = get_view(user, workspace, request.view_id)
        if not view.get_type().can_filter:
            raise ViewDoesNotExist()
        CoreHandler().check_permissions(
            user, ListViewFilterOperationType.type, workspace=workspace, context=view
        )
        return ViewFiltersNavigationType(
            type="database-view-filters",
            database_id=view.table.database_id,
            table_id=view.table_id,
            view_id=view.id,
            view_name=view.name,
            view_type=view.get_type().type,
        )


AnyNavigationRequestType = Annotated[
    TableNavigationRequestType | ViewFiltersNavigationRequestType,
    Field(discriminator="type"),
]
