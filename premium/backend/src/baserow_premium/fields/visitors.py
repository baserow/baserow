from typing import Dict

from baserow.contrib.database.fields.utils import get_field_id_from_field_key
from baserow.core.formula import BaserowFormula, BaserowFormulaVisitor
from baserow.core.formula.parser.exceptions import FieldByIdReferencesAreDeprecated
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.utils import to_path


class BaserowFormulaReplaceFieldReferences(BaserowFormulaVisitor):
    """
    This visitor does nothing with most off the context but update the path of the
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
        return ctx.expr().accept(self)

    def process_string(self, ctx):
        ctx.getText()

    def visitFunctionCall(self, ctx: BaserowFormula.FunctionCallContext):
        function_name = ctx.func_name().accept(self).lower()
        function_argument_expressions = ctx.expr()

        return self._do_func_import(function_argument_expressions, function_name)

    def _do_func_import(self, function_argument_expressions, function_name: str):
        args = [expr.accept(self) for expr in function_argument_expressions]

        # If it's a get function then let's update the field reference.
        if function_name == "get" and isinstance(
            function_argument_expressions[0], BaserowFormula.StringLiteralContext
        ):
            unquoted_arg = args[0]
            name, *path = to_path(unquoted_arg[1:-1])
            if name == "fields":
                field_id = get_field_id_from_field_key(path[0])
                path[0] = f"field_{self.id_mapping[field_id]}"

            args = [f"'{'.'.join([name, *path])}'"]

        return f"{function_name}({','.join(args)})"

    def visitBinaryOp(self, ctx: BaserowFormula.BinaryOpContext):
        return ctx.getText()

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


def replace_field_id_references(formula: str, id_mapping: Dict[str, str]) -> str:
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

    if not formula:
        return formula

    tree = get_parse_tree_for_formula(formula)
    return BaserowFormulaReplaceFieldReferences(id_mapping).visit(tree)
