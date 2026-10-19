from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS, transaction
from django.utils import translation

from asgiref.sync import sync_to_async
from loguru import logger

from baserow.api.sessions import (
    set_client_undo_redo_action_group_id,
    set_untrusted_client_session_id,
)
from baserow.core.chat_runs.constants import ChatRunErrorCode
from baserow.core.chat_runs.models import ChatRun, ChatRunStatus
from baserow.core.chat_runs.registries import ChatRunType
from baserow.core.chat_runs.types import ChatRunOutcome
from baserow.core.handler import CoreHandler

from .assistant import BackgroundAssistant, assistant_message_payload
from .exceptions import AssistantModelNotSupportedError
from .history import NOT_STARTED_ANSWER, append_turn, unfinished_answer
from .model_profiles import (
    ResolvedAssistantModelProfile,
    check_lm_ready_or_raise,
    resolve_assistant_model,
)
from .models import AssistantChat, AssistantChatMessage, AssistantChatPrediction
from .operations import ChatAssistantChatOperationType
from .runs import ASSISTANT_RUN_TYPE, ERROR_MODEL_UNAVAILABLE, AssistantRunResult
from .telemetry import AssistantTraceOutcome, PosthogTracingCallback
from .types import UIContext

if TYPE_CHECKING:
    from baserow.core.chat_runs.journal import ChatRunJournal


def trace_outcome_for(status: str, error_code: str) -> AssistantTraceOutcome:
    """
    Maps how a run ended to the outcome of its `$ai_trace`, so Kuma's outcome
    rates stay comparable with streamed messages.

    :param status: The run's final status.
    :param error_code: Why the run failed or stopped, if it did.
    :return: The trace outcome.
    """

    if error_code in (ChatRunErrorCode.INTERRUPTED, ChatRunErrorCode.TIMEOUT):
        return AssistantTraceOutcome.INTERRUPTED
    if error_code == ChatRunErrorCode.NOT_STARTED:
        return AssistantTraceOutcome.NOT_STARTED
    if error_code:
        return AssistantTraceOutcome.ERROR
    if status == ChatRunStatus.CANCELLED:
        return AssistantTraceOutcome.CANCELLED
    return AssistantTraceOutcome.ANSWERED


@dataclass(frozen=True)
class RestoredRun:
    """What a run answers, with the sending request's context restored."""

    chat: AssistantChat
    human_message: AssistantChatMessage
    ui_context: Optional[UIContext]
    model_profile: ResolvedAssistantModelProfile


