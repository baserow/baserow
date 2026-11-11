"""
When a builder tool value is a formula rather than text. These differ from
``needs_formula``: a whole function call such as ``upper('abc')`` is a formula, and
a field value such as ``42`` goes through the formula step.
"""

import re

from baserow.core.formula.literals import EMPTY_FORMULA, needs_formula
from baserow.core.formula.parser.exceptions import BaserowFormulaException
from baserow.core.formula.parser.generated.BaserowFormula import BaserowFormula
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow_enterprise.tools.formula_utils import literal_or_placeholder

_NUMBER_OR_BOOLEAN_RE = re.compile(
    r"-?(?:0|[1-9]\d*)(?:\.\d*[1-9])?|true|false", re.IGNORECASE
)


def _is_function_call(value: str | None) -> bool:
    """Whether the whole value is one call to a function the formulas have."""

    if not value or not value.strip():
        return False
    try:
        expr = get_parse_tree_for_formula(value.strip()).expr()
    except (BaserowFormulaException, RecursionError):
        return False
    if not isinstance(expr, BaserowFormula.FunctionCallContext):
        return False
    name = expr.func_name().getText().lower()
    return name in formula_runtime_function_registry.get_types()


def is_text_formula(value: str | None) -> bool:
    """
    Whether a title, description or parameter is a formula. It also counts when the
    whole value is a function call, since a list_element_actions value like ``upper('abc')``
    is sent back.
    """

    return needs_formula(value) or _is_function_call(value)


def mapping_value_is_formula(value: str) -> bool:
    """
    Whether a field value or link parameter goes through the formula step. A number
    or boolean counts, as a field can need the type, unless a formula would show it
    differently, like ``007``. Sums like ``3/4`` are fixed text.
    """

    return is_text_formula(value) or bool(
        _NUMBER_OR_BOOLEAN_RE.fullmatch(value.strip())
    )


def text_or_placeholder(value: str | None) -> str:
    """The quoted text, or an empty placeholder for a formula the formula step stores."""

    return EMPTY_FORMULA if is_text_formula(value) else literal_or_placeholder(value)
