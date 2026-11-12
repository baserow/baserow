from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser

from asgiref.sync import sync_to_async
from pydantic_ai.models import Model

from baserow.core.chat_runs.constants import ChatRunErrorCode
from baserow.core.chat_runs.models import ChatRun, ChatRunStatus
from baserow.core.chat_runs.registries import ChatRunType
from baserow.core.chat_runs.steps import stop_running_steps
from baserow.core.chat_runs.stream import fold_output
from baserow.core.chat_runs.types import ChatRunOutcome
from baserow.core.exceptions import PermissionException
from baserow.core.models import Workspace
from baserow.core.signals import application_pending_count_updated

from .api.serializers import AgentMessageSerializer
from .constants import (
    AGENT_NOT_ALLOWED,
    AGENT_NOT_READY,
    AGENT_RUN_TYPE,
    AGENT_TRIGGER_OFF,
)
from .exceptions import AgentConversationDoesNotExist, AgentNotReady, AgentTriggerOff
from .handler import AgentHandler
from .models import AgentReplyStatus
from .replies import AgentResponder, create_reply_model
from .service import AgentService
from .signals import agent_conversation_activity
from .types import AgentReplyRequest, AgentReplyResult

if TYPE_CHECKING:
    from baserow.core.chat_runs.journal import ChatRunJournal


class AgentChatRunType(ChatRunType):
    """An Agent's reply to one message in a conversation."""

    type = AGENT_RUN_TYPE

    def get_max_active_runs_per_user(self) -> int | None:
        """No per-user limit: operators can bound replies at the workspace level."""

        return None

    def get_max_active_runs_per_workspace(self, workspace: Workspace) -> int | None:
        """A plugin can replace this run type to set the limit per plan."""

        return settings.BASEROW_AGENT_MAX_ACTIVE_RUNS_PER_WORKSPACE

    def can_read(self, user: AbstractUser, run: ChatRun) -> bool:
        """
        :param user: The user asking.
        :param run: The run writing a reply in a conversation.
        :return: Whether the user may read it: the owner, or any reader of the
            Agent's conversations for a shared one.
        """

        return AgentService().can_read_conversation(user, run.chat_id)

    def can_cancel(self, user: AbstractUser, run: ChatRun) -> bool:
        """
        :param user: The user asking.
        :param run: The run writing a reply in a conversation.
        :return: Whether the user may stop it: the owner, or for a shared
            conversation a reader who may also update the Agent.
        """

        return AgentService().can_cancel_conversation_run(user, run.chat_id)

    def can_follow_chat(self, user: AbstractUser, chat_id: int) -> bool:
        """
        :param user: The user following the conversation.
        :param chat_id: The id of the conversation.
        :return: Whether the user may follow its runs.
        """

        return AgentService().can_follow_conversation(user, chat_id)

    async def execute(self, run: ChatRun, journal: "ChatRunJournal") -> ChatRunOutcome:
        """Check access and configuration again: both can change while the run waits."""

        try:
            request, model, model_settings = await sync_to_async(self._prepare)(run)
        except AgentConversationDoesNotExist:
            return ChatRunOutcome(ChatRunStatus.FAILED, ChatRunErrorCode.FAILED)
        except AgentNotReady:
            return ChatRunOutcome(ChatRunStatus.FAILED, AGENT_NOT_READY)
        except AgentTriggerOff:
            return ChatRunOutcome(ChatRunStatus.FAILED, AGENT_TRIGGER_OFF)
        except PermissionException:
            return ChatRunOutcome(ChatRunStatus.FAILED, AGENT_NOT_ALLOWED)
        return await AgentResponder(request, journal, model, model_settings).answer()

    def _prepare(self, run: ChatRun) -> tuple[AgentReplyRequest, Model, dict]:
        request = AgentService().prepare_reply(run.context["reply_id"])
        return (request, *create_reply_model(request))

    def persist_outcome(self, run: ChatRun, outcome: ChatRunOutcome) -> dict | None:
        return self._finish_reply(
            run, outcome.status, outcome.error_code, outcome.result
        )

    def on_run_lost(
        self, run: ChatRun, events: list[dict[str, Any]] | None = None
    ) -> dict | None:
        """Keep the text and activity the user already saw."""

        output = fold_output(events or [])
        return self._finish_reply(
            run,
            run.status,
            run.error_code,
            AgentReplyResult(
                text=output["text"], steps=stop_running_steps(output["steps"]) or None
            ),
        )

    def on_run_not_started(self, run: ChatRun) -> dict | None:
        return self._finish_reply(run, run.status, run.error_code, None)

    def ensure_interruption_warning(self, run: ChatRun) -> None:
        """Mark the reply interrupted unless it already ended: it may run twice."""

        conversation = AgentHandler().mark_reply_interrupted(run.context["reply_id"])
        if conversation is not None:
            agent_conversation_activity.send(self, conversation=conversation, user=None)

    def _finish_reply(
        self,
        run: ChatRun,
        status: str,
        error_code: str,
        result: AgentReplyResult | None,
    ) -> dict | None:
        """
        Save how the reply ended and tell every session that sees the conversation,
        with the pending counts of those who may decide when the reply now waits for
        approvals.

        :param run: The run that wrote the reply.
        :param status: The final status.
        :param error_code: Why the reply failed, or an empty string.
        :param result: What the reply produced, or None when it never started.
        :return: The saved reply as the messages list shows it, so followers don't
            read it again, or None when the reply no longer exists.
        """

        reply = AgentHandler().finish_reply(
            run.context["reply_id"], status, error_code, result
        )
        if reply is None:
            return None
        conversation = reply.conversation
        agent_conversation_activity.send(self, conversation=conversation, user=None)
        if reply.status == AgentReplyStatus.WAITING:
            application_pending_count_updated.send(
                self,
                application=conversation.agent,
                user_ids=conversation.pending_count_user_ids,
            )
        return dict(AgentMessageSerializer(reply).data)
