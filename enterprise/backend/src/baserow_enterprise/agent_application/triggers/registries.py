import json
import re
from typing import Any, Callable, Dict, Iterable, Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.db import router

from loguru import logger

from baserow.core.registry import Instance, Registry
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry

from ..exceptions import AgentTriggerDoesNotExist
from ..handler import AgentChatHandler
from ..models import AgentChatMessage, AgentTrigger

_EVENT_PAYLOAD_PROMPT_LIMIT = 8000

# A bulk import can fire a trigger with thousands of rows; the stored payload
# backs the conversation's preview and the opening prompt only, so lists are
# cut to what a person would look at and long strings to what the prompt
# would show.
_EVENT_PAYLOAD_LIST_LIMIT = 50


def cap_event_payload(payload, depth: int = 0):
    if isinstance(payload, dict):
        return {
            key: cap_event_payload(value, depth + 1) for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [
            cap_event_payload(value, depth + 1)
            for value in payload[:_EVENT_PAYLOAD_LIST_LIMIT]
        ]
    if isinstance(payload, str) and len(payload) > _EVENT_PAYLOAD_PROMPT_LIMIT:
        return payload[:_EVENT_PAYLOAD_PROMPT_LIMIT] + "… (truncated)"
    return payload


def _count_in_window(cache_key: str) -> int:
    """
    Counts within a 60s window aligned to the first hit. The key can expire
    between `add` and `incr`, in which case this hit opens a new window.
    """

    cache.add(cache_key, 0, timeout=60)
    try:
        return cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=60)
        return 1


class AgentTriggerType(Instance):
    """
    Connects a trigger service type to the agent application: when the
    service's event fires for a service owned by an agent trigger, a new
    agent chat is started with an opening prompt describing the event.
    """

    # The trigger service type this agent trigger listens to.
    service_type: str = None

    def after_register(self):
        service_type_registry.get(self.service_type).start_listening(self.on_event)
        return super().after_register()

    def before_unregister(self):
        service_type_registry.get(self.service_type).stop_listening(self.on_event)
        return super().before_unregister()

    def get_opening_headline(self, trigger: AgentTrigger) -> str:
        return f"Trigger: {self.type} event occurred."

    def get_tokens(self, trigger: AgentTrigger) -> list[dict]:
        """
        The `{{trigger.…}}` tokens the instructions may use for this trigger,
        as `{token, description}` dicts. Resolution goes through
        `get_token_aliases`.
        """

        return []

    def get_token_aliases(self, trigger_payload: Any) -> dict[str, list]:
        """
        Maps the first segment(s) of a token path onto a path inside the event
        payload, e.g. `{"row": ["results", 0]}` so that `trigger.row.Name`
        reads `payload["results"][0]["Name"]`.
        """

        return {}

    def get_sample_payload(self, trigger: AgentTrigger) -> Optional[dict]:
        """
        What "Run once" hands the agent, and what the configuration shows as
        the example payload.
        """

        return None

    def prepare_config(self, config: dict) -> dict:
        """
        Validates and normalizes the trigger's own options before they are
        stored. Unknown keys are dropped so a stale client cannot store
        anything the type does not read.

        :raises rest_framework.exceptions.ValidationError: When invalid.
        """

        return {}

    def should_run(self, trigger: AgentTrigger, event_payload: Any) -> bool:
        """
        Whether this event starts a run for the trigger, given its options.
        Consulted before the rate limit so skipped events never count.
        """

        return True

    def resolve_token(self, path: str, event_payload: Any) -> Optional[str]:
        """
        Resolves a token path (without the `trigger.` prefix) against the
        event payload. Returns None when the path doesn't exist.
        """

        segments = path.split(".")
        aliases = self.get_token_aliases(event_payload)
        value = event_payload
        # The longest alias wins, so `comment.message` beats `comment`.
        for length in range(len(segments), 0, -1):
            alias = ".".join(segments[:length])
            if alias in aliases:
                value = _dig(event_payload, aliases[alias])
                segments = segments[length:]
                break
        value = _dig(value, segments)
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str)
        return str(value)

    def get_opening_prompt(self, trigger: AgentTrigger, event_payload) -> str:
        """
        Renders the system message that starts the triggered conversation.
        """

        headline = self.get_opening_headline(trigger)

        if event_payload is None:
            return headline

        payload_json = json.dumps(event_payload, default=str)
        if len(payload_json) > _EVENT_PAYLOAD_PROMPT_LIMIT:
            payload_json = payload_json[:_EVENT_PAYLOAD_PROMPT_LIMIT] + "… (truncated)"

        return f"{headline}\n\nEvent data:\n```json\n{payload_json}\n```"

    def _is_rate_limited(self, trigger: AgentTrigger) -> bool:
        """
        Protects against run storms (e.g. a bulk import firing a rows-created
        trigger repeatedly). Runs beyond the per-minute limit are dropped.
        """

        limit = settings.AGENT_APPLICATION_TRIGGER_RATE_LIMIT_PER_MINUTE
        cache_key = f"agent_application:trigger:{trigger.id}:rate"
        # `add` only sets the key (and its 60s window) when absent, so the
        # window is aligned to the first run within it.
        count = _count_in_window(cache_key)
        if count > limit:
            logger.warning(
                "Agent trigger {} exceeded the rate limit of {} runs per minute",
                trigger.id,
                limit,
            )
            return True
        return False

    def on_event(
        self,
        services: Iterable[Service],
        event_payload: Optional[Dict | Callable] = None,
        user: Optional[AbstractUser] = None,
    ):
        triggers = list(
            AgentTrigger.objects.filter(
                service__in=services,
                enabled=True,
                application__active=True,
                application__trashed=False,
                application__workspace__trashed=False,
            )
            .using(router.db_for_write(AgentTrigger))
            .select_related("application__workspace")
        )

        service_map = {service.id: service for service in services}
        chat_handler = AgentChatHandler()

        for trigger in triggers:
            service_payload = (
                event_payload(service_map[trigger.service_id])
                if callable(event_payload)
                else event_payload
            )
            if not self.should_run(trigger, service_payload):
                continue
            if self._is_rate_limited(trigger):
                continue

            main_agent = trigger.application.agents.first()
            if main_agent is None:
                continue

            chat = chat_handler.create_triggered_chat(
                main_agent, self.type, cap_event_payload(service_payload)
            )
            message = chat_handler.create_message(
                chat,
                AgentChatMessage.Role.SYSTEM,
                self.get_opening_prompt(trigger, service_payload),
            )
            chat_handler.start_chat_run(chat, message)


