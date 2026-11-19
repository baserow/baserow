"""Extract properties used by runtime formulas through their data providers."""

from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import (
    BaserowFormula,
    BaserowFormulaException,
    BaserowFormulaObject,
    BaserowFormulaVisitor,
    get_parse_tree_for_formula,
)
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW
from baserow.core.utils import merge_dicts_no_duplicates, to_path


class FormulaFieldVisitor(BaserowFormulaVisitor):
    """Delegate literal get paths to the registered provider's extraction hook."""

    def __init__(self, data_provider_type_registry, **kwargs):
        self.registry = data_provider_type_registry
        self.extra_context = kwargs
        self.results = {}

    def visit(self, tree):
        """Return the union of provider properties found anywhere in the formula."""
        self.results = {}
        super().visit(tree)
        return self.results

    def visitFunctionCall(self, ctx):
        """Collect nested references without evaluating formula functions."""
        arguments = ctx.expr()
        if (
            ctx.func_name().getText().lower() == "get"
            and arguments
            and isinstance(arguments[0], BaserowFormula.StringLiteralContext)
        ):
            name, *path = to_path(arguments[0].getText()[1:-1])
            try:
                provider = self.registry.get(name)
                self.results = merge_dicts_no_duplicates(
                    self.results,
                    provider.extract_properties(path, **self.extra_context),
                )
            except (BaserowFormulaException, InstanceTypeDoesNotExist, ValueError):
                # Deleted sources and invalid paths contribute no properties.
                pass
        return self.visitChildren(ctx)


def extract_formula_properties(formulas, data_provider_type_registry, **kwargs):
    """Collect service properties from valid non-raw formulas."""
    result = {}
    for formula in formulas:
        formula = BaserowFormulaObject.to_formula(formula)
        if formula["mode"] == BASEROW_FORMULA_MODE_RAW or not formula["formula"]:
            continue
        visitor = FormulaFieldVisitor(data_provider_type_registry, **kwargs)
        try:
            visitor.visit(get_parse_tree_for_formula(formula["formula"]))
        except (BaserowFormulaException, RecursionError, ValueError):
            continue
        result = merge_dicts_no_duplicates(result, visitor.results)
    return result
