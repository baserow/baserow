from typing import TYPE_CHECKING, Optional

from baserow.core.formula.exceptions import InvalidRuntimeFormula
from baserow.core.formula.parser.exceptions import (
    FieldByIdReferencesAreDeprecated,
    FormulaFunctionTypeDoesNotExist,
    InvalidNumberOfArguments,
)
from baserow.core.formula.parser.generated.BaserowFormula import BaserowFormula
from baserow.core.formula.parser.generated.BaserowFormulaVisitor import (
    BaserowFormulaVisitor,
)

if TYPE_CHECKING:
    from baserow.core.formula import FunctionCollection
    from baserow.core.formula.registries import DataProviderTypeRegistry


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

    def visitFunctionCall(self, ctx: BaserowFormula.FunctionCallContext):
        """
        Visits a function call node in the parse tree. For each function we encounter,
        we validate its args using the corresponding function type's `validate_args`
        method.

        :param ctx: The function call context from the parse tree.
        :raises InvalidNumberOfArguments: If the number of arguments provided to the
            function does not match the expected number.
        :return: The result of visiting child nodes.
        """

        accepted_args = [expr.accept(self) for expr in ctx.expr()]
        function_name = ctx.func_name().getText().lower()
        try:
            formula_function_type = self.functions.get(function_name)
        except FormulaFunctionTypeDoesNotExist:
            raise InvalidRuntimeFormula(f"Unsupported function '{function_name}'.")
        if not formula_function_type.validate_number_of_args(accepted_args):
            raise InvalidNumberOfArguments(formula_function_type, len(accepted_args))
        args_parsed = formula_function_type.parse_args(accepted_args)
        formula_function_type.validate_args(
            args_parsed,
            validation_context={
                "data_provider_type_registry": self.data_provider_type_registry
            },
        )
