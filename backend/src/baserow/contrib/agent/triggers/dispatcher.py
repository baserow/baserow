from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timedelta
from functools import partial
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger

from baserow.core.exceptions import SubjectTypeNotExist
from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.registries import subject_type_registry
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.types import Subject
from baserow.core.utils import exception_capturer, rate_limit_window_exceeded

from ..constants import AGENT_TRIGGER_MESSAGE_FAILED, AgentReadinessState
from ..handler import AgentHandler
from ..models import AgentApplication, AgentConversation, AgentMessage, AgentTrigger
from ..signals import agent_conversation_activity
from .handler import AgentTriggerHandler
from .overlap import get_overlap_limits
from .tasks import start_trigger_conversation


class AgentTriggerDispatcher:
    """Starts, queues or skips a shared conversation for each trigger that fires."""

    def on_event(
        self,
        services: Iterable[Service],
        event_payload: dict | Callable | None = None,
        user: Subject | None = None,
        isolate_failures: bool = False,
    ) -> list:
        """
        Fire every trigger of the given services: resolve the message of each
        enabled one now, and apply its rules once the event commits. Every matched
        trigger gets its payload first, so a schedule keeps advancing while its
        trigger is disabled, its agent can't run or a rule skips it. A trigger that
        fails is logged and skipped whatever ``isolate_failures`` says: an agent
        bug must never fail the event's other listeners.

        :param services: The services the event applies to.
        :param event_payload: The payload, or a callable returning it per service.
        :param user: The user or identity who caused the event, never stored.
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
            if (
                trigger.enabled
                and self._agent_is_live(trigger.agent)
                and not self._is_self_event(trigger, user)
            ):
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

    def _is_self_event(self, trigger: AgentTrigger, user: Subject | None) -> bool:
        """
        Whether the agent's own run identity caused the event, so an agent never
        triggers itself in a loop. Not a limit, so nothing is recorded.

        :param trigger: The matched trigger, with its agent.
        :param user: The user or identity who caused the event, or None.
        :return: True when the event comes from the agent's run identity.
        """

        agent = trigger.agent
        if user is None or agent.run_as_subject_id is None:
            return False
        try:
            subject_type = subject_type_registry.get_by_model(user).type
        except SubjectTypeNotExist:
            return False
        caused_by = (subject_type, user.pk)
        if caused_by != (agent.run_as_subject_type, agent.run_as_subject_id):
            return False
        logger.debug(
            "Agent trigger {} skipped: its agent caused the event.", trigger.id
        )
        return True

    def _queue_start(
        self, trigger: AgentTrigger, payload: dict, fired_at: datetime
    ) -> None:
        """
        Resolve the trigger's message while its payload is at hand, and apply the
        trigger's rules in their own transaction after the event's one commits, so
        the workspace run lock isn't held for the rest of a beat tick. A message
        that can't be resolved opens with the payload and fails its reply.

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
        Apply the rules of a trigger that fired, if it still can run: start or
        queue its conversation and tell the readers, or record why the firing was
        skipped. A failure is logged and reported, never raised.

        :param trigger_id: The id of the trigger that fired.
        :param content: The resolved message opening the conversation.
        :param failure: The error code failing the reply instead of running it, or
            None.
        """

        try:
            with transaction.atomic():
                trigger = self._lock(trigger_id)
                if trigger is None or not self._is_runnable(trigger):
                    return
                # Read under the lock, so saved times follow the order rules ran in.
                now = timezone.now()
                reason = self._rate_limit_reason(trigger, now)
                if reason is None:
                    reason = self._open_conversation(trigger, content, failure, now)
                if reason is not None:
                    AgentTriggerHandler().record_skip(trigger, reason, now)
                    logger.debug("Agent trigger {} skipped: {}.", trigger.id, reason)
        except Exception as e:
            logger.exception("Could not start agent trigger {}.", trigger_id)
            exception_capturer(e)

    def _lock(self, trigger_id: int) -> AgentTrigger | None:
        """
        Lock the Agent, then its trigger, while a firing's rules apply. This
        matches builder saves and serializes firings across the Agent's triggers.
        Re-read the trigger under its lock so a switch-off is never missed.

        :param trigger_id: The id of the trigger.
        :return: The trigger with its agent, workspace and service, or None when it
            was trashed or deleted since it fired.
        """

        # A builder locks the Agent before the trigger. Taking that lock first
        # avoids waiting for the Agent's FK check while holding the trigger.
        # No key: a concurrent private conversation may hold the workspace run
        # lock and must still be able to commit its foreign key to this Agent.
        agent = (
            AgentApplication.objects.filter(triggers__id=trigger_id)
            .select_for_update(of=("self",), no_key=True)
            .only("pk")
            .first()
        )
        if agent is None:
            return None
        # No key: a transaction only referencing the trigger never holds it back.
        trigger = (
            AgentTrigger.objects.select_for_update(of=("self",), no_key=True)
            .select_related("agent__workspace", "service")
            .filter(id=trigger_id)
            .first()
        )
        if trigger is None:
            logger.debug("Agent trigger {} skipped: it was trashed.", trigger_id)
        return trigger

    def _rate_limit_reason(
        self, trigger: AgentTrigger, now: datetime
    ) -> AgentTrigger.SkipReason | None:
        """
        Check the trigger's own limits, then its agent's limits across all of the
        agent's triggers, on the conversations they started.

        :param trigger: The trigger that fired, with its agent.
        :param now: The moment the rules apply.
        :return: The reason of the limit reached, or None when both allow it.
        """

        handler = AgentTriggerHandler()
        if self._limit_reached(
            settings.AGENT_TRIGGER_RATE_LIMITS,
            partial(handler.recent_conversation_times, trigger),
            now,
        ):
            return AgentTrigger.SkipReason.RATE_LIMITED
        if self._limit_reached(
            settings.AGENT_TRIGGER_AGENT_RATE_LIMITS,
            partial(handler.recent_agent_conversation_times, trigger.agent),
            now,
        ):
            return AgentTrigger.SkipReason.AGENT_RATE_LIMITED
        return None

    def _limit_reached(
        self,
        limits: Sequence[tuple[int, int]],
        recent_times: Callable[[datetime], list[datetime]],
        now: datetime,
    ) -> bool:
        """
        Read the counted conversations of the largest window once and check every
        pair against them.

        :param limits: The ``(max_runs, window_seconds)`` pairs; empty means none.
        :param recent_times: Returns the creation times of the counted
            conversations since a moment.
        :param now: The moment every window ends.
        :return: Whether any pair is reached.
        """

        if not limits:
            return False
        since = now - timedelta(seconds=max(window for _, window in limits))
        return rate_limit_window_exceeded(recent_times(since), limits, now) is not None

    def _open_conversation(
        self,
        trigger: AgentTrigger,
        content: str,
        failure: str | None,
        now: datetime,
    ) -> AgentTrigger.SkipReason | None:
        """
        Apply the trigger's overlap rule (see ``OverlapLimits``): start the
        conversation while fewer of its replies are going than the rule allows
        and nothing is queued ahead, queue it while the queue has room, or skip.
        Queued replies a lost hand-off left behind start first, so a firing never
        queues behind a queue that doesn't move. The workspace's run limit queues
        a firing where the rule queues, and fails it, visibly, where it doesn't.
        A failed message fails its reply at once, never queued.

        :param trigger: The trigger that fired, with its agent.
        :param content: The resolved message opening the conversation.
        :param failure: The error code failing the reply instead of running it, or
            None.
        :param now: The moment the rules apply.
        :return: Why the firing was skipped, or None when its conversation exists.
        """

        trigger_handler = AgentTriggerHandler()
        limits = get_overlap_limits(trigger.on_overlap)
        self.start_queued_replies(trigger)
        going = trigger_handler.count_going_replies(trigger)
        queued = trigger_handler.count_queued_replies(trigger)
        queues = limits.max_queued != 0
        if limits.has_room_to_go(going) and not (queues and queued):
            created = AgentHandler().start_trigger_conversation(
                trigger, content, failure, queue_on_run_limit=queues
            )
        elif not queues:
            return AgentTrigger.SkipReason.PREVIOUS_RUNNING
        elif not limits.has_room_to_queue(queued):
            return AgentTrigger.SkipReason.QUEUE_FULL
        else:
            created = AgentHandler().start_trigger_conversation(
                trigger, content, failure, start_run=False
            )
        trigger_handler.record_fired(trigger, now)
        self._notify(created.conversation, created.run_id)
        return None

    def start_queued_replies(self, trigger: AgentTrigger) -> list[AgentMessage]:
        """
        Start the trigger's queued replies its overlap rule has room for, and tell
        their readers. Called when a trigger's reply ends, by the sweep and by a
        firing; it never raises, so one trigger can't stop the others.

        :param trigger: The trigger whose queue moves on.
        :return: The replies now running, even when their readers couldn't be
            told; none when nothing is queued, the rule has no room, the trigger
            is locked by another caller or stopped, the workspace is at its run
            limit, or the start failed.
        """

        replies = []
        try:
            replies = AgentHandler().start_queued_replies(trigger)
            for reply in replies:
                runs = AgentHandler().get_active_reply_runs(reply.conversation)
                self._notify(reply.conversation, runs.get(reply.id))
        except SoftTimeLimitExceeded:
            raise
        except Exception as e:
            logger.exception(
                "Could not start queued replies of agent trigger {}.", trigger.id
            )
            exception_capturer(e)
        return replies

    def _notify(self, conversation: AgentConversation, run_id: UUID | None) -> None:
        """
        Tell the readers of a trigger conversation about it and its run.

        :param conversation: The conversation just created, or whose reply started.
        :param run_id: The run writing its reply, or None when the reply is queued
            or failed.
        """

        agent_conversation_activity.send(
            self, conversation=conversation, user=None, run_id=run_id
        )


agent_trigger_dispatcher = AgentTriggerDispatcher()
