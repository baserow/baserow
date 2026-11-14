"""Static checks of the input references in an action's service formulas."""

from typing import Any

from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import BaserowFormulaException
from baserow.core.formula.exceptions import InvalidRuntimeFormula
from baserow.core.formula.parser.formula_validation_visitor import (
    BaserowFormulaValidationVisitor,
)
from baserow.core.formula.parser.generated.BaserowFormula import BaserowFormula
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW
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


def get_formula_errors(
    service: Service, inputs: list[AgentActionInput]
) -> dict[str, str]:
    """
    Find the service formulas that can't be resolved from the action's inputs,
    without resolving them.

    :param service: The action's specific service.
    :param inputs: The action's declared inputs.
    :return: ``invalid`` by service field, for each formula that doesn't parse or
        reads something else than a declared input.
    """

    errors = {}
    for formula in service.get_type().formulas_to_resolve(service):
        value = formula.formula
        if not value["formula"] or value.get("mode") == BASEROW_FORMULA_MODE_RAW:
            continue
        try:
            ActionFormulaValidationVisitor(inputs).visit(
                get_parse_tree_for_formula(value["formula"])
            )
        except (BaserowFormulaException, InstanceTypeDoesNotExist):
            errors[formula.key] = "invalid"
    return errors
