from typing import Any

from baserow.core.registry import Instance, Registry
from baserow.core.services.models import Service


class AgentTriggerType(Instance):
    """
    Changes how an Agent hosts a trigger service type, under the service type's
    name. One is written only where an Agent needs something else than the service
    type gives; every other trigger service type is hosted as it is.
    """

    # The values a new service of the type starts with, unless others are given.
    default_service_values: dict[str, Any] = {}
    # The service fields only another consumer uses, which stay at their defaults.
    unused_service_fields: tuple[str, ...] = ()

    def __init__(self, service_type_name: str | None = None) -> None:
        """
        :param service_type_name: The service type an unregistered type stands in
            for, or None when the class names its own.
        """

        if service_type_name is not None:
            self.type = service_type_name
        super().__init__()

    def get_event_text(
        self, service: Service, event_payload: dict[str, Any]
    ) -> str | None:
        """
        What one event says in plain text, which opens the conversation of a
        trigger that has no message.

        :param service: The specific trigger service the event fired.
        :param event_payload: The payload the service produced for the event.
        :return: The text, or None when the event holds nothing an Agent should
            read unless a builder asks for it.
        """

        return None


class AgentTriggerTypeRegistry(Registry[AgentTriggerType]):
    name = "agent_trigger"

    def get_for_service_type(self, service_type_name: str) -> AgentTriggerType:
        """
        :param service_type_name: The name of a trigger service type.
        :return: The type registered under that name, or one that changes nothing.
        """

        return self.registry.get(service_type_name) or AgentTriggerType(
            service_type_name
        )


agent_trigger_type_registry = AgentTriggerTypeRegistry()