class AgentTriggerTypeRegistry(Registry[AgentTriggerType]):
    name = "agent_trigger_type"

    def get_by_service_type(self, service_type: str) -> AgentTriggerType:
        for trigger_type in self.get_all():
            if trigger_type.service_type == service_type:
                return trigger_type
        raise AgentTriggerDoesNotExist(
            f"No agent trigger exists for service type {service_type}."
        )


agent_trigger_type_registry = AgentTriggerTypeRegistry()


def _dig(value: Any, path: list) -> Any:
    for key in path:
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list) and isinstance(key, int) and key < len(value):
            value = value[key]
        elif isinstance(value, list) and isinstance(key, str) and key.isdigit():
            index = int(key)
            value = value[index] if index < len(value) else None
        else:
            return None
        if value is None:
            return None
    return value


_TOKEN_PATTERN = re.compile(r"\{\{\s*trigger\.([^{}]+?)\s*\}\}")


def substitute_trigger_tokens(text: str, trigger_type_str: str, event_payload) -> str:
    """
    Replaces `{{trigger.…}}` tokens in the instructions with values of the
    event that started the conversation. Unknown tokens are left untouched so
    the model still sees what was meant.
    """

    if not text or "{{" not in text:
        return text
    try:
        trigger_type = agent_trigger_type_registry.get(trigger_type_str)
    except agent_trigger_type_registry.does_not_exist_exception_class:
        return text
    if event_payload is None:
        return text

    def replace(match):
        resolved = trigger_type.resolve_token(match.group(1).strip(), event_payload)
        return match.group(0) if resolved is None else resolved

    return _TOKEN_PATTERN.sub(replace, text)
