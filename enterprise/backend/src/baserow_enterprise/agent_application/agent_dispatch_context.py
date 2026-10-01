from typing import TYPE_CHECKING, Optional

from baserow.core.services.dispatch_context import DispatchContext

if TYPE_CHECKING:
    from .models import AgentChat


class AgentDispatchContext(DispatchContext):
    """
    Dispatch context for services executed as agent tools. Exposes the
    LLM-provided runtime inputs and the trigger's event payload to service
    formulas via the agent data providers.
    """

    own_properties = [
        "chat",
        "runtime_inputs",
        "event_payload",
        "actor_overrides_integration",
    ]

    def __init__(
        self,
        chat: Optional["AgentChat"] = None,
        runtime_inputs: Optional[dict] = None,
        actor_overrides_integration: bool = False,
        **kwargs,
    ):
        self.chat = chat
        self.runtime_inputs = runtime_inputs or {}
        # Per-tool identities: the actor wins over the integration's subject.
        self.actor_overrides_integration = actor_overrides_integration
        if "event_payload" not in kwargs and chat is not None:
            kwargs["event_payload"] = chat.event_payload
        super().__init__(**kwargs)

    @property
    def data_provider_registry(self):
        from .data_providers import agent_application_data_provider_type_registry

        return agent_application_data_provider_type_registry

    def range(self, service):
        return [0, None]
