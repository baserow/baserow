from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS, transaction
from django.utils import translation

from asgiref.sync import sync_to_async
from loguru import logger

from baserow.api.sessions import (
    set_client_undo_redo_action_group_id,
    set_untrusted_client_session_id,
)
from baserow.core.chat_runs.constants import ChatRunErrorCode, ChatRunEventKind
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
    rates stay comparable with runs whose agent traced itself.

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
    ui_context: UIContext
    model_profile: ResolvedAssistantModelProfile


class AssistantChatRunType(ChatRunType):
    """
    Kuma's messages, answered in the background. The send endpoint saves the
    human message. A run first closes its chat's earlier interrupted turns, then
    saves its own answer, prediction and history when it ends.
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
        reporting to the journal.

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
                run.context["origin_tab_id"],
            )
            return await assistant.answer(
                restored.human_message.content,
                restored.ui_context,
                run.context["generate_title"],
            )

    def _restore(self, run: ChatRun) -> RestoredRun:
        """
        Loads what the run answers and puts the sending request's context back on
        the chat's user, so tools act as they would have during the request. It
        first closes the chat's earlier interrupted turns, so the model reads a
        complete history.

        :param run: The claimed run.
        :return: The chat, the message, the UI context and a ready model profile.
        """

        self._repair_interrupted_turns(run)
        chat = AssistantChat.objects.select_related("workspace", "user__profile").get(
            id=run.chat_id
        )
        human_message = chat.messages.get(id=run.context["human_message_id"])
        ui_context = UIContext.model_validate(run.context["ui_context"])

        user = chat.user
        if session_id := run.context["client_session_id"]:
            set_untrusted_client_session_id(user, session_id)
        set_client_undo_redo_action_group_id(user, run.context["action_group_id"])
        # Without a websocket id, the sending tab also gets the realtime events.
        user.web_socket_id = None
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
        Saves the final answer and model history. Without a result the turn
        closes as unfinished, since execution may have changed data, unless the
        model was unavailable and nothing ran.

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
                NOT_STARTED_ANSWER
                if outcome.error_code == ERROR_MODEL_UNAVAILABLE
                else unfinished_answer(""),
            ),
        )
        return self._save_answer(
            run, chat, human_message, result, outcome.status, outcome.error_code
        )

    def serialize_outcome(self, run: ChatRun) -> dict[str, Any] | None:
        """
        Returns the run's saved answer with its current rating and chat title,
        which can both change after the run ends.

        :param run: The run.
        :return: The saved answer, the run's own outcome once its chat is
            deleted, or None when the run saved no answer.
        """

        if run.outcome is None:
            return None
        message = (
            AssistantChatMessage.objects.using(DEFAULT_DB_ALIAS)
            .select_related("prediction", "chat")
            .filter(
                id=run.outcome["id"],
                chat_id=run.chat_id,
                role=AssistantChatMessage.Role.AI,
            )
            .first()
        )
        if message is None:
            return run.outcome
        return {**assistant_message_payload(message), "chat_title": message.chat.title}

    def on_run_lost(
        self, run: ChatRun, events: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """
        Saves what the user saw of a run whose worker died, closing its turn as
        unfinished.

        :param run: The run.
        :param events: The run's output, or None when it was missing or
            incomplete, which keeps no text.
        :return: The saved AI message.
        """

        chat, human_message = self._load_turn(run)
        text = ""
        segment = None
        for event in events or []:
            data = event.get("data") or {}
            if event.get("kind") == ChatRunEventKind.TEXT_DELTA:
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
        """
        Closes, once, the turn of a started run that saved no answer, so the model
        knows changes may exist.

        :param run: The run.
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
                .filter(id=run.context["human_message_id"])
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
        """
        Closes the chat's earlier turns whose run started but saved no answer.

        :param run: The run about to answer the chat's next message.
        """

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
            action_group_id=run.context["action_group_id"],
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
