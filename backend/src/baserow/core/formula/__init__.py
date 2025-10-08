from typing import Any

from baserow.core.formula.field import BaserowFormulaContext
from baserow.core.formula.parser.exceptions import (
    BaserowFormulaException,
    BaserowFormulaSyntaxError,
    MaximumFormulaSizeError,
)
from baserow.core.formula.parser.generated.BaserowFormula import BaserowFormula
from baserow.core.formula.parser.generated.BaserowFormulaVisitor import (
    BaserowFormulaVisitor,
)
from baserow.core.formula.types import FormulaContext, FunctionCollection

__all__ = [
    BaserowFormulaException,
    MaximumFormulaSizeError,
    BaserowFormulaVisitor,
    BaserowFormula,
    BaserowFormulaSyntaxError,
]

from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.formula.parser.python_executor import BaserowPythonExecutor


def resolve_formula(
    formula: BaserowFormulaContext,
    functions: FunctionCollection,
    formula_context: FormulaContext,
) -> Any:
    """
    Helper to resolve a formula given the formula_context.

    :param formula: the formula itself.
    :param formula_context: A dict like object that contains the data that can
        be accessed in from the formulas.
    :return: the formula result.
    """

    # If we receive a blank formula string, don't attempt to parse it.
    if not formula["formula"]:
        return ""

    tree = get_parse_tree_for_formula(formula["formula"])
    return BaserowPythonExecutor(functions, formula_context).visit(tree)
