from collections.abc import Callable, Iterable
from datetime import datetime

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils import timezone

from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger

from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.utils import exception_capturer

from ..constants import AGENT_TRIGGER_MESSAGE_FAILED, AgentReadinessState
from ..handler import AgentHandler
from ..models import AgentApplication, AgentTrigger
from ..signals import agent_conversation_activity
from .handler import AgentTriggerHandler
from .tasks import start_trigger_conversation


class AgentTriggerDispatcher:
    """Starts a shared conversation for every agent trigger an event applies to."""

    def on_event(
        self,
        services: Iterable[Service],
        event_payload: dict | Callable | None = None,
        user: AbstractUser | None = None,
        isolate_failures: bool = False,
    ) -> list:
        """
        Start one conversation per runnable trigger of the given services. Every
        matched trigger gets its payload first, so a schedule keeps advancing while
        its trigger is disabled or its agent can't run. A trigger that fails to
        start is logged and skipped whatever ``isolate_failures`` says: an agent
        bug must never fail the event's other listeners.

        :param services: The services the event applies to.
        :param event_payload: The payload, or a callable returning it per service.
        :param user: The user who caused the event, never stored.
        :param isolate_failures: Ignored, failures are always isolated.
        :return: An empty list, so listeners that return histories stay first.
        """

        fired_at = timezone.now()
        try:
            with transaction.atomic():
                triggers, payloads = self._match(services, event_payload)
        except SoftTimeLimitExceeded:
            raise
        except Exception as e:
            logger.exception("Could not match agent triggers.")
            exception_capturer(e)
            return []
        if not feature_flag_is_enabled(FF_AGENT_BUILDER):
            logger.debug("Agent triggers skipped: the agent builder is off.")
            return []
        for trigger in triggers:
            if trigger.enabled and self._agent_is_live(trigger.agent):
                self._queue_start(trigger, payloads[trigger.id] or {}, fired_at)
        return []

    @staticmethod
    def _agent_is_live(agent: AgentApplication) -> bool:
        """
        :param agent: The agent, with its workspace.
        :return: Whether the agent and its workspace exist outside the trash and
            outside a snapshot.
        """

        workspace = agent.workspace
        return not agent.trashed and workspace is not None and not workspace.trashed

    def _match(
        self, services: Iterable[Service], event_payload: dict | Callable | None
    ) -> tuple[list[AgentTrigger], dict[int, dict | None]]:
        """
        Find the triggers of the given services and resolve the payload of each.

        :param services: The services the event applies to.
        :param event_payload: The payload, or a callable returning it per service.
        :return: The matched triggers, and their payloads by trigger id.
        """

        services_by_id = {service.id: service for service in services}
        triggers = list(
            AgentTrigger.objects.filter(
                service_id__in=list(services_by_id)
            ).select_related("agent__workspace")
        )
        for trigger in triggers:
            trigger.service = services_by_id[trigger.service_id]
        # The callable gets the instances it handed over, which it then saves.
        payloads = {
            trigger.id: (
                event_payload(services_by_id[trigger.service_id])
                if callable(event_payload)
                else event_payload
            )
            for trigger in triggers
        }
        return triggers, payloads

    def _is_runnable(self, trigger: AgentTrigger) -> bool:
        """
        Whether the trigger may start a conversation now, logging why not.

        :param trigger: The matched trigger, with its agent and workspace.
        :return: True when the trigger is enabled and its agent can reply.
        """

        agent = trigger.agent
        service_type = service_type_registry.get_by_model(
            trigger.service.specific_class
        )
        if not trigger.enabled:
            reason = "it is disabled"
        elif not self._agent_is_live(agent):
            reason = "its agent is trashed or is a snapshot"
        elif service_type.type not in AgentTriggerHandler().available_trigger_types(
            agent
        ):
            reason = "its type isn't available"
        elif (
            AgentHandler().get_configuration_readiness(agent)[0]
            != AgentReadinessState.READY
        ):
            reason = "its agent isn't ready"
        else:
            return True
        logger.debug("Agent trigger {} skipped: {}.", trigger.id, reason)
        return False

    def _queue_start(
        self, trigger: AgentTrigger, payload: dict, fired_at: datetime
    ) -> None:
        """
        Resolve the trigger's message while its payload is at hand, and start its
        conversation in its own transaction after the event's one commits, so the
        workspace run lock isn't held for the rest of a beat tick. A message that
        can't be resolved opens with the payload and fails its reply.

        :param trigger: The enabled trigger that fired.
        :param payload: The event payload the message formula reads.
        :param fired_at: When the event was handled, shared by all its triggers.
        """

        failure = None
        try:
            content = AgentTriggerHandler().resolve_message(trigger, payload, fired_at)
        except SoftTimeLimitExceeded:
            raise
        except Exception as e:
            # A user's formula, not a bug: log it without reporting it.
            logger.warning(
                "Agent trigger {} message failed ({}).", trigger.id, type(e).__name__
            )
            content = AgentTriggerHandler().payload_as_message(payload)
            failure = AGENT_TRIGGER_MESSAGE_FAILED
        # A broker error for one trigger mustn't drop the starts queued after it.
        transaction.on_commit(
            lambda: start_trigger_conversation.delay(trigger.id, content, failure),
            robust=True,
        )

    def start(self, trigger_id: int, content: str, failure: str | None) -> None:
        """
        Start the conversation of a trigger that fired, if it still can run, and
        tell the readers. A failure is logged and reported, never raised.

        :param trigger_id: The id of the trigger that fired.
        :param content: The resolved message opening the conversation.
        :param failure: The error code failing the reply instead of running it, or
            None.
        """

        try:
            with transaction.atomic():
                trigger = (
                    AgentTrigger.objects.filter(id=trigger_id)
                    .select_related("agent__workspace", "service")
                    .first()
                )
                if trigger is None or not self._is_runnable(trigger):
                    return
                created = AgentHandler().start_trigger_conversation(
                    trigger, content, failure
                )
                agent_conversation_activity.send(
                    self,
                    conversation=created.conversation,
                    user=None,
                    run_id=created.run_id,
                )
        except Exception as e:
            logger.exception("Could not start agent trigger {}.", trigger_id)
            exception_capturer(e)


agent_trigger_dispatcher = AgentTriggerDispatcher()
