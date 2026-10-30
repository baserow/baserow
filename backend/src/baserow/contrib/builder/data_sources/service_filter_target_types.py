from typing import Callable, Iterable

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.data_providers.registries import (
    builder_data_provider_type_registry,
)
from baserow.contrib.builder.data_sources.actions import UpdateDataSourceActionType
from baserow.contrib.builder.data_sources.exceptions import DataSourceDoesNotExist
from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.data_sources.operations import (
    ListDataSourcesPageOperationType,
    ReadDataSourceOperationType,
    UpdateDataSourceOperationType,
)
from baserow.contrib.integrations.local_baserow.service_filters.exceptions import (
    ServiceFilterTargetDoesNotExist,
)
from baserow.contrib.integrations.local_baserow.service_filters.registries import (
    ServiceFilterTargetType,
)
from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import get_parse_tree_for_formula
from baserow.core.formula.exceptions import InvalidRuntimeFormula
from baserow.core.formula.parser.exceptions import BaserowFormulaException
from baserow.core.formula.parser.formula_validation_visitor import (
    BaserowFormulaValidationVisitor,
)
from baserow.core.formula.parser.generated.BaserowFormula import BaserowFormula
from baserow.core.formula.parser.generated.BaserowFormulaVisitor import (
    BaserowFormulaVisitor,
)
from baserow.core.formula.parser.parser import convert_string_literal_token_to_string
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.utils import to_path

# Data sources can't read form data or the current record, and reading other data
# sources is left out to avoid dependency cycles between them.
FILTER_DATA_PROVIDERS = ("page_parameter", "user")

FORMULA_ERRORS = (BaserowFormulaException, InvalidRuntimeFormula, RecursionError)


class _GetPathCollector(BaserowFormulaVisitor):
    """Collects the paths read by the `get()` calls of a formula."""

    def __init__(self):
        self.paths: list[list[str]] = []

    def visitFunctionCall(self, ctx: BaserowFormula.FunctionCallContext):
        arguments = ctx.expr()
        if (
            ctx.func_name().getText().lower() == "get"
            and arguments
            and isinstance(arguments[0], BaserowFormula.StringLiteralContext)
        ):
            literal = arguments[0].getText()
            self.paths.append(
                to_path(
                    convert_string_literal_token_to_string(
                        literal, literal.startswith("'")
                    )
                )
            )
        return self.visitChildren(ctx)


def _page_parameter_names(page) -> list[str]:
    names = []
    for params in (page.path_params or [], page.query_params or []):
        for param in params:
            names.append(param.get("name") if isinstance(param, dict) else param)
    return names


class BuilderDataSourceServiceFilterTargetType(ServiceFilterTargetType):
    type = "builder_data_source"
    application_type = "builder"
    read_operation_type = ReadDataSourceOperationType.type
    update_operation_type = UpdateDataSourceOperationType.type
    list_operation_type = ListDataSourcesPageOperationType.type

    def get_owner(self, owner_id: int) -> DataSource:
        try:
            data_source = DataSourceHandler().get_data_source(owner_id)
        except DataSourceDoesNotExist as exc:
            raise ServiceFilterTargetDoesNotExist() from exc
        builder = data_source.page.builder
        # Published copies have no workspace, and are changed by publishing again.
        if data_source.page.trashed or builder.trashed or builder.workspace_id is None:
            raise ServiceFilterTargetDoesNotExist()
        return data_source

    def get_workspace(self, owner: DataSource) -> Workspace:
        return owner.page.builder.workspace

    def get_location(self, owner: DataSource) -> str:
        return "Shared by all pages" if owner.page.shared else owner.page.name

    def list_owners(self, user: AbstractUser, application) -> Iterable[DataSource]:
        return CoreHandler().filter_queryset(
            user,
            self.list_operation_type,
            DataSource.objects.filter(
                page__builder=application, page__trashed=False
            ).select_related("page", "service"),
            workspace=application.workspace,
        )

    def get_formula_check(
        self, user: AbstractUser, owner: DataSource
    ) -> Callable[[str], str | None]:
        page_parameters = _page_parameter_names(owner.page)

        def check(formula: str) -> str | None:
            try:
                tree = get_parse_tree_for_formula(formula)
                BaserowFormulaValidationVisitor(
                    formula_runtime_function_registry,
                    data_provider_type_registry=builder_data_provider_type_registry,
                ).visit(tree)
                collector = _GetPathCollector()
                collector.visit(tree)
            except InstanceTypeDoesNotExist as exc:
                return f"'{exc.type_name}' is not a data provider."
            except FORMULA_ERRORS as exc:
                return str(exc) or "the formula can't be parsed."

            for provider, *path in collector.paths:
                if provider not in FILTER_DATA_PROVIDERS:
                    return (
                        f"a data source filter can't read '{provider}'. It can only "
                        "read the page parameters and the logged in user."
                    )
                if provider == "page_parameter" and (
                    not path or path[0] not in page_parameters
                ):
                    available = ", ".join(page_parameters) or "none"
                    return (
                        f"'{'.'.join(path)}' is not a parameter of the page. Its "
                        f"parameters: {available}."
                    )
            return None

        return check

    def describe_formula_values(self) -> str:
        return (
            "Filter values can be formulas reading the page parameters with "
            "get('page_parameter.<name>') or the logged in user with "
            "get('user.<property>'). Nothing else is available: data sources can't "
            "read form data, the current record or other data sources."
        )

    def persist(self, user, owner, service_type, values) -> None:
        data_source = DataSourceHandler().get_data_source_for_update(owner.id)
        UpdateDataSourceActionType.do(
            user, data_source, service_type=service_type, **values
        )
