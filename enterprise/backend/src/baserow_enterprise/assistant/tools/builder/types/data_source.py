"""
Builder data source type models.

Defines ``DataSourceCreate`` (flat) for creating data sources and
``DataSourceItem`` for reading them back.
"""

from typing import TYPE_CHECKING, Any, Callable, Literal

from pydantic import Field, PrivateAttr, model_serializer, model_validator

from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_ADVANCED,
    BaserowFormulaObject,
)
from baserow_enterprise.assistant.tools.shared.formula_utils import (
    formula_desc,
    literal_or_placeholder,
    needs_formula,
)
from baserow_enterprise.assistant.types import BaseModel

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow_enterprise.assistant.tools.builder.agents import BuilderFormulaContext

# ---------------------------------------------------------------------------
# Data source sort
# ---------------------------------------------------------------------------

DataSourceType = Literal["list_rows", "get_row"]


class DataSourceSort(BaseModel):
    """Sort configuration for data source."""

    field_id: int = Field(..., description="Field ID to sort by.")
    direction: Literal["ASC", "DESC"] = Field(default="ASC")


# ---------------------------------------------------------------------------
# Required fields per type
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "list_rows": ("table_id",),
    "get_row": ("table_id", "row_id"),
}

# ---------------------------------------------------------------------------
# Service type mapping
# ---------------------------------------------------------------------------

_SERVICE_TYPE: dict[str, str] = {
    "list_rows": "local_baserow_list_rows",
    "get_row": "local_baserow_get_row",
}

# Structural match dispatch: type -> (new, existing) -> bool
# Used to detect duplicate data sources regardless of name.
_STRUCTURAL_MATCH: dict[str, Callable] = {
    "list_rows": lambda new, ex: new.table_id == ex.table_id,
    "get_row": lambda new, ex: False,  # row_id varies, can't dedup
}


# ---------------------------------------------------------------------------
# DataSourceCreate (flat)
# ---------------------------------------------------------------------------


class DataSourceCreate(BaseModel):
    """
    Flat model for creating a data source: list_rows or get_row.

    Type-specific fields are optional — a ``@model_validator`` enforces
    the correct required fields per type.
    """

    ref: str = Field(..., description="Reference ID for this data source.")
    name: str = Field(..., description="Human-readable name.")
    type: DataSourceType = Field(..., description="'list_rows' or 'get_row'.")
    table_id: int = Field(..., description="ID of the table to fetch from.")

    # get_row only
    row_id: str | None = Field(
        default=None,
        description=("(get_row) Row ID. Supports $formula: prefix for dynamic values."),
    )

    # list_rows only
    search_query: str | None = Field(
        default=None,
        description=(
            "(list_rows) Search query. Supports $formula: prefix for dynamic values."
        ),
    )
    sortings: list[DataSourceSort] | None = Field(
        default=None,
        description="(list_rows) Sort configuration.",
    )
    view_id: int | None = Field(
        default=None,
        description=(
            "(list_rows) ID of a database table view whose filters and sortings "
            "will be applied to this data source. Use create_views and "
            "create_view_filters to set up the view first."
        ),
    )

    @model_validator(mode="after")
    def _check_required(self):
        for field_name in _REQUIRED_FIELDS.get(self.type, ()):
            if getattr(self, field_name) is None:
                raise ValueError(f"'{field_name}' is required for type '{self.type}'.")
        return self

    # -- ORM helpers --------------------------------------------------------

    def get_service_type(self) -> str:
        """Return the service type string for this data source."""
        return _SERVICE_TYPE[self.type]

    def matches_existing(self, existing: "DataSourceItem") -> bool:
        """Check if this create request would produce a duplicate of *existing*.

        Delegates to a per-type matcher in ``_STRUCTURAL_MATCH``.
        """

        if self.type != existing.type:
            return False
        matcher = _STRUCTURAL_MATCH.get(self.type)
        return matcher(self, existing) if matcher else False

    def to_service_kwargs(self, user: "AbstractUser", workspace: Any) -> dict:
        """Build kwargs for ``DataSourceService.create_data_source()``."""

        from baserow_enterprise.assistant.tools.builder.helpers import ToolInputError
        from baserow_enterprise.assistant.tools.database.helpers import filter_tables

        table = filter_tables(user, workspace).filter(id=self.table_id).first()
        if table is None:
            raise ToolInputError(f"Table with id {self.table_id} not found.")
        kwargs: dict[str, Any] = {"table": table}

        if self.type == "get_row" and self.row_id is not None:
            kwargs["row_id"] = BaserowFormulaObject.create(
                literal_or_placeholder(self.row_id),
                mode=BASEROW_FORMULA_MODE_ADVANCED,
            )

        if self.type == "list_rows" and self.search_query:
            kwargs["search_query"] = BaserowFormulaObject.create(
                literal_or_placeholder(self.search_query),
                mode=BASEROW_FORMULA_MODE_ADVANCED,
            )

        if self.view_id is not None:
            from baserow_enterprise.assistant.tools.database.helpers import get_view

            kwargs["view"] = get_view(user, workspace, self.view_id)

        return kwargs

    def get_sortings(self) -> list[dict]:
        """Return sortings in ORM format."""
        if not self.sortings:
            return []
        return [
            {"field_id": s.field_id, "order_by": s.direction} for s in self.sortings
        ]

    # -- Formula helpers ----------------------------------------------------

    def get_formulas_to_create(
        self,
        orm_data_source: Any,
        context: "BuilderFormulaContext",
    ) -> dict[str, str]:
        """Return ``{field_path: description}`` for LLM formula generation."""

        formulas: dict[str, str] = {}

        if self.type == "get_row" and self.row_id and needs_formula(self.row_id):
            formulas["row_id"] = formula_desc(self.row_id)

        if (
            self.type == "list_rows"
            and self.search_query
            and needs_formula(self.search_query)
        ):
            formulas["search_query"] = formula_desc(self.search_query)

        return formulas

    def update_with_formulas(
        self,
        user: "AbstractUser",
        orm_data_source: Any,
        formulas: dict[str, str],
    ) -> None:
        """Apply LLM-generated formulas to this data source."""

        if not formulas:
            return

        from baserow.contrib.builder.data_sources.handler import DataSourceHandler
        from baserow.contrib.builder.data_sources.service import DataSourceService
        from baserow.core.services.registries import service_type_registry

        service_kwargs: dict[str, Any] = {}

        if "row_id" in formulas:
            service_kwargs["row_id"] = BaserowFormulaObject.create(
                formulas["row_id"], mode=BASEROW_FORMULA_MODE_ADVANCED
            )

        if "search_query" in formulas:
            service_kwargs["search_query"] = BaserowFormulaObject.create(
                formulas["search_query"], mode=BASEROW_FORMULA_MODE_ADVANCED
            )

        if service_kwargs:
            ds_for_update = DataSourceHandler().get_data_source_for_update(
                orm_data_source.id
            )
            service_type = service_type_registry.get_by_model(
                ds_for_update.service.specific
            )
            DataSourceService().update_data_source(
                user, ds_for_update, service_type=service_type, **service_kwargs
            )


