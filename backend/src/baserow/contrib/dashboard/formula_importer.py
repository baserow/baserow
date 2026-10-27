import logging

from baserow.contrib.dashboard.data_providers import (
    dashboard_formula_import_data_provider_type_registry,
)
from baserow.contrib.dashboard.formula_references import get_literal_reference_path
from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import (
    BaserowFormulaException,
    BaserowFormulaObject,
    get_parse_tree_for_formula,
)
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW
from baserow.core.services.formula_importer import BaserowFormulaImporter

logger = logging.getLogger(__name__)


class DashboardFormulaImporter(BaserowFormulaImporter):
    def get_data_provider_type_registry(self):
        return dashboard_formula_import_data_provider_type_registry

    def visitFunctionCall(self, ctx):
        reference = get_literal_reference_path(ctx)
        if reference is None:
            return super().visitFunctionCall(ctx)

        provider_name, *path = reference
        provider = self.get_data_provider_type_registry().get(provider_name)
        provider.is_valid(path)
        if provider_name == "dashboard_filter" and int(path[0]) not in (
            self.id_mapping.get("dashboard_filters", {})
        ):
            # Deleted controls are not exported. Keep their absent value without
            # retaining a reference to the original dashboard.
            return "null()"
        imported_path = provider.import_path(
            path, self.id_mapping, **self.extra_context
        )
        return f"get('{'.'.join([provider_name, *imported_path])}')"


def import_formula(formula, id_mapping, **kwargs):
    formula = BaserowFormulaObject.to_formula(formula)
    if formula["mode"] == BASEROW_FORMULA_MODE_RAW or not formula["formula"]:
        return formula
    try:
        tree = get_parse_tree_for_formula(formula["formula"])
        updated = DashboardFormulaImporter(id_mapping, **kwargs).visit(tree)
    except (
        BaserowFormulaException,
        RecursionError,
        InstanceTypeDoesNotExist,
        ValueError,
    ) as exc:
        logger.warning("Skipping the import of an invalid dashboard formula: %s", exc)
        return formula
    return {**formula, "formula": updated}
