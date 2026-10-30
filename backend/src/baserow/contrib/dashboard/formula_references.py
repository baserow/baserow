from baserow.core.formula import (
    BaserowFormula,
    BaserowFormulaExecutionVisitor,
    get_parse_tree_for_formula,
)
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW
from baserow.core.utils import to_path


def unwrap_expression(expression):
    wrappers = (
        BaserowFormula.BracketsContext,
        BaserowFormula.LeftWhitespaceOrCommentsContext,
        BaserowFormula.RightWhitespaceOrCommentsContext,
    )
    while isinstance(expression, wrappers):
        expression = expression.expr()
    return expression


def get_literal_reference_path(expression):
    """Decode a literal get() path with the formula runtime's string/path rules."""

    expression = unwrap_expression(expression)
    if not (
        isinstance(expression, BaserowFormula.FunctionCallContext)
        and expression.func_name().getText().lower() == "get"
        and len(expression.expr()) == 1
    ):
        return None
    argument = unwrap_expression(expression.expr(0))
    if not isinstance(argument, BaserowFormula.StringLiteralContext):
        return None
    # Only evaluate the literal; no functions or data providers can be invoked.
    literal = argument.accept(BaserowFormulaExecutionVisitor({}, {}))
    return to_path(literal)


def get_direct_reference_path(formula, provider):
    """Return a validated provider path only for a direct literal get() formula."""

    if formula["mode"] == BASEROW_FORMULA_MODE_RAW or not formula["formula"]:
        return None
    reference = get_literal_reference_path(
        get_parse_tree_for_formula(formula["formula"]).expr()
    )
    if not reference or reference[0] != provider.type:
        return None
    path = reference[1:]
    provider.is_valid(path)
    return path
