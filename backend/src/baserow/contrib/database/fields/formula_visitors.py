import re
from functools import lru_cache
from typing import Dict, Optional, Union

from baserow.contrib.database.fields.utils import get_field_id_from_field_key
from baserow.core.cache import local_cache
from baserow.core.formula import (
    BASEROW_FORMULA_MODE_RAW,
    BaserowFormula,
    BaserowFormulaObject,
    BaserowFormulaVisitor,
)
from baserow.core.formula.parser.exceptions import (
    BaserowFormulaException,
    FieldByIdReferencesAreDeprecated,
)
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.utils import to_path


class BaserowFormulaReplaceFieldReferences(BaserowFormulaVisitor):
    """
    This visitor does nothing with most of the context but update the path of the
    `get()` function.
    """

    def __init__(self, id_mapping):
        self.id_mapping = id_mapping

    def visitRoot(self, ctx: BaserowFormula.RootContext):
        return ctx.expr().accept(self)

    def visitStringLiteral(self, ctx: BaserowFormula.StringLiteralContext):
        # noinspection PyTypeChecker
        return ctx.getText()

    def visitDecimalLiteral(self, ctx: BaserowFormula.DecimalLiteralContext):
        return ctx.getText()

    def visitBooleanLiteral(self, ctx: BaserowFormula.BooleanLiteralContext):
        return ctx.getText()

    def visitBrackets(self, ctx: BaserowFormula.BracketsContext):
        # Keep the parentheses, dropping them would change the evaluation
        # order of the surrounding expression.
        return f"({ctx.expr().accept(self)})"

    def visitFunctionCall(self, ctx: BaserowFormula.FunctionCallContext):
        function_name = ctx.func_name().accept(self).lower()
        function_argument_expressions = ctx.expr()

        return self._do_func_import(function_argument_expressions, function_name)

    def _do_func_import(self, function_argument_expressions, function_name: str):
        args = [expr.accept(self) for expr in function_argument_expressions]

        # If it's a get function then let's update the field reference. The
        # argument count isn't guaranteed: `get()` and `get('fields')` both
        # parse, so every index is guarded to keep an import from crashing.
        if (
            function_name == "get"
            and args
            and isinstance(
                function_argument_expressions[0], BaserowFormula.StringLiteralContext
            )
        ):
            unquoted_arg = args[0]
            name, *path = to_path(unquoted_arg[1:-1])
            if name == "fields" and path:
                field_id = get_field_id_from_field_key(path[0])
                path[0] = f"field_{self.id_mapping[field_id]}"

            args = [f"'{'.'.join([name, *path])}'"]

        return f"{function_name}({','.join(args)})"

    def visitBinaryOp(self, ctx: BaserowFormula.BinaryOpContext):
        # Visit both operands so nested get() references are also remapped.
        left = ctx.expr(0).accept(self)
        right = ctx.expr(1).accept(self)
        return f"{left}{ctx.op.text}{right}"

    def visitFunc_name(self, ctx: BaserowFormula.Func_nameContext):
        return ctx.getText()

    def visitIdentifier(self, ctx: BaserowFormula.IdentifierContext):
        return ctx.getText()

    def visitIntegerLiteral(self, ctx: BaserowFormula.IntegerLiteralContext):
        return ctx.getText()

    def visitFieldByIdReference(self, ctx: BaserowFormula.FieldByIdReferenceContext):
        raise FieldByIdReferencesAreDeprecated()

    def visitLeftWhitespaceOrComments(
        self, ctx: BaserowFormula.LeftWhitespaceOrCommentsContext
    ):
        return ctx.expr().accept(self)

    def visitRightWhitespaceOrComments(
        self, ctx: BaserowFormula.RightWhitespaceOrCommentsContext
    ):
        return ctx.expr().accept(self)


def replace_field_id_references(
    formula: Union[str, BaserowFormulaObject], id_mapping: Dict[str, str]
) -> str:
    """
    Replace the `get("fields.field_1")` field id references with the new value in the
    provided mapping.

    (
        replace_field_id_references('get("fields.field_1")', {1: 2})
        == get("fields.field_2")
    )

    :param formula: The formula where the field id references must be replaced in.
    :param id_mapping: A key value dict where the key is the old id and the value the
        new id.
    :return: The formula with the updated field references.
    """

    # Figure out what our formula string is.
    formula_str = formula if isinstance(formula, str) else formula["formula"]

    if not formula_str:
        return formula_str

    # Raw formulas are literal text, so there are no references to replace.
    if not isinstance(formula, str) and formula["mode"] == BASEROW_FORMULA_MODE_RAW:
        return formula_str

    tree = get_parse_tree_for_formula(formula_str)
    return BaserowFormulaReplaceFieldReferences(id_mapping).visit(tree)


FIELD_ID_RE = re.compile(r"^fields\.field_(\d+)$")


