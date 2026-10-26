"""
Telling the formulas in a node's values from literals, and checking them without a
model. A value is a formula when it holds a ``$formula:`` description or looks like
formula syntax (``get(``, ``concat(``, ``{{ }}``, ...). Anything else is a literal,
stored as a quoted string.
"""

import re
from typing import Any, Callable

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
# only)" stays a literal. A whole value that is one call, such as
# "concat ('a', 'b')", is a formula even with a space before the parenthesis.
_FUNCTION_NAMES = (
    r"get|concat|equal|not_equal|greater_than|less_than"
    r"|greater_than_(?:or_)?equal|less_than_(?:or_)?equal"
)
RAW_FORMULA_RE = re.compile(
    r"\bget\(|\bconcat\(|\{\{.*\}\}"
    r"|\b(?:equal|not_equal|greater_than|less_than"
    r"|greater_than_(?:or_)?equal|less_than_(?:or_)?equal)\("
    r"|\bif\(|\btoday\(|\bnow\("
    rf"|^(?:{_FUNCTION_NAMES})\s+\(.*\)$",
    re.DOTALL,
)

# A string literal of a formula, quoted with ' or ", with backslash escapes.
STRING_LITERAL_RE = re.compile(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"")

# A get( right before a string literal, the path it reads.
GET_OPEN_RE = re.compile(r"\bget\(\s*$")

# A previous_node path: previous_node.<node>.<rest>.
PREVIOUS_NODE_PATH_RE = re.compile(r"previous_node\.([^.]+)(.*)", re.DOTALL)

# The most output paths an error lists.
MAX_LISTED_PATHS = 30


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


def _mask_strings(formula: str) -> str:
    """The formula with the text of its string literals blanked, quotes kept."""

    return STRING_LITERAL_RE.sub(
        lambda m: m.group()[0] + " " * (len(m.group()) - 2) + m.group()[-1], formula
    )


def previous_node_paths(formula: str) -> list[tuple[int, int, str, str]]:
    """
    The previous_node paths the get() calls of a formula read, as the start and
    end of the node part in the formula, the node part and the rest of the path.
    Text in other string literals, such as concat('from previous_node.orders'), is
    left alone.
    """

    masked = _mask_strings(formula)
    paths = []
    for literal in STRING_LITERAL_RE.finditer(formula):
        if not GET_OPEN_RE.search(masked, 0, literal.start()):
            continue
        path = PREVIOUS_NODE_PATH_RE.fullmatch(literal.group()[1:-1])
        if path is None:
            continue
        start = literal.start() + 1 + path.start(1)
        paths.append((start, start + len(path.group(1)), path.group(1), path.group(2)))
    return paths


def resolve_node_refs(formula: str, refs: dict[str, int]) -> str:
    """
    Replace the refs of nodes made earlier in the call with their IDs in the
    formula's previous_node paths, so ``get('previous_node.trigger.0.id')`` reads
    the trigger.
    """

    for start, end, node, _ in reversed(previous_node_paths(formula)):
        if node in refs:
            formula = formula[:start] + str(refs[node]) + formula[end:]
    return formula


def check_automation_formula(field: str, formula: str) -> None:
    """
    Check that a formula is valid in an automation: it parses, and its functions,
    arguments and data providers exist. ``check_output_paths`` checks the
    ``previous_node`` paths it reads against the workflow.

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
    if FORMULA_PREFIX in _mask_strings(stripped).lower():
        raise InvalidAutomationFormula(
            field,
            formula,
            f"'{field}' needs a formula, not a description. Write it in Baserow "
            "formula syntax.",
        )
    for _, _, node, _ in previous_node_paths(formula):
        if not node.isdigit():
            raise InvalidAutomationFormula(
                field,
                formula,
                f"'{node}' is not a node ID. Read a node's output with "
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


def _is_index(segment: str) -> bool:
    return segment.isdigit() or segment == "*"


def _matches_properties(
    segments: list[str], properties: dict[str, Any], by_title: bool = False
) -> bool:
    """
    :param by_title: Whether the first segment may also name a row's field by
        its name, which the row services read too.
    """

    if not segments:
        return True
    prop = properties.get(segments[0])
    if prop is None and by_title:
        prop = next(
            (
                p
                for key, p in properties.items()
                if key.startswith("field_") and p.get("title") == segments[0]
            ),
            None,
        )
    if prop is None:
        return False
    rest = segments[1:]
    if not rest:
        return True
    if prop.get("properties"):
        return _matches_properties(rest, prop["properties"])
    if prop.get("type") == "array":
        if not _is_index(rest[0]):
            return False
        items = prop.get("items")
        return _matches_properties(rest[1:], items) if items else True
    # An object of unknown shape can hold anything; a plain value holds nothing.
    return prop.get("type") == "object"


def _matches_output(segments: list[str], output: dict[str, Any]) -> bool:
    if not output["properties"]:
        # The node's output isn't known, so any path is accepted.
        return True
    if output["formula_path"].count(".") > 1:
        # A node that outputs a list is read one item at a time.
        if not segments:
            return True
        if not _is_index(segments[0]):
            return False
        segments = segments[1:]
    return _matches_properties(segments, output["properties"], by_title=True)


def _listed_paths(output: dict[str, Any]) -> str:
    paths = [
        f"{output['formula_path']}.{key} ({prop['title']})"
        for key, prop in output["properties"].items()
    ]
    if len(paths) > MAX_LISTED_PATHS:
        paths = paths[:MAX_LISTED_PATHS] + ["..."]
    return ", ".join(paths)


def check_output_paths(
    field: str,
    formula: str,
    outputs: Callable[[int], dict[str, Any] | None],
) -> None:
    """
    Check that each ``get('previous_node.<id>...')`` of a formula reads a node of
    the workflow, and a path that node outputs.

    :param outputs: The output schema of a node of the workflow by its ID, as
        ``output_schema`` gives it, or None when the workflow has no such node.
    :raises InvalidAutomationFormula: Naming the paths the node outputs.
    """

    for _, _, node_id, rest in previous_node_paths(formula):
        if not node_id.isdigit():
            continue
        path = f"previous_node.{node_id}{rest}"
        segments = rest.split(".")[1:]
        output = outputs(int(node_id))
        if output is None:
            raise InvalidAutomationFormula(
                field,
                formula,
                f"Node {node_id} is not in this workflow, so '{path}' can't be "
                "read. list_nodes gives the nodes and their output paths.",
            )
        if not _matches_output(segments, output):
            raise InvalidAutomationFormula(
                field,
                formula,
                f"'{path}' is not an output of node {node_id}. Its outputs: "
                f"{_listed_paths(output)}.",
            )


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
