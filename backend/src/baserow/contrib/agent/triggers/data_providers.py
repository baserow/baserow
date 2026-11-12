from datetime import datetime
from functools import cached_property
from typing import Any
from zoneinfo import ZoneInfo

from baserow.contrib.agent.models import AgentTrigger
from baserow.contrib.agent.registries import agent_data_provider_type_registry
from baserow.core.formula.registries import (
    DataProviderType,
    DataProviderTypeRegistry,
)
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.models import Service

FIRED_AT_PATH = "fired_at"
FIRED_AT_FORMAT = "%Y-%m-%d %H:%M"
FIRED_AT_DEFAULT_TIMEZONE = "UTC"


def trigger_timezone_name(service: Service) -> str:
    """
    :param service: The trigger's specific service.
    :return: The timezone the trigger runs in, for its message and its replies'
        dates, or UTC when its type has none.
    """

    return service.get_type().get_timezone_name(service) or FIRED_AT_DEFAULT_TIMEZONE


class AgentTriggerDispatchContext(DispatchContext):
    """
    The context a trigger message formula is resolved in: the trigger that fired,
    the payload its service produced for the event and the moment it fired.
    """

    own_properties = ["trigger", "event_payload", "fired_at"]

    def __init__(
        self, trigger: AgentTrigger, event_payload: dict[str, Any], fired_at: datetime
    ) -> None:
        """
        :param trigger: The trigger whose message is being resolved.
        :param event_payload: The payload the trigger's service produced for this
            event, in the shape its `generate_schema` describes.
        :param fired_at: When the dispatcher handled the event.
        """

        self.trigger = trigger
        self.fired_at = fired_at
        super().__init__(event_payload=event_payload, workspace=trigger.agent.workspace)

    @property
    def data_provider_registry(self) -> DataProviderTypeRegistry:
        """
        :return: The registry `get('<provider>.…')` looks providers up in.
        """

        return agent_data_provider_type_registry

    @cached_property
    def service(self) -> Service:
        """
        :return: The trigger's service in its specific form.
        """

        return self.trigger.service.specific

    def get_fired_at_display(self) -> str:
        """
        :return: When the trigger fired, as `YYYY-MM-DD HH:mm (Zone/Name)` in the
            timezone its service runs in, or in UTC when the type has none.
        """

        zone_name = trigger_timezone_name(self.service)
        local = self.fired_at.astimezone(ZoneInfo(zone_name))
        return f"{local.strftime(FIRED_AT_FORMAT)} ({zone_name})"


class TriggerDataProviderType(DataProviderType):
    """
    Exposes the payload of the trigger that started the conversation as the
    `trigger` provider, so a trigger message can read `get('trigger.<property>')`.
    Every trigger also offers `trigger.fired_at`, computed here and never part of
    the service payload; it takes precedence over a payload key of that name.
    """

    type = "trigger"

    def get_data_chunk(
        self, dispatch_context: AgentTriggerDispatchContext, path: list[str]
    ) -> Any:
        """
        Read a value of the event payload. A list service keeps its rows under
        `results`, so the first path part is the row index and the service type
        maps the rest (for example a `field_<id>` db column to the field name).

        :param dispatch_context: The context holding the trigger and its payload.
        :param path: The path parts after the provider name.
        :return: The value at the path, or `None` when there is none.
        """

        if path == [FIRED_AT_PATH]:
            return dispatch_context.get_fired_at_display()
        service = dispatch_context.service
        return service.get_type().get_result_value(
            service, dispatch_context.event_payload, path
        )
