"""
Builder data source type models.

Defines ``DataSourceCreate`` (flat) for creating data sources and
``DataSourceItem`` for reading them back.
"""

from typing import TYPE_CHECKING, Any, Callable, Literal

from pydantic import Field, PrivateAttr, model_serializer, model_validator

from baserow.core.formula.literals import EMPTY_FORMULA
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
from baserow.core.tools.formula_utils import (
    formula_desc,
    formula_object,
    literal_or_placeholder,
)
from baserow.core.tools.types import BaseModel, without_field

from .formula_policy import is_text_formula, text_or_placeholder
from .limits import MAX_NESTED_ITEMS

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.contrib.builder.tools.formulas import BuilderFormulaContext

# ---------------------------------------------------------------------------
# Data source sort
# ---------------------------------------------------------------------------

DataSourceType = Literal[
    "list_rows",
    "get_row",
    "local_baserow_list_rows",
    "local_baserow_get_row",
]

# list_data_sources reports registered names; the tables below key on short forms.
_CANONICAL_TO_SHORT_TYPE = {
    "local_baserow_list_rows": "list_rows",
    "local_baserow_get_row": "get_row",
}


class DataSourceSort(BaseModel):
    """Sort configuration for data source."""

    field_id: int = Field(..., description="Field ID to sort by.")
    direction: Literal["ASC", "DESC"] = Field(default="ASC")


# ---------------------------------------------------------------------------
# Required fields per type
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "list_rows": ("table_id",),
    # Without a row_id, a get_row reads the first row its view or filters match.
    "get_row": ("table_id",),
}


