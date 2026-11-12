import json
from datetime import datetime
from functools import cached_property
from typing import Any
from zoneinfo import ZoneInfo

from baserow.contrib.agent.constants import (
    TRIGGER_ROWS_NOT_SHOWN,
    TRIGGER_ROWS_TEXT_HEADROOM,
)
from baserow.contrib.agent.models import AgentTrigger
from baserow.contrib.agent.registries import agent_data_provider_type_registry
from baserow.contrib.agent.validators import AGENT_TEXT_MAX_LENGTH
from baserow.core.formula.registries import (
    DataProviderType,
    DataProviderTypeRegistry,
)
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.models import Service
from baserow.core.utils import get_value_at_path

FIRED_AT_PATH = "fired_at"
FIRED_AT_FORMAT = "%Y-%m-%d %H:%M"
FIRED_AT_DEFAULT_TIMEZONE = "UTC"
ROWS_PATH = "rows"


def trigger_timezone_name(service: Service) -> str:
    """
    :param service: The trigger's specific service.
    :return: The timezone the trigger runs in, for its message and its replies'
        dates, or UTC when its type has none.
    """

    return service.get_type().get_timezone_name(service) or FIRED_AT_DEFAULT_TIMEZONE


def rows_as_text(service: Service, event_payload: dict[str, Any]) -> str:
    """
    The rows of a list payload as a fenced JSON block with one row per line, for a
    message. Whole rows are left out from the end until the block fits the room a
    message keeps for it, and a note after the block says how many.

    :param service: The trigger's specific service, whose type reads the rows.
    :param event_payload: The list payload, or one batch of it.
    :return: The block, starting on a new line so it renders after any text.
    """

    rows = service.get_type().get_result_value(service, event_payload, [])
    room = AGENT_TEXT_MAX_LENGTH - TRIGGER_ROWS_TEXT_HEADROOM
    lines = []
    for row in rows:
        line = json.dumps(row, default=str, ensure_ascii=False)
        room -= len(line) + 2
        if room < 0:
            break
        lines.append(line)
    text = "\n```json\n[\n" + ",\n".join(lines) + "\n]\n```"
    hidden = len(rows) - len(lines)
    if hidden:
        text += "\n" + TRIGGER_ROWS_NOT_SHOWN.format(count=hidden)
    return text


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
            event, in the shape its `generate_schema` describes, or one batch of a
            list payload.
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

    def get_timezone_name(self) -> str:
        """
        :return: The timezone the trigger runs in, which formula functions given no
            timezone use, so their dates match Fired at.
        """

        return trigger_timezone_name(self.service)

    @cached_property
    def event_context(self) -> dict[str, Any]:
        """
        :return: The values the service type describes the event with, such as
            the count of a list payload, computed once per resolution.
        """

        return self.service.get_type().get_event_context(
            self.service, self.event_payload
        )

    def get_rows_text(self) -> str:
        """
        :return: The rows of a list payload as a fenced JSON block, see
            `rows_as_text`.
        """

        return rows_as_text(self.service, self.event_payload)

    def get_fired_at_display(self) -> str:
        """
        :return: When the trigger fired, as `YYYY-MM-DD HH:mm (Zone/Name)` in the
            timezone its service runs in, or in UTC when the type has none.
        """

        zone_name = self.get_timezone_name()
        local = self.fired_at.astimezone(ZoneInfo(zone_name))
        return f"{local.strftime(FIRED_AT_FORMAT)} ({zone_name})"


class TriggerDataProviderType(DataProviderType):
    """
    Exposes the payload of the trigger that started the conversation as the
    `trigger` provider, so a trigger message can read `get('trigger.<property>')`.
    A list payload is read as `trigger.rows`, next to the values its service type
    describes the event with, like `trigger.count`; the payload itself is never
    changed. Every trigger also offers `trigger.fired_at`, computed here and never
    part of the service payload; it takes precedence over a payload key of that
    name.
    """

    type = "trigger"

    def get_data_chunk(
        self, dispatch_context: AgentTriggerDispatchContext, path: list[str]
    ) -> Any:
        """
        Read a value of the event. `trigger.rows` alone is the rows as a fenced
        JSON block; below it, the first part is the row index and the service type
        maps the rest (for example a `field_<id>` db column to the field name).

        :param dispatch_context: The context holding the trigger and its payload.
        :param path: The path parts after the provider name.
        :return: The value at the path, or `None` when there is none.
        """

        if path == [FIRED_AT_PATH]:
            return dispatch_context.get_fired_at_display()
        service = dispatch_context.service
        service_type = service.get_type()
        payload = dispatch_context.event_payload
        if not service_type.returns_list(service):
            return service_type.get_result_value(service, payload, path)
        if path == [ROWS_PATH]:
            return dispatch_context.get_rows_text()
        if path and path[0] == ROWS_PATH:
            return service_type.get_result_value(service, payload, path[1:])
        return get_value_at_path(dispatch_context.event_context, path)

    def import_path(
        self,
        path: list[str],
        id_mapping: dict,
        service: Service | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """
        Remap the ids a path below `trigger.rows` names, such as `field_<id>`,
        through the service type, so an imported message reads the imported
        fields.

        :param path: The path parts after the provider name.
        :param id_mapping: The export-to-import id map.
        :param service: The imported trigger's specific service.
        :param kwargs: Other import context, unused here.
        :return: The imported path.
        """

        if service is None or not path or path[0] != ROWS_PATH:
            return path
        return [ROWS_PATH, *service.get_type().import_path(path[1:], id_mapping)]
