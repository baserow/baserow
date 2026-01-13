from typing import TYPE_CHECKING, List, Optional, Type

from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import BaserowFormulaSyntaxError
from baserow.core.formula.parser.generated.BaserowFormula import BaserowFormula
from baserow.core.formula.parser.generated.BaserowFormulaVisitor import (
    BaserowFormulaVisitor,
)
from baserow.core.formula.parser.parser import convert_string_literal_token_to_string
from baserow.core.formula.runtime_formula_types import RuntimeGet
from baserow.core.utils import to_path

if TYPE_CHECKING:
    from baserow.core.formula.registries import (
        DataProviderTypeRegistry,
        RuntimeFormulaFunction,
    )


class BaserowFormulaArgumentVisitor(BaserowFormulaVisitor):
    """
    A Baserow formula visitor which is responsible for validating a formula's
    function arguments. At the moment only one function is supported, `RuntimeGet`.

    The `RuntimeGet` function requires a `data_provider_type_registry` to be passed in
    the constructor in order to validate its argument paths. If it's given, we
    can then check if the path's provider name exists, and then using that provider,
    check if the rest of the path is valid.
    """

    def __init__(
        self, data_provider_type_registry: Optional["DataProviderTypeRegistry"] = None
    ):
        self.data_provider_type_registry = data_provider_type_registry

    def validate_argument_length(
        self,
        function: Type["RuntimeFormulaFunction"],
        expressions: List[BaserowFormula.ExprContext],
    ):
        """
        Validates that the number of arguments provided to a function matches the
        expected number of arguments for that function.

        :param function: The runtime formula function to validate against.
        :param expressions: A list of expression contexts containing the arguments.
        :raises BaserowFormulaSyntaxError: if the number of arguments does not match.
        """

        expected_args = len(function.args or [])
        if expected_args != len(expressions):
            raise BaserowFormulaSyntaxError(
                f"The '{function.type}' function requires exactly {expected_args} "
                f"argument(s), but {len(expressions)} were provided."
            )

    def validate_get_arguments(
        self, expressions: List[BaserowFormula.StringLiteralContext]
    ):
        """
        Validates the arguments of a `RuntimeGet` function call.

        :param expressions: A list of string literal contexts containing the arguments.
            This particular function expects exactly one argument.
        :raises InstanceTypeDoesNotExist: if the data provider does not exist.
        """

        self.validate_argument_length(RuntimeGet, expressions)

        # At this stage the text is single quoted, so we need to remove them.
        arguments = convert_string_literal_token_to_string(
            expressions[0].getText(), True
        )

        provider_name, *rest = to_path(arguments)
        if not provider_name:
            raise BaserowFormulaSyntaxError(
                f"The '{RuntimeGet.type}' function arguments "
                "must start with a formula provider name."
            )

        try:
            provider = self.data_provider_type_registry.get(provider_name)
        except InstanceTypeDoesNotExist:
            # Re-raise the exception but with a more precise message. We
            # are at a stage where we have enough variables that we can
            # precisely say where the argument is wrong.
            raise InstanceTypeDoesNotExist(
                provider_name,
                f"The formula provider '{provider_name}' "
                f"used in '{arguments}' does not exist in the "
                f"{self.data_provider_type_registry.provided_module_name} module.",
            )
        provider.is_valid(rest)

    def visitFunctionCall(self, ctx: BaserowFormula.FunctionCallContext):
        """
        Visits a function call node in the parse tree. If the function is `RuntimeGet`,
        then it validates its arguments.

        :param ctx: The function call context from the parse tree.
        :return: The result of visiting child nodes.
        """

        function_name = ctx.func_name().getText().lower()
        function_argument_expressions = ctx.expr()

        if function_name == RuntimeGet.type:
            self.validate_get_arguments(function_argument_expressions)

        return self.visitChildren(ctx)
