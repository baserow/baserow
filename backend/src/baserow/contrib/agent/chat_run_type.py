from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS

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

from .api.serializers import AgentMessageSerializer
from .constants import AGENT_NOT_ALLOWED, AGENT_NOT_READY, AGENT_RUN_TYPE
from .exceptions import AgentConversationDoesNotExist, AgentNotReady
from .handler import AgentHandler
from .replies import AgentResponder, create_reply_model
from .service import AgentService
from .signals import agent_conversation_updated
from .types import AgentReplyRequest, AgentReplyResult

if TYPE_CHECKING:
    from baserow.core.chat_runs.journal import ChatRunJournal


class AgentChatRunType(ChatRunType):
    """An Agent's reply to one message in a private conversation."""

    type = AGENT_RUN_TYPE

    def get_max_active_runs_per_user(self) -> int | None:
        """No per-user limit: the workspace limit bounds the replies of all members."""

        return None

    def get_max_active_runs_per_workspace(self, workspace: Workspace) -> int | None:
        """A plugin can replace this run type to set the limit per plan."""

        return settings.BASEROW_AGENT_MAX_ACTIVE_RUNS_PER_WORKSPACE

    def can_read(self, user: AbstractUser, run: ChatRun) -> bool:
        """Only the owner, while they may still read the Agent's conversations."""

        return AgentService().can_read_conversation(user, run.chat_id)

    def can_cancel(self, user: AbstractUser, run: ChatRun) -> bool:
        return self.can_read(user, run)

    def can_follow_chat(self, user: AbstractUser, chat_id: int) -> bool:
        """One query, as it runs on the websocket's shared thread."""

        # A replica can lag behind the conversation that this tab's send just created.
        return (
            AgentHandler()
            .get_accessible_conversations(user)
            .using(DEFAULT_DB_ALIAS)
            .filter(id=chat_id)
            .exists()
        )

    async def execute(self, run: ChatRun, journal: "ChatRunJournal") -> ChatRunOutcome:
        """Check access and configuration again: both can change while the run waits."""

        try:
            request, model, model_settings = await sync_to_async(self._prepare)(run)
        except AgentConversationDoesNotExist:
            return ChatRunOutcome(ChatRunStatus.FAILED, ChatRunErrorCode.FAILED)
        except AgentNotReady:
            return ChatRunOutcome(ChatRunStatus.FAILED, AGENT_NOT_READY)
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
            agent_conversation_updated.send(self, conversation=conversation, user=None)

    def _finish_reply(
        self,
        run: ChatRun,
        status: str,
        error_code: str,
        result: AgentReplyResult | None,
    ) -> dict | None:
        """
        Save how the reply ended and tell all the owner's sessions.

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
        agent_conversation_updated.send(
            self, conversation=reply.conversation, user=None
        )
        return dict(AgentMessageSerializer(reply).data)