# ---------------------------------------------------------------------------
# DataSourceUpdate
# ---------------------------------------------------------------------------


class DataSourceUpdate(BaseModel):
    """
    Update an existing data source's properties.

    All fields are optional. Only non-None fields are sent to the service layer.
    """

    data_source_id: int = Field(..., description="ID of the data source to update.")
    name: str | None = Field(default=None, description="New name.")
    table_id: int | None = Field(
        default=None, description="New table ID to fetch from."
    )
    row_id: str | None = Field(
        default=None,
        description="(get_row) Row ID. Supports $formula: prefix.",
    )
    search_query: str | None = Field(
        default=None,
        description="(list_rows) Search query. Supports $formula: prefix.",
    )
    view_id: int | None = Field(
        default=None,
        description=(
            "ID of a database table view whose filters and sortings will be applied."
        ),
    )

    def to_update_kwargs(self, user: "AbstractUser", workspace: Any) -> dict:
        """Return kwargs for ``DataSourceService.update_data_source()``."""

        kwargs: dict[str, Any] = {}

        if self.name is not None:
            kwargs["name"] = self.name

        if self.table_id is not None:
            from baserow_enterprise.assistant.tools.builder.helpers import (
                ToolInputError,
            )
            from baserow_enterprise.assistant.tools.database.helpers import (
                filter_tables,
            )

            table = filter_tables(user, workspace).filter(id=self.table_id).first()
            if table is None:
                raise ToolInputError(f"Table with id {self.table_id} not found.")
            kwargs["table"] = table

        if self.row_id is not None:
            kwargs["row_id"] = BaserowFormulaObject.create(
                literal_or_placeholder(self.row_id),
                mode=BASEROW_FORMULA_MODE_ADVANCED,
            )

        if self.search_query is not None:
            kwargs["search_query"] = BaserowFormulaObject.create(
                literal_or_placeholder(self.search_query),
                mode=BASEROW_FORMULA_MODE_ADVANCED,
            )

        if self.view_id is not None:
            from baserow_enterprise.assistant.tools.database.helpers import get_view

            kwargs["view"] = get_view(user, workspace, self.view_id)

        return kwargs

    def get_formulas_to_update(
        self,
        orm_data_source: Any,
        context: "BuilderFormulaContext",
    ) -> dict[str, str]:
        """Return ``{field_path: description}`` for LLM formula generation."""

        formulas: dict[str, str] = {}
        if self.row_id and needs_formula(self.row_id):
            formulas["row_id"] = formula_desc(self.row_id)
        if self.search_query and needs_formula(self.search_query):
            formulas["search_query"] = formula_desc(self.search_query)
        return formulas

    def get_updated_field_names(self) -> list[str]:
        """Return names of fields that were explicitly set (non-None)."""

        skip = {"data_source_id"}
        return [
            name
            for name in self.__class__.model_fields
            if name not in skip and getattr(self, name) is not None
        ]


# ---------------------------------------------------------------------------
# DataSourceItem (for listing)
# ---------------------------------------------------------------------------


class DataSourceItem(BaseModel):
    """Existing data source with ID."""

    id: int
    name: str
    type: str
    table_id: int | None = None

    _table_name: str | None = PrivateAttr(default=None)

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        data = handler(self)
        if self._table_name is not None:
            data["table_name"] = self._table_name
        return data

    @classmethod
    def from_orm(cls, data_source) -> "DataSourceItem":
        """Create DataSourceItem from ORM DataSource instance."""

        table_id = None
        table_name = None
        if data_source.service:
            service = data_source.service.specific
            if hasattr(service, "table_id"):
                table_id = service.table_id
            if hasattr(service, "table") and service.table:
                table_name = service.table.name

        item = cls(
            id=data_source.id,
            name=data_source.name,
            type=data_source.service.get_type().type if data_source.service else "",
            table_id=table_id,
        )
        item._table_name = table_name
        return item
