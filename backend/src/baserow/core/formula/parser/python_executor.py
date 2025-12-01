from baserow.core.formula import BaserowFormula, BaserowFormulaVisitor
from baserow.core.formula.parser.exceptions import (
    BaserowFormulaSyntaxError,
    FieldByIdReferencesAreDeprecated,
    FormulaFunctionTypeDoesNotExist,
    UnknownOperator,
)
from baserow.core.formula.types import (
    FormulaContext,
    FormulaFunction,
    FunctionCollection,
)


class BaserowPythonExecutor(BaserowFormulaVisitor):
    def __init__(
        self,
        functions: FunctionCollection,
        context: FormulaContext,
    ):
        self.context = context
        self.functions = functions

    def visitRoot(self, ctx: BaserowFormula.RootContext):
        return ctx.expr().accept(self)

    def visitStringLiteral(self, ctx: BaserowFormula.StringLiteralContext):
        # noinspection PyTypeChecker
        return self.process_string(ctx)

    def visitDecimalLiteral(self, ctx: BaserowFormula.DecimalLiteralContext):
        return float(ctx.getText())

    def visitBooleanLiteral(self, ctx: BaserowFormula.BooleanLiteralContext):
        return ctx.TRUE() is not None

    def visitBrackets(self, ctx: BaserowFormula.BracketsContext):
        return ctx.expr().accept(self)

    def process_string(self, ctx):
        literal_without_outer_quotes = ctx.getText()[1:-1]
        if ctx.SINGLEQ_STRING_LITERAL() is not None:
            literal = literal_without_outer_quotes.replace("\\'", "'")
        else:
            literal = literal_without_outer_quotes.replace('\\"', '"')
        return literal

    def visitFunctionCall(self, ctx: BaserowFormula.FunctionCallContext):
        function_name = ctx.func_name().accept(self).lower()
        function_argument_expressions = ctx.expr()

        return self._do_func(function_argument_expressions, function_name)

    def _do_func(self, function_argument_expressions, function_name: str):
        args = [expr.accept(self) for expr in function_argument_expressions]
        formula_function_type = self._get_formula_function_type(function_name)

        formula_function_type.validate_args(args)

        args_parsed = formula_function_type.parse_args(args)

        return formula_function_type.execute(self.context, args_parsed)

    def _get_formula_function_type(self, function_name: str) -> FormulaFunction:
        try:
            return self.functions.get(function_name)
        except FormulaFunctionTypeDoesNotExist:
            raise BaserowFormulaSyntaxError(f"{function_name} is not a valid function")

    def visitBinaryOp(self, ctx: BaserowFormula.BinaryOpContext):
        if ctx.PLUS():
            op = "add"
        elif ctx.MINUS():
            op = "minus"
        elif ctx.SLASH():
            op = "divide"
        elif ctx.EQUAL():
            op = "equal"
        elif ctx.BANG_EQUAL():
            op = "not_equal"
        elif ctx.STAR():
            op = "multiply"
        elif ctx.GT():
            op = "greater_than"
        elif ctx.LT():
            op = "less_than"
        elif ctx.GTE():
            op = "greater_than_or_equal"
        elif ctx.LTE():
            op = "less_than_or_equal"
        elif ctx.AMP_AMP():
            op = "and"
        elif ctx.PIPE_PIPE():
            op = "or"
        else:
            raise UnknownOperator(ctx.getText())

        return self._do_func(ctx.expr(), op)

    def visitFunc_name(self, ctx: BaserowFormula.Func_nameContext):
        return ctx.getText()

    def visitIdentifier(self, ctx: BaserowFormula.IdentifierContext):
        return ctx.getText()

    def visitIntegerLiteral(self, ctx: BaserowFormula.IntegerLiteralContext):
        return int(ctx.getText())

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
