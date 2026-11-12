from baserow.core.formula.exceptions import InvalidFormulaContext
from baserow.core.formula.registries import DataProviderType, DataProviderTypeRegistry
from baserow.core.services.dispatch_context import DispatchContext

agent_action_data_provider_type_registry = DataProviderTypeRegistry()


class ToolInputDataProviderType(DataProviderType):
    type = "tool_input"

    def get_data_chunk(self, dispatch_context, path):
        if len(path) != 1 or path[0] not in dispatch_context.tool_inputs:
            raise InvalidFormulaContext("This action input no longer exists.")
        return dispatch_context.tool_inputs[path[0]]


class AgentActionDispatchContext(DispatchContext):
    data_provider_registry = agent_action_data_provider_type_registry
    own_properties = [*DispatchContext.own_properties, "tool_inputs"]
    sends_external_calls_outside_transaction = True

    def __init__(self, tool_inputs=None, **kwargs):
        self.tool_inputs = tool_inputs or {}
        super().__init__(**kwargs)