class AssistantChatRunType(ChatRunType):
    """
    Kuma's messages, answered in the background. The send endpoint saves the
    human message; a run saves nothing until it ends, when one of these hooks
    saves the AI message, its prediction and the chat's history.
    """

    type = ASSISTANT_RUN_TYPE

    def can_read(self, user: AbstractUser, run: ChatRun) -> bool:
        """
        Only the chat's owner reads a run's events or stops it, while they can use
        Kuma in the workspace.

        :param user: The user asking.
        :param run: The run.
        :return: True when allowed.
        """

        if not AssistantChat.objects.filter(id=run.chat_id, user_id=user.id).exists():
            return False
        return CoreHandler().check_permissions(
            user,
            ChatAssistantChatOperationType.type,
            workspace=run.workspace,
            context=run.workspace,
            raise_permission_exceptions=False,
        )

    def can_cancel(self, user: AbstractUser, run: ChatRun) -> bool:
        """Stopping Kuma requires ownership and current access to its workspace."""

        return self.can_read(user, run)

    def can_follow_chat(self, user: AbstractUser, chat_id: int) -> bool:
        """
        One indexed query, as it runs on the websocket's shared thread: the user
        owns the chat and is still a member of its workspace.

        :param user: The user subscribing, possibly anonymous.
        :param chat_id: The id of the chat.
        :return: True when allowed.
        """

        if not user.is_authenticated:
            return False
        # A replica can lag behind the chat that this tab's send just created.
        return (
            AssistantChat.objects.using(DEFAULT_DB_ALIAS)
            .filter(
                id=chat_id,
                user_id=user.id,
                workspace__trashed=False,
                workspace__workspaceuser__user_id=user.id,
            )
            .exists()
        )

    async def execute(self, run: ChatRun, journal: "ChatRunJournal") -> ChatRunOutcome:
        """
        Restores the sending request's context and answers the message while
        reporting to the journal. Nothing is saved here: `persist_outcome` saves
        the outcome when the run ends.

        :param run: The claimed run.
        :param journal: The run's journal.
        :return: How the run ended.
        """

        try:
            restored = await sync_to_async(self._restore)(run)
        except AssistantModelNotSupportedError:
            logger.warning("Kuma's model can't be used for chat run {}", run.id)
            return ChatRunOutcome(
                status=ChatRunStatus.FAILED, error_code=ERROR_MODEL_UNAVAILABLE
            )

        with translation.override(restored.chat.user.profile.language):
            assistant = await sync_to_async(BackgroundAssistant)(
                restored.chat,
                restored.model_profile,
                journal,
                run.context.get("origin_tab_id", ""),
            )
            return await assistant.answer(
                restored.human_message.content,
                restored.ui_context,
                run.context.get("generate_title", False),
            )

    def _restore(self, run: ChatRun) -> RestoredRun:
        """
        Loads what the run answers and puts the sending request's context back on
        the chat's user, so tools act as they would have during the request.

        :param run: The claimed run.
        :return: The chat, the message, the UI context and a ready model profile.
        """

        self._repair_interrupted_turns(run)
        chat = AssistantChat.objects.select_related("workspace", "user__profile").get(
            id=run.chat_id
        )
        human_message = chat.messages.get(id=run.context["human_message_id"])
        ui_context_data = run.context.get("ui_context")
        ui_context = (
            UIContext.model_validate(ui_context_data) if ui_context_data else None
        )

        user = chat.user
        if session_id := run.context.get("client_session_id"):
            set_untrusted_client_session_id(user, session_id)
        set_client_undo_redo_action_group_id(user, run.context.get("action_group_id"))
        # Without a websocket id, the sending tab also gets the realtime events.
        user.web_socket_id = None
        if ui_context is not None:
            user.profile.timezone = ui_context.timezone

        model_profile = resolve_assistant_model(workspace=chat.workspace)
        check_lm_ready_or_raise(model_profile=model_profile)
        return RestoredRun(
            chat=chat,
            human_message=human_message,
            ui_context=ui_context,
            model_profile=model_profile,
        )

    def persist_outcome(self, run: ChatRun, outcome: ChatRunOutcome) -> dict[str, Any]:
        """
        Saves the final answer and model history. An absent result does not prove
        that execution made no changes.

        :param run: The run.
        :param outcome: How the run ended, with an `AssistantRunResult` if any.
        :return: The saved AI message.
        """

        chat, human_message = self._load_turn(run)
        result = outcome.result or AssistantRunResult(
            text="",
            message_history=append_turn(
                chat.message_history,
                human_message.content,
                (unfinished_answer("") if run.started_on else NOT_STARTED_ANSWER),
            ),
        )
        return self._save_answer(
            run, chat, human_message, result, outcome.status, outcome.error_code
        )

    def serialize_outcome(self, run: ChatRun) -> dict[str, Any] | None:
        """Recover the associated answer with its current rating and chat title.

        The durable payload identifies the saved message even after another turn
        finishes. Feedback and titles remain product state and can change later.
        """

        if run.outcome is None:
            return None
        message_id = run.outcome.get("id")
        message = None
        if isinstance(message_id, int) and not isinstance(message_id, bool):
            message = (
                AssistantChatMessage.objects.using(DEFAULT_DB_ALIAS)
                .select_related("prediction", "chat")
                .filter(
                    id=message_id,
                    chat_id=run.chat_id,
                    role=AssistantChatMessage.Role.AI,
                )
                .first()
            )
        if message is not None:
            return {
                **assistant_message_payload(message),
                "chat_title": message.chat.title,
            }
        # A product message can have been removed; the terminal run still keeps
        # the original result. Never substitute a later conversation message.
        title = (
            AssistantChat.objects.using(DEFAULT_DB_ALIAS)
            .filter(id=run.chat_id)
            .values_list("title", flat=True)
            .first()
        )
        return {**run.outcome, **({"chat_title": title} if title is not None else {})}

    def on_run_lost(
        self, run: ChatRun, events: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Save only a complete, retained Redis reconstruction, never a tail."""

        chat, human_message = self._load_turn(run)
        text = ""
        segment = None
        for event in events or []:
            kind = event.get("kind")
            data = event.get("data") or {}
            if kind == "run.baseline":
                text, segment = data.get("text", ""), data.get("segment")
            elif kind == "text.delta":
                if data.get("segment") != segment:
                    text, segment = "", data.get("segment")
                text += data.get("text", "")
        history = append_turn(
            chat.message_history, human_message.content, unfinished_answer(text)
        )
        return self._save_answer(
            run,
            chat,
            human_message,
            AssistantRunResult(text=text, message_history=history),
            run.status,
            run.error_code,
        )

    def ensure_interruption_warning(self, run: ChatRun) -> None:
        """Keep a failed persistence warning after generic run metadata is pruned.

        The marker lives on the original prompt. It makes repair idempotent even
        when the normal prediction/outcome hook failed after tools ran.
        """

        if run.started_on is None or run.outcome is not None:
            return
        with transaction.atomic():
            chat = (
                AssistantChat.objects.select_for_update().filter(id=run.chat_id).first()
            )
            if chat is None:
                return
            human = (
                chat.messages.select_for_update()
                .filter(id=run.context.get("human_message_id"))
                .first()
            )
            if human is None or human.artifacts.get("run_warning"):
                return
            # A successfully persisted incomplete outcome already closed its turn.
            if not AssistantChatPrediction.objects.filter(human_message=human).exists():
                chat.message_history = append_turn(
                    chat.message_history, human.content, unfinished_answer("")
                )
                chat.save(update_fields=["message_history", "updated_on"])
            human.artifacts = {
                **human.artifacts,
                "run_warning": {"run_id": str(run.id), "error_code": run.error_code},
            }
            human.save(update_fields=["artifacts", "updated_on"])

    def _repair_interrupted_turns(self, run: ChatRun) -> None:
        """Repair missing prior turns before a new model reads the conversation."""

        for previous in ChatRun.objects.filter(
            run_type=self.type,
            chat_id=run.chat_id,
            started_on__isnull=False,
            outcome__isnull=True,
            status__in=[ChatRunStatus.FAILED, ChatRunStatus.CANCELLED],
        ).order_by("created_on", "id"):
            self.ensure_interruption_warning(previous)

    def on_run_not_started(self, run: ChatRun) -> dict[str, Any]:
        """
        Saves an empty answer, and records in the history that nothing was done,
        for a message no worker picked up or that the user stopped while it
        waited.

        :param run: The run, failed with `not_started` or cancelled.
        :return: The saved AI message.
        """

        chat, human_message = self._load_turn(run)
        history = append_turn(
            chat.message_history, human_message.content, NOT_STARTED_ANSWER
        )
        result = AssistantRunResult(text="", message_history=history)
        return self._save_answer(
            run, chat, human_message, result, run.status, run.error_code
        )

    def _load_turn(self, run: ChatRun) -> tuple[AssistantChat, AssistantChatMessage]:
        """
        :param run: A Kuma run.
        :return: The run's chat and the human message the run answers.
        """

        chat = AssistantChat.objects.get(id=run.chat_id)
        return chat, chat.messages.get(id=run.context["human_message_id"])

    def _save_answer(
        self,
        run: ChatRun,
        chat: AssistantChat,
        human_message: AssistantChatMessage,
        result: AssistantRunResult,
        status: str,
        error_code: str,
    ) -> dict[str, Any]:
        """
        Saves the AI message answering the run's human message, its prediction, and
        the chat's history and title. A run whose agent didn't trace itself is
        reported now, so every message counts in Kuma's outcomes.

        :param run: The run.
        :param chat: The run's chat.
        :param human_message: The message the run answers.
        :param result: What the run produced.
        :param status: The run's final status.
        :param error_code: Why the run failed or stopped, if it did.
        :return: The saved AI message, as clients show it.
        """

        trace_id = result.trace_id
        if trace_id is None:
            tracer = PosthogTracingCallback()
            tracer.capture_outcome(
                chat,
                human_message.content,
                trace_outcome_for(status, error_code),
                run.started_on or run.created_on,
            )
            trace_id = tracer.trace_id

        artifacts: dict[str, Any] = {"sources": result.sources}
        if result.onboarding_target is not None:
            artifacts["onboarding_target"] = result.onboarding_target
        if status != ChatRunStatus.COMPLETED:
            artifacts["run"] = {"status": str(status), "error_code": error_code}
        ai_message = AssistantChatMessage.objects.create(
            chat=chat,
            role=AssistantChatMessage.Role.AI,
            content=result.text,
            artifacts=artifacts,
            action_group_id=run.context.get("action_group_id"),
        )
        AssistantChatPrediction.objects.create(
            human_message=human_message,
            ai_response=ai_message,
            prediction={"answer": result.text, "posthog_trace_id": trace_id},
        )

        chat.message_history = result.message_history
        update_fields = ["message_history", "updated_on"]
        if result.title:
            chat.title = result.title
            update_fields.append("title")
        chat.save(update_fields=update_fields)
        return assistant_message_payload(ai_message)
