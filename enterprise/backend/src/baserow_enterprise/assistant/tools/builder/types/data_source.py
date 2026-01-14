from typing import Annotated, Literal, Optional

from pydantic import Field

from baserow_enterprise.assistant.tools.builder.types.element import (
    BaserowFormulaObject,
)
from baserow_enterprise.assistant.tools.navigation.types import filter_tables
from baserow_enterprise.assistant.types import BaseModel


class DataSourceFilter(BaseModel):
    """Filter for data source queries."""

    field_id: int = Field(..., description="Field ID to filter on")
    type: str = Field(
        ...,
        description="Filter type: equal, not_equal, contains, higher_than, lower_than, etc.",
    )
    value: str = Field(..., description="Filter value (can be formula)")


class DataSourceSort(BaseModel):
    """Sort configuration for data source."""

    field_id: int = Field(..., description="Field ID to sort by")
    direction: Literal["ASC", "DESC"] = Field(default="ASC")


class DataSourceBase(BaseModel):
    """Base data source properties."""

    ref: str = Field(..., description="Reference ID for this data source")
    name: str = Field(..., description="Human-readable name")


class ListRowsDataSourceCreate(DataSourceBase):
    """Data source that lists rows from a table."""

    type: Literal["list_rows"] = "list_rows"
    table_id: int = Field(..., description="ID of the table to fetch from")
    filters: list[DataSourceFilter] = Field(default_factory=list)
    sortings: list[DataSourceSort] = Field(default_factory=list)
    search_query: str = Field(default="", description="Search query (can be formula)")

    def get_service_type(self) -> str:
        return "local_baserow_list_rows"

    def to_service_kwargs(self, user, workspace) -> dict:
        """Get service kwargs for service creation."""

        table = filter_tables(user, workspace).filter(id=self.table_id).first()
        kwargs = {"table": table}
        if self.search_query:
            kwargs["search_query"] = BaserowFormulaObject.create(self.search_query)
        return kwargs

    def get_filters(self) -> list[dict]:
        """Get filters in format for service creation."""

        return [
            {
                "field_id": f.field_id,
                "type": f.type,
                "value": BaserowFormulaObject.create(f.value),
            }
            for f in self.filters
        ]

    def get_sortings(self) -> list[dict]:
        """Get sortings in format for service creation."""

        return [
            {
                "field_id": s.field_id,
                "order_by": s.direction,
            }
            for s in self.sortings
        ]


class GetRowDataSourceCreate(DataSourceBase):
    """Data source that gets a single row by ID."""

    type: Literal["get_row"] = "get_row"
    table_id: int = Field(..., description="ID of the table to fetch from")
    row_id: str = Field(
        ..., description="Row ID or formula (e.g., \"get('page_parameter.id')\")"
    )

    def get_service_type(self) -> str:
        return "local_baserow_get_row"

    def to_service_kwargs(self, user, workspace) -> dict:
        table = filter_tables(user, workspace).filter(id=self.table_id).first()

        return {
            "table": table,
            "row_id": BaserowFormulaObject.create(self.row_id),
        }


AnyDataSourceCreate = Annotated[
    ListRowsDataSourceCreate | GetRowDataSourceCreate,
    Field(discriminator="type"),
]


class DataSourceItem(BaseModel):
    """Existing data source with ID."""

    id: int = Field(..., description="Data source ID")
    name: str = Field(..., description="Data source name")
    type: str = Field(..., description="Service type")
    table_id: Optional[int] = Field(default=None, description="Table ID if applicable")

    @classmethod
    def from_orm(cls, data_source) -> "DataSourceItem":
        """Create DataSourceItem from ORM DataSource instance."""

        table_id = None
        if data_source.service:
            service = data_source.service.specific
            if hasattr(service, "table_id"):
                table_id = service.table_id

        return cls(
            id=data_source.id,
            name=data_source.name,
            type=data_source.service.get_type().type if data_source.service else "",
            table_id=table_id,
        )
