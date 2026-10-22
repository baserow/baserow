from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS

from asgiref.sync import sync_to_async
from pydantic_ai.models import Model

from baserow.core.chat_runs.constants import ChatRunErrorCode
from baserow.core.chat_runs.models import ChatRun, ChatRunStatus
from baserow.core.chat_runs.registries import ChatRunType
from baserow.core.chat_runs.stream import fold_output
from baserow.core.chat_runs.types import ChatRunOutcome
from baserow.core.exceptions import PermissionException

from .constants import AGENT_NOT_ALLOWED, AGENT_NOT_READY, AGENT_RUN_TYPE
from .exceptions import AgentConversationDoesNotExist, AgentNotReady
from .handler import AgentHandler
from .replies import AgentResponder, create_reply_model
from .types import AgentReply, AgentReplyRequest

if TYPE_CHECKING:
    from baserow.core.chat_runs.journal import ChatRunJournal


class AgentChatRunType(ChatRunType):
    """An Agent's reply to one message in a private conversation."""

    type = AGENT_RUN_TYPE

    def get_max_active_runs_per_user(self) -> int | None:
        """No per-user limit: the workspace limit bounds the replies of all members."""

        return None

    def get_max_active_runs_per_workspace(self) -> int | None:
        return settings.BASEROW_AGENT_MAX_ACTIVE_RUNS_PER_WORKSPACE

    def can_read(self, user: AbstractUser, run: ChatRun) -> bool:
        """Only the owner, while they may still read the Agent's conversations."""

        return AgentHandler().can_read_conversation(user, run.chat_id)

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
        request = AgentHandler().prepare_reply(run)
        return (request, *create_reply_model(request))

    def persist_outcome(self, run: ChatRun, outcome: ChatRunOutcome) -> dict | None:
        return AgentHandler().finish_turn(
            run.context["turn_id"], outcome.status, outcome.error_code, outcome.result
        )

    def on_run_lost(
        self, run: ChatRun, events: list[dict[str, Any]] | None = None
    ) -> dict | None:
        """Keep the text the user already saw."""

        text = fold_output(events)["text"] if events else ""
        return AgentHandler().finish_turn(
            run.context["turn_id"], run.status, run.error_code, AgentReply(text=text)
        )

    def on_run_not_started(self, run: ChatRun) -> dict | None:
        return AgentHandler().finish_turn(
            run.context["turn_id"], run.status, run.error_code, None
        )

    def ensure_interruption_warning(self, run: ChatRun) -> None:
        """Mark the turn interrupted unless it already ended: it may run twice."""

        AgentHandler().mark_turn_interrupted(run.context["turn_id"])
