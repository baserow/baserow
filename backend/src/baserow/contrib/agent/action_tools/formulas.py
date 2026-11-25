"""Static checks of the input references in an action's service formulas."""

from typing import Any

from baserow.core.formula.exceptions import InvalidRuntimeFormula
from baserow.core.formula.parser.formula_validation_visitor import (
    BaserowFormulaValidationVisitor,
)
from baserow.core.formula.parser.generated.BaserowFormula import BaserowFormula
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW, BaserowFormulaObject
from baserow.core.services.models import Service
from baserow.core.utils import to_path

from .data_providers import agent_action_data_provider_type_registry
from .inputs import AgentActionInput


class ActionFormulaValidationVisitor(BaserowFormulaValidationVisitor):
    """Validate stable input references without evaluating formulas or fake values."""

    def __init__(self, inputs: list[AgentActionInput]) -> None:
        """
        :param inputs: The action's declared inputs.
        """

        super().__init__(
            formula_runtime_function_registry,
            agent_action_data_provider_type_registry,
        )
        self.input_ids = {item["id"] for item in inputs}

    def visitFunctionCall(
        self, ctx: BaserowFormula.FunctionCallContext, function_name: str = None
    ) -> Any:
        """
        Validate the call like the shared formula editor, then require every
        ``get`` to name a declared input by a literal path.

        :param ctx: The function call node.
        :param function_name: The function's name, when the caller knows it.
        :return: What the shared validation returns for the call.
        :raises InvalidRuntimeFormula: When a ``get`` path is computed, or names
            anything but a declared input.
        """

        result = super().visitFunctionCall(ctx, function_name)
        name = function_name or ctx.func_name().getText().lower()
        if name == "get":
            # A computed path validates to a DeferredValue, never to a string.
            argument = ctx.expr()[0].accept(self)
            if not isinstance(argument, str):
                raise InvalidRuntimeFormula(
                    "Action input references must be literal paths."
                )
            provider, *path = to_path(argument)
            if (
                provider != "tool_input"
                or len(path) != 1
                or path[0] not in self.input_ids
            ):
                raise InvalidRuntimeFormula("This action input no longer exists.")
        return result


def reads_only_inputs(
    value: BaserowFormulaObject, inputs: list[AgentActionInput]
) -> bool:
    """
    Check a stored formula without resolving it.

    :param value: The formula.
    :param inputs: The inputs the formula may read.
    :return: False when the formula doesn't parse, has an argument its function
        refuses, reads something else than one of the inputs, or fails the check
        in any other way.
    """

    if not value["formula"] or value.get("mode") == BASEROW_FORMULA_MODE_RAW:
        return True
    try:
        ActionFormulaValidationVisitor(inputs).visit(
            get_parse_tree_for_formula(value["formula"])
        )
    # A stored formula can make the parser or a function's check raise anything.
    except Exception:
        return False
    return True


def get_single_input_id(value: BaserowFormulaObject) -> str | None:
    """
    Read a stored formula that is exactly one input, however it is spelled:
    ``get('tool_input.<id>')``, ``GET("tool_input[<id>]")``, in brackets or
    with spaces around it.

    :param value: The formula.
    :return: The ID of the input, or None when the formula is anything else.
    """

    if not value.get("formula") or value.get("mode") == BASEROW_FORMULA_MODE_RAW:
        return None
    try:
        call = _unwrap(get_parse_tree_for_formula(value["formula"]).expr())
    # A stored formula can make the parser raise anything.
    except Exception:
        return None
    if (
        not isinstance(call, BaserowFormula.FunctionCallContext)
        or call.func_name().getText().lower() != "get"
        or len(call.expr()) != 1
    ):
        return None
    argument = _unwrap(call.expr()[0])
    if not isinstance(argument, BaserowFormula.StringLiteralContext):
        return None
    provider, *path = to_path(
        BaserowFormulaValidationVisitor(
            formula_runtime_function_registry,
            agent_action_data_provider_type_registry,
        ).process_string(argument)
    )
    return path[0] if provider == "tool_input" and len(path) == 1 else None


def _unwrap(expr: BaserowFormula.ExprContext) -> BaserowFormula.ExprContext:
    """
    :return: The expression without the brackets, spaces and comments around it.
    """

    while isinstance(
        expr,
        (
            BaserowFormula.BracketsContext,
            BaserowFormula.LeftWhitespaceOrCommentsContext,
            BaserowFormula.RightWhitespaceOrCommentsContext,
        ),
    ):
        expr = expr.expr()
    return expr


def get_formula_errors(
    service: Service, inputs: list[AgentActionInput]
) -> dict[str, str]:
    """
    Find the service formulas that can't be resolved from the action's inputs,
    without resolving them.

    :param service: The action's specific service.
    :param inputs: The action's declared inputs.
    :return: ``invalid`` by service field, for each formula that fails the check.
    """

    return {
        formula.key: "invalid"
        for formula in service.get_type().formulas_to_resolve(service)
        if not reads_only_inputs(formula.formula, inputs)
    }
