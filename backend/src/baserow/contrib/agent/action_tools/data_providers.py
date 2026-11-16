from typing import Any

from baserow.core.formula.exceptions import InvalidFormulaContext
from baserow.core.formula.registries import DataProviderType, DataProviderTypeRegistry
from baserow.core.services.dispatch_context import DispatchContext

agent_action_data_provider_type_registry = DataProviderTypeRegistry()


class ToolInputDataProviderType(DataProviderType):
    """Gives an action's formulas the inputs of the call, by input ID."""

    type = "tool_input"

    def get_data_chunk(
        self, dispatch_context: "AgentActionDispatchContext", path: list[str]
    ) -> Any:
        """
        :param dispatch_context: The context of the call.
        :param path: The ID of one of the action's inputs.
        :return: The value the model gave that input, None when it left an
            optional one out.
        :raises InvalidFormulaContext: When the action has no such input.
        """

        if len(path) != 1 or path[0] not in dispatch_context.tool_inputs:
            raise InvalidFormulaContext("This action input no longer exists.")
        return dispatch_context.tool_inputs[path[0]]


class AgentActionDispatchContext(DispatchContext):
    """What one call of an action resolves its formulas from, and sends."""

    data_provider_registry = agent_action_data_provider_type_registry
    own_properties = [*DispatchContext.own_properties, "tool_inputs"]
    sends_external_calls_outside_transaction = True

    def __init__(self, tool_inputs: dict[str, Any] | None = None, **kwargs) -> None:
        """
        :param tool_inputs: The validated arguments of the call, by input ID.
        :param kwargs: What every dispatch context takes.
        """

        self.tool_inputs = tool_inputs or {}
        super().__init__(**kwargs)
