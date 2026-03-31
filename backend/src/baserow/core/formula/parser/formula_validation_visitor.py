from typing import TYPE_CHECKING, List, Optional

from baserow.core.formula.exceptions import InvalidRuntimeFormula
from baserow.core.formula.parser.exceptions import (
    FieldByIdReferencesAreDeprecated,
    FormulaFunctionTypeDoesNotExist,
    InvalidNumberOfArguments,
    UnknownOperator,
)
from baserow.core.formula.parser.generated.BaserowFormula import BaserowFormula
from baserow.core.formula.parser.generated.BaserowFormulaVisitor import (
    BaserowFormulaVisitor,
)

if TYPE_CHECKING:
    from baserow.core.formula import FunctionCollection
    from baserow.core.formula.registries import DataProviderTypeRegistry


class DeferredValue:
    """
    Marker class representing a value that will be resolved at execution time.

    During validation, when we encounter nested function calls (e.g., `is_even(get('foo.bar'))`),
    the inner function's return value isn't available yet. Instead of failing validation
    because we can't type-check an unknown value, we return this marker to indicate
    "this will be a valid value at runtime, skip type validation for now."
    """

    pass


class BaserowFormulaValidationVisitor(BaserowFormulaVisitor):
    """
    A Baserow formula visitor which is responsible for validating a formula's
    function and its arguments.
    """

    def __init__(
        self,
        functions: "FunctionCollection",
        data_provider_type_registry: Optional["DataProviderTypeRegistry"] = None,
    ):
        self.functions = functions
        self.data_provider_type_registry = data_provider_type_registry

    def visitRoot(self, ctx: BaserowFormula.RootContext):
        return ctx.expr().accept(self)

    def visitStringLiteral(self, ctx: BaserowFormula.StringLiteralContext):
        # noinspection PyTypeChecker
        return self.process_string(ctx)

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

        return self.visitFunctionCall(ctx, op)

    def process_string(self, ctx):
        literal_without_outer_quotes = ctx.getText()[1:-1]
        if ctx.SINGLEQ_STRING_LITERAL() is not None:
            literal = literal_without_outer_quotes.replace("\\'", "'")
        else:
            literal = literal_without_outer_quotes.replace('\\"', '"')
        return literal

    def visitDecimalLiteral(self, ctx: BaserowFormula.DecimalLiteralContext):
        return float(ctx.getText())

    def visitBooleanLiteral(self, ctx: BaserowFormula.BooleanLiteralContext):
        return ctx.TRUE() is not None

    def visitBrackets(self, ctx: BaserowFormula.BracketsContext):
        return ctx.expr().accept(self)

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

    def visitFieldReference(self, ctx: BaserowFormula.FieldReferenceContext):
        """
        Handle field('name') syntax. There is no native support for this function
        in non-database formulas, so we raise an error.
        """

        raise InvalidRuntimeFormula("'field' is not a a supported function")

    def _parse_args_for_validation(
        self, formula_function_type, accepted_args: List
    ) -> List:
        """
        Parse arguments for validation, skipping DeferredValue instances.

        During validation, nested function calls return DeferredValue markers
        since their actual values aren't available yet. We pass these through
        unchanged rather than attempting to parse/cast them.

        :param formula_function_type: The function type with arg definitions.
        :param accepted_args: The arguments from visiting child expressions.
        :return: Parsed arguments with DeferredValue instances preserved.
        """

        if formula_function_type.args is None:
            return accepted_args

        result = []
        for index, arg in enumerate(accepted_args):
            if isinstance(arg, DeferredValue):
                # Preserve deferred values - they'll be resolved at execution time
                result.append(arg)
            elif index < len(formula_function_type.args):
                result.append(formula_function_type.args[index].parse(arg))
            else:
                result.append(arg)
        return result

    def visitFunctionCall(
        self, ctx: BaserowFormula.FunctionCallContext, function_name: str = None
    ):
        """
        Visits a function call node in the parse tree. For each function we encounter,
        we validate its args using the corresponding function type's `validate_args`
        method.

        :param ctx: The function call context from the parse tree.
        :param function_name: Optional function name to use instead of
            the one in the context. Mainly used for operator visits.
        :raises InvalidNumberOfArguments: If the number of arguments provided to the
            function does not match the expected number.
        :return: DeferredValue marker to indicate this function's result will be
            resolved at execution time.
        """

        accepted_args = [expr.accept(self) for expr in ctx.expr()]
        function_name = function_name or ctx.func_name().getText().lower()
        try:
            formula_function_type = self.functions.get(function_name)
        except FormulaFunctionTypeDoesNotExist:
            raise InvalidRuntimeFormula(f"Unsupported function '{function_name}'.")
        if not formula_function_type.validate_number_of_args(accepted_args):
            raise InvalidNumberOfArguments(formula_function_type, len(accepted_args))

        args_parsed = self._parse_args_for_validation(
            formula_function_type, accepted_args
        )
        # Only run validate_args if none of the arguments are DeferredValue.
        # DeferredValue represents nested function calls whose values aren't
        # available until execution time, so we can't type-check them.
        has_deferred = any(isinstance(arg, DeferredValue) for arg in args_parsed)
        if not has_deferred:
            formula_function_type.validate_args(
                args_parsed,
                validation_context={
                    "data_provider_type_registry": self.data_provider_type_registry
                },
            )

        # Return DeferredValue so parent function calls know this arg's value
        # will only be available at execution time
        return DeferredValue()