def _row_id_is_formula(value: str | None) -> bool:
    """A row id is a number or a formula: other text can't select a row."""

    return bool(value and value.strip()) and not value.strip().isdigit()


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

    @model_validator(mode="before")
    @classmethod
    def _fold_registered_type(cls, data):
        """Normalize source aliases while leaving malformed types for validation.

        :param data: The raw data source payload before model validation.
        :return: The payload with any registered type replaced by its short alias.
        """

        if isinstance(data, dict):
            source_type = data.get("type")
            if isinstance(source_type, str) and source_type in _CANONICAL_TO_SHORT_TYPE:
                data["type"] = _CANONICAL_TO_SHORT_TYPE[source_type]
        return data

    ref: str = Field(..., description="Reference ID for this data source.")
    name: str = Field(..., max_length=255, description="Human-readable name.")
    type: DataSourceType = Field(..., description="'list_rows' or 'get_row'.")
    table_id: int = Field(..., description="ID of the table to fetch from.")

    # get_row only
    row_id: str | None = Field(
        default=None,
        description=(
            "(get_row) Row ID. Can be a formula: see the tool description. Omit it "
            "to read the first row the view_id's filters and sortings select."
        ),
    )

    # list_rows only
    search_query: str | None = Field(
        default=None,
        description=(
            "(list_rows) Search query. Can be a formula: see the tool description."
        ),
    )
    sortings: list[DataSourceSort] | None = Field(
        max_length=MAX_NESTED_ITEMS,
        default=None,
        description="(list_rows) Sort configuration.",
    )
    view_id: int | None = Field(
        default=None,
        description=(
            "(list_rows) ID of an existing database table view whose filters and "
            "sortings will be applied to this data source. To filter the data "
            "source itself, use update_service_filters instead."
        ),
    )

    @model_validator(mode="after")
    def _check_required(self):
        for field_name in _REQUIRED_FIELDS.get(self.type, ()):
            value = getattr(self, field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                raise ValueError(f"'{field_name}' is required for type '{self.type}'.")
        return self

    # -- ORM helpers --------------------------------------------------------

    def get_service_type(self) -> str:
        """Return the service type string for this data source."""
        return _SERVICE_TYPE[self.type]

    def matches_existing(self, existing: "DataSourceItem") -> bool:
        """
        Check if this create request would produce a duplicate of an
        existing data source.

        Delegates to a per-type matcher in ``_STRUCTURAL_MATCH``.

        :param existing: The existing data source to compare against.
        :return: True when both share the type and structural configuration.
        """

        existing_type = _CANONICAL_TO_SHORT_TYPE.get(existing.type, existing.type)
        if self.type != existing_type:
            return False
        matcher = _STRUCTURAL_MATCH.get(self.type)
        return matcher(self, existing) if matcher else False

    def to_service_kwargs(self, user: "AbstractUser", workspace: Any) -> dict:
        """
        Build kwargs for ``DataSourceService.create_data_source()``.

        :param user: The acting user.
        :param workspace: The workspace the referenced table must belong to.
        :return: The service kwargs for this data source type.
        :raises ToolInputError: When the referenced table does not exist.
        """

        from baserow.contrib.database.table.handler import TableHandler
        from baserow.core.tools.errors import ToolInputError

        table = (
            TableHandler()
            .list_workspace_tables(user, workspace)
            .filter(id=self.table_id)
            .first()
        )
        if table is None:
            raise ToolInputError(f"Table with id {self.table_id} not found.")
        kwargs: dict[str, Any] = {"table": table}

        if self.type == "get_row" and self.row_id and self.row_id.strip():
            kwargs["row_id"] = formula_object(
                EMPTY_FORMULA
                if _row_id_is_formula(self.row_id)
                else literal_or_placeholder(self.row_id),
                mode=BASEROW_FORMULA_MODE_ADVANCED,
            )

        if self.type == "list_rows" and self.search_query:
            kwargs["search_query"] = formula_object(
                text_or_placeholder(self.search_query),
                mode=BASEROW_FORMULA_MODE_ADVANCED,
            )

        if self.view_id is not None:
            from baserow.contrib.database.tools.views import get_view
            from baserow.core.tools import ToolContext

            # The service type checks the view belongs to the table.
            ctx = ToolContext(user=user, workspace=workspace)
            kwargs["view_id"] = get_view(ctx, self.view_id).id

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

        if self.type == "get_row" and _row_id_is_formula(self.row_id):
            formulas["row_id"] = formula_desc(self.row_id)

        if (
            self.type == "list_rows"
            and self.search_query
            and is_text_formula(self.search_query)
        ):
            formulas["search_query"] = formula_desc(self.search_query)

        return formulas

    def get_required_formulas(self) -> dict[str, str]:
        """Return the formulas this data source can't run without."""

        formulas = self.get_formulas_to_create(None, None)
        return {"row_id": formulas["row_id"]} if "row_id" in formulas else {}

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
            service_kwargs["row_id"] = formula_object(
                formulas["row_id"], mode=BASEROW_FORMULA_MODE_ADVANCED
            )

        if "search_query" in formulas:
            service_kwargs["search_query"] = formula_object(
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
    name: str | None = Field(default=None, max_length=255, description="New name.")
    table_id: int | None = Field(
        default=None, description="New table ID to fetch from."
    )
    row_id: str | None = Field(
        default=None,
        description=(
            "(get_row) Row ID. Can be a formula: see the tool description. '' "
            "removes it, so the data source reads the first row its view selects."
        ),
    )
    search_query: str | None = Field(
        default=None,
        description="(list_rows) Search query. Can be a formula: see the tool description.",
    )
    view_id: int | None = Field(
        default=None,
        description=(
            "ID of a database table view whose filters and sortings will be applied."
        ),
    )

    def to_update_kwargs(self, user: "AbstractUser", workspace: Any) -> dict:
        """
        Return kwargs for ``DataSourceService.update_data_source()``.

        :param user: The acting user.
        :param workspace: The workspace the referenced table must belong to.
        :return: The service kwargs built from the fields that are set.
        :raises ToolInputError: When the referenced table does not exist.
        """

        kwargs: dict[str, Any] = {}

        if self.name is not None:
            kwargs["name"] = self.name

        if self.table_id is not None:
            from baserow.contrib.database.table.handler import TableHandler
            from baserow.core.tools.errors import ToolInputError

            table = (
                TableHandler()
                .list_workspace_tables(user, workspace)
                .filter(id=self.table_id)
                .first()
            )
            if table is None:
                raise ToolInputError(f"Table with id {self.table_id} not found.")
            kwargs["table"] = table

        # A value that needs a formula is written once it's generated, so the
        # previous one stays if generation fails.
        if self.row_id is not None and not self.row_id.strip():
            # An empty formula, not '', so the data source reads the first row.
            kwargs["row_id"] = formula_object("", mode=BASEROW_FORMULA_MODE_ADVANCED)
        elif self.row_id is not None and not _row_id_is_formula(self.row_id):
            kwargs["row_id"] = formula_object(
                literal_or_placeholder(self.row_id),
                mode=BASEROW_FORMULA_MODE_ADVANCED,
            )
        if self.search_query is not None and not is_text_formula(self.search_query):
            kwargs["search_query"] = formula_object(
                literal_or_placeholder(self.search_query),
                mode=BASEROW_FORMULA_MODE_ADVANCED,
            )

        if self.view_id is not None:
            from baserow.contrib.database.tools.views import get_view
            from baserow.core.tools import ToolContext

            # The service type checks the view belongs to the table.
            ctx = ToolContext(user=user, workspace=workspace)
            kwargs["view_id"] = get_view(ctx, self.view_id).id

        return kwargs

    def get_formulas_to_update(
        self,
        orm_data_source: Any,
        context: "BuilderFormulaContext",
    ) -> dict[str, str]:
        """Return ``{field_path: description}`` for LLM formula generation."""

        formulas: dict[str, str] = {}
        if _row_id_is_formula(self.row_id):
            formulas["row_id"] = formula_desc(self.row_id)
        if self.search_query and is_text_formula(self.search_query):
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


DataSourceChanges = without_field(
    DataSourceUpdate, "DataSourceChanges", "data_source_id"
)


# ---------------------------------------------------------------------------
# DataSourceItem (for listing)
# ---------------------------------------------------------------------------


class DataSourceItem(BaseModel):
    """Existing data source with ID."""

    id: int
    name: str
    type: str
    table_id: int | None = None
    page_name: str | None = Field(
        default=None,
        description="Page name. '[shared]' for data sources on the shared page.",
    )

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
            page_name="[shared]" if data_source.page.shared else data_source.page.name,
            table_id=table_id,
        )
        item._table_name = table_name
        return item
