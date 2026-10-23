"""
Telling the formulas in a node's values from literals, and checking them without a
model. A value is a formula when it holds a ``$formula:`` description or looks like
formula syntax (``get(``, ``concat(``, ``{{ }}``, ...). Anything else is a literal,
stored as a quoted string.
"""

import re
from typing import Any

from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula.exceptions import InvalidRuntimeFormula
from baserow.core.formula.parser.exceptions import BaserowFormulaException
from baserow.core.formula.parser.formula_validation_visitor import (
    BaserowFormulaValidationVisitor,
)
from baserow.core.formula.parser.generated.BaserowFormula import BaserowFormula
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_SIMPLE,
    BaserowFormulaMode,
    BaserowFormulaObject,
)

FORMULA_PREFIX = "$formula:"

# An empty string literal, stored for a value that is missing or could not be set.
EMPTY_FORMULA = "''"

# Formula syntax written as a value: get('...'), concat(...), {{ ... }},
# comparison functions, if(...), today(), now().
# A function name must touch its parenthesis, so text such as "Order now (today
# only)" stays a literal.
RAW_FORMULA_RE = re.compile(
    r"\bget\(|\bconcat\(|\{\{.*\}\}"
    r"|\b(?:equal|not_equal|greater_than|less_than"
    r"|greater_than_(?:or_)?equal|less_than_(?:or_)?equal)\("
    r"|\bif\(|\btoday\(|\bnow\("
)

# The node part of a previous_node path: previous_node.<node>.…
PREVIOUS_NODE_RE = re.compile(r"(previous_node\.)([^.'\"\s)]+)")


class InvalidAutomationFormula(Exception):
    """A node value that should be a formula but isn't a valid one."""

    def __init__(self, field: str, formula: str, error: str):
        self.field = field
        self.formula = formula
        self.error = error
        super().__init__(f"Invalid formula for '{field}': {error}")


def needs_formula(value: str | None) -> bool:
    """
    Whether a value is a formula: it holds a ``$formula:`` description or looks
    like formula syntax.
    """

    if not value:
        return False
    stripped = value.strip()
    return FORMULA_PREFIX in stripped.lower() or bool(RAW_FORMULA_RE.search(stripped))


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


def resolve_node_refs(formula: str, refs: dict[str, int]) -> str:
    """
    Replace the refs of nodes made earlier in the call with their IDs in the
    formula's previous_node paths, so ``get('previous_node.trigger.0.id')`` reads
    the trigger.
    """

    def replace(match: re.Match) -> str:
        node = match.group(2)
        return match.group(1) + str(refs.get(node, node))

    return PREVIOUS_NODE_RE.sub(replace, formula)


def check_automation_formula(field: str, formula: str) -> None:
    """
    Check that a formula is valid in an automation: it parses, and its functions,
    arguments and data providers exist. Whether a ``previous_node`` it reads exists
    is only known when the workflow runs.

    :param field: The name of the value, for the error message.
    :param formula: The formula to check.
    :raises InvalidAutomationFormula: With the parser's message, or with a request
        for a formula when it is empty or a ``$formula:`` description.
    """

    from baserow.contrib.automation.data_providers.registries import (
        automation_data_provider_type_registry,
    )

    stripped = formula.strip()
    if not stripped:
        raise InvalidAutomationFormula(field, formula, f"'{field}' needs a formula.")
    if FORMULA_PREFIX in stripped.lower():
        raise InvalidAutomationFormula(
            field,
            formula,
            f"'{field}' needs a formula, not a description. Write it in Baserow "
            "formula syntax.",
        )
    for match in PREVIOUS_NODE_RE.finditer(formula):
        if not match.group(2).isdigit():
            raise InvalidAutomationFormula(
                field,
                formula,
                f"'{match.group(2)}' is not a node ID. Read a node's output with "
                "get('previous_node.<node id>...'): list_nodes gives the IDs, and "
                "a node defined earlier in the same call can be named by its ref.",
            )
    try:
        tree = get_parse_tree_for_formula(formula)
        BaserowFormulaValidationVisitor(
            formula_runtime_function_registry,
            data_provider_type_registry=automation_data_provider_type_registry,
        ).visit(tree)
    except InstanceTypeDoesNotExist as exc:
        raise InvalidAutomationFormula(
            field, formula, f"'{exc.type_name}' is not a data source."
        ) from exc
    except (BaserowFormulaException, InvalidRuntimeFormula) as exc:
        raise InvalidAutomationFormula(field, formula, str(exc)) from exc
    except RecursionError as exc:
        raise InvalidAutomationFormula(
            field, formula, "The formula is nested too deeply."
        ) from exc


def formula_object(
    formula: str, mode: BaserowFormulaMode = BASEROW_FORMULA_MODE_SIMPLE
) -> BaserowFormulaObject | str:
    """The value to store for a formula: a plain string in simple mode."""

    if mode == BASEROW_FORMULA_MODE_SIMPLE:
        return formula
    return BaserowFormulaObject.create(formula, mode)


def formula_error(
    node: Any, error: InvalidAutomationFormula, **target: Any
) -> dict[str, Any]:
    """
    A ``formula_errors`` entry: the node, the value and why it wasn't stored.

    :param target: ``field_id`` for a row value, ``edge_label`` for a router
        condition.
    """

    return {
        "node_id": node.id,
        "node_label": node.label,
        "field": error.field,
        **target,
        "formula": error.formula,
        "error": error.error,
    }
