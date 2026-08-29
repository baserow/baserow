from abc import ABC
from typing import List

from baserow.core.formula.registries import DataProviderType, DataProviderTypeRegistry
from baserow.core.utils import get_value_at_path


class AgentApplicationDataProviderType(DataProviderType, ABC): ...


class ToolInputDataProviderType(AgentApplicationDataProviderType):
    """
    Resolves `get('tool_input.<name>')` formulas from the arguments the LLM
    provided when calling a service tool.
    """

    type = "tool_input"

    def get_data_chunk(self, dispatch_context, path: List[str]):
        return get_value_at_path(dispatch_context.runtime_inputs, path)


class TriggerDataProviderType(AgentApplicationDataProviderType):
    """
    Resolves `get('trigger.<path>')` formulas from the event payload that
    started the conversation, so service tools can reference trigger data.
    """

    type = "trigger"

    def get_data_chunk(self, dispatch_context, path: List[str]):
        if dispatch_context.event_payload is None:
            return None
        return get_value_at_path(dispatch_context.event_payload, path)


agent_application_data_provider_type_registry = DataProviderTypeRegistry()
agent_application_data_provider_type_registry.register(ToolInputDataProviderType())
agent_application_data_provider_type_registry.register(TriggerDataProviderType())
