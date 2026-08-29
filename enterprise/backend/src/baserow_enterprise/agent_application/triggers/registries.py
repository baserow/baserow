import json
from typing import Callable, Dict, Iterable, Optional

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
        cache.add(cache_key, 0, timeout=60)
        count = cache.incr(cache_key)
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
            if self._is_rate_limited(trigger):
                continue

            main_agent = trigger.application.agents.first()
            if main_agent is None:
                continue

            service_payload = (
                event_payload(service_map[trigger.service_id])
                if callable(event_payload)
                else event_payload
            )

            chat = chat_handler.create_triggered_chat(
                main_agent, self.type, service_payload
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
