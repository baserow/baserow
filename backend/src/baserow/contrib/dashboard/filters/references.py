from baserow.contrib.dashboard.data_providers import DashboardFilterDataProviderType
from baserow.contrib.dashboard.formula_references import get_literal_reference_path
from baserow.core.formula import (
    BaserowFormulaException,
    BaserowFormulaVisitor,
    get_parse_tree_for_formula,
)
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW


class DashboardFilterReferenceVisitor(BaserowFormulaVisitor):
    def __init__(self):
        self.filter_ids = set()

    def visitFunctionCall(self, ctx):
        reference = get_literal_reference_path(ctx)
        if reference and reference[0] == DashboardFilterDataProviderType.type:
            path = reference[1:]
            DashboardFilterDataProviderType().is_valid(path)
            self.filter_ids.add(int(path[0]))
        return self.visitChildren(ctx)


def get_referenced_dashboard_filters(formula):
    """Find control references, including those inside calculated conditions."""

    if formula["mode"] == BASEROW_FORMULA_MODE_RAW or not formula["formula"]:
        return set()
    visitor = DashboardFilterReferenceVisitor()
    try:
        visitor.visit(get_parse_tree_for_formula(formula["formula"]))
    except (BaserowFormulaException, RecursionError):
        # Unrelated invalid formulas must not prevent deleting a control.
        return set()
    return visitor.filter_ids
