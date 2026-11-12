from abc import ABC, abstractmethod

from baserow.core.registry import Instance, Registry
from baserow.core.services.registries import service_type_registry


class AgentActionType(Instance, ABC):
    """The small agent-specific adapter around an existing action service.

    Services own configuration and delivery. Adapters own tool defaults and the
    readable request people approve.
    """

    @property
    def service_type(self):
        return service_type_registry.get(self.type)

    def is_available(self, workspace):
        return not self.service_type.is_deactivated(workspace)

    @abstractmethod
    def get_defaults(self): ...

    @abstractmethod
    def get_configuration_errors(self, action): ...

    @abstractmethod
    def get_preview(self, action, arguments): ...

    @abstractmethod
    def dispatch(self, action, arguments): ...


class AgentActionTypeRegistry(Registry[AgentActionType]):
    name = "agent_action"


agent_action_type_registry = AgentActionTypeRegistry()
