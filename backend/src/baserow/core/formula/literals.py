"""
Telling formula values from literals. A value is a formula when it holds a
``$formula:`` description or looks like formula syntax (``get(``, ``concat(``,
``{{ }}``, ...). Anything else is a literal, stored as a quoted string. Shared by
the tools that write formulas for the builder and automations.
"""

import re

from baserow.core.formula.parser.exceptions import BaserowFormulaException
from baserow.core.formula.parser.generated.BaserowFormula import BaserowFormula
from baserow.core.formula.parser.parser import get_parse_tree_for_formula

FORMULA_PREFIX = "$formula:"

# An empty string literal, stored for a value that is missing or could not be set.
EMPTY_FORMULA = "''"

# Formula syntax written as a value: get('...'), concat(...), comparison
# functions, if(...), today(), now(). ``{{ ... }}`` is checked separately in
# ``needs_formula``, because a regex for it backtracks quadratically on a long
# value with many ``{{`` and no ``}}``.
# A function name must touch its parenthesis, so text such as "Order now (today
# only)" stays a literal. A whole value that is one call, such as
# "concat ('a', 'b')", is a formula even with a space before the parenthesis.
_FUNCTION_NAMES = (
    r"get|concat|equal|not_equal|greater_than|less_than"
    r"|greater_than_(?:or_)?equal|less_than_(?:or_)?equal"
)
RAW_FORMULA_RE = re.compile(
    r"\bget\(|\bconcat\("
    r"|\b(?:equal|not_equal|greater_than|less_than"
    r"|greater_than_(?:or_)?equal|less_than_(?:or_)?equal)\("
    r"|\bif\(|\btoday\(|\bnow\("
    rf"|^(?:{_FUNCTION_NAMES})\s+\(.*\)$",
    re.DOTALL,
)

# A string literal of a formula, quoted with ' or ", with backslash escapes.
STRING_LITERAL_RE = re.compile(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"")


def needs_formula(value: str | None) -> bool:
    """
    Whether a value is a formula: it holds a ``$formula:`` description or looks
    like formula syntax.
    """

    if not value:
        return False
    stripped = value.strip()
    if FORMULA_PREFIX in stripped.lower() or _has_template_braces(stripped):
        return True
    return bool(RAW_FORMULA_RE.search(stripped))


def _has_template_braces(value: str) -> bool:
    """Whether the value holds a ``{{`` followed later by ``}}``."""

    start = value.find("{{")
    return start != -1 and value.find("}}", start + 2) != -1


def is_valid_formula(value: str) -> bool:
    """Whether the formula can be parsed."""

    try:
        get_parse_tree_for_formula(value)
    except (BaserowFormulaException, RecursionError):
        return False
    return True


def is_string_literal(value: str) -> bool:
    """
    Whether the formula is a single, complete string literal. Checking the first
    and last character isn't enough: ``'Managers' Week'`` looks quoted, but is
    invalid syntax.
    """

    try:
        tree = get_parse_tree_for_formula(value)
    except (BaserowFormulaException, RecursionError):
        return False
    return isinstance(tree.expr(), BaserowFormula.StringLiteralContext)


def wrap_static_string(value: str) -> str:
    """
    A literal as a formula string literal. A value that already is one (``'Submit'``)
    is kept, so it isn't quoted twice. Anything else is escaped the way the
    frontend does it, so apostrophes and backslashes still give a valid formula.
    """

    if is_string_literal(value):
        return value
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"