class FieldIDExtractingVisitor(BaserowFormulaVisitor):
    """
    Extracts all field IDs referenced in a formula string.
    Specifically, detects usages like get("fields.field_123") and collects {123}.
    """

    def __init__(self):
        super().__init__()
        self.field_ids = set()

    def visitRoot(self, ctx: BaserowFormula.RootContext):
        ctx.expr().accept(self)
        return self.field_ids

    def visitStringLiteral(self, ctx: BaserowFormula.StringLiteralContext):
        return ctx.getText()

    def visitDecimalLiteral(self, ctx: BaserowFormula.DecimalLiteralContext):
        return ctx.getText()

    def visitBooleanLiteral(self, ctx: BaserowFormula.BooleanLiteralContext):
        return ctx.getText()

    def visitIntegerLiteral(self, ctx: BaserowFormula.IntegerLiteralContext):
        return ctx.getText()

    def visitIdentifier(self, ctx: BaserowFormula.IdentifierContext):
        return ctx.getText()

    def visitFunc_name(self, ctx: BaserowFormula.Func_nameContext):
        return ctx.getText()

    def visitBrackets(self, ctx: BaserowFormula.BracketsContext):
        ctx.expr().accept(self)

    def visitBinaryOp(self, ctx: BaserowFormula.BinaryOpContext):
        # Traverse both sides of the binary op
        for child in ctx.children:
            if hasattr(child, "accept"):
                child.accept(self)

    def visitFunctionCall(self, ctx: BaserowFormula.FunctionCallContext):
        function_name = ctx.func_name().accept(self).lower()
        function_argument_expressions = ctx.expr()

        args = [expr.accept(self) for expr in function_argument_expressions]

        # Detect get('fields.field_XXX') references. The parser accepts both
        # single and double quoted string literals, so strip either style.
        if function_name == "get" and args and args[0]:
            if field_id_match := FIELD_ID_RE.match(args[0].strip("'\"")):
                self.field_ids.add(int(field_id_match.group(1)))

    def visitLeftWhitespaceOrComments(
        self, ctx: BaserowFormula.LeftWhitespaceOrCommentsContext
    ):
        ctx.expr().accept(self)

    def visitRightWhitespaceOrComments(
        self, ctx: BaserowFormula.RightWhitespaceOrCommentsContext
    ):
        ctx.expr().accept(self)


EXTRACTED_FIELD_IDS_CACHE_SIZE = 512


@lru_cache(maxsize=EXTRACTED_FIELD_IDS_CACHE_SIZE)
def _extract_field_id_dependencies(formula_str: str) -> frozenset[int]:
    """
    The ids a formula string references never change, so the parse is cached.
    Only successful parses are cached; an unparseable formula raises every
    time, which is the rare path.
    """

    tree = get_parse_tree_for_formula(formula_str)
    visitor = FieldIDExtractingVisitor()
    visitor.visit(tree)
    return frozenset(visitor.field_ids)


def extract_field_id_dependencies(
    formula: Union[str, BaserowFormulaObject],
) -> set[int]:
    """
    Extracts all field IDs referenced by get("fields.field_X") calls in the formula.
    """

    formula_str = formula if isinstance(formula, str) else formula["formula"]
    if not formula_str:
        return set()

    # Raw formulas are literal text and are never parsed, so they reference
    # nothing.
    if not isinstance(formula, str) and formula["mode"] == BASEROW_FORMULA_MODE_RAW:
        return set()

    # Copied so a caller can't mutate the cached value.
    return set(_extract_field_id_dependencies(formula_str))


TABLE_FIELD_IDS_CACHE_KEY = "formula_field_table_field_ids"


def get_table_field_ids(table_id: int) -> set[int]:
    """
    Returns the ids of the non-trashed fields in the given table, cached per
    request/task so validating many formulas doesn't repeat the query. The cache
    is invalidated by `table_schema_changed` (see fields/receivers.py).
    """

    from baserow.contrib.database.fields.models import Field

    return local_cache.get(
        f"{TABLE_FIELD_IDS_CACHE_KEY}_{table_id}",
        lambda: set(
            Field.objects.filter(table_id=table_id, trashed=False).values_list(
                "id", flat=True
            )
        ),
    )


def get_formula_field_error(
    formula: Union[str, BaserowFormulaObject], table_id: int
) -> Optional[str]:
    """
    Returns an error message when the formula cannot be parsed or references a
    field that does not exist (non-trashed) in the given table, else None.
    """

    formula_str = formula if isinstance(formula, str) else formula["formula"]
    if not formula_str:
        return None

    # Raw formulas are literal text and are never parsed, so they can't error.
    if not isinstance(formula, str) and formula["mode"] == BASEROW_FORMULA_MODE_RAW:
        return None

    try:
        referenced_ids = extract_field_id_dependencies(formula)
    except BaserowFormulaException:
        return "The formula could not be parsed."

    if referenced_ids and referenced_ids - get_table_field_ids(table_id):
        return "The formula references a field that no longer exists."

    return None
