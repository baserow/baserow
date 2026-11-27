"""Read and project saved Kuma messages without constructing a model client."""

from typing import Any

from baserow.core.action.models import Action

from .models import AssistantChat, AssistantChatMessage
from .types import AiMessage, HumanMessage, ReplyUndo


def _reply_undo(message: AssistantChatMessage) -> ReplyUndo | None:
    if message.action_group_id:
        session = (
            Action.objects.filter(
                user_id=message.chat.user_id,
                action_group=message.action_group_id,
                undone_at__isnull=True,
                session__isnull=False,
            )
            .values_list("session", flat=True)
            .first()
        )
        if session:
            return ReplyUndo(group_id=str(message.action_group_id), session_id=session)
    return None


def to_assistant_message(
    message: AssistantChatMessage, *, latest: bool = True
) -> HumanMessage | AiMessage:
    """
    Projects a saved chat message to the message the chat shows.

    :param message: The saved message, with `prediction` selected for AI messages.
    :return: The human or AI message.
    """

    if message.role == AssistantChatMessage.Role.HUMAN:
        return HumanMessage(
            content=message.content, id=message.id, timestamp=message.created_on
        )

    prediction = getattr(message, "prediction", None)
    run_state = message.artifacts.get("run") or {}
    return AiMessage(
        undo=_reply_undo(message) if latest else None,
        content=message.content,
        id=message.id,
        timestamp=message.created_on,
        sources=message.artifacts.get("sources"),
        run_status=run_state.get("status"),
        error_code=run_state.get("error_code"),
        onboarding_target=message.artifacts.get("onboarding_target"),
        can_submit_feedback=prediction is not None,
        human_sentiment=prediction.get_human_sentiment_display()
        if prediction
        else None,
    )


def assistant_message_payload(message: AssistantChatMessage) -> dict[str, Any]:
    """
    Projects a saved chat message to the JSON the chat run events carry, the same
    shape the chat messages API returns.

    :param message: The saved message, with `prediction` selected for AI messages.
    :return: The message as a JSON-serializable dict.
    """

    return to_assistant_message(message).model_dump(mode="json")


def list_chat_messages(
    chat: AssistantChat, last_message_id: int | None = None, limit: int = 100
) -> list[HumanMessage | AiMessage]:
    """Read recent saved messages in chronological order.

    :param chat: The chat whose messages to read.
    :param last_message_id: An exclusive message-ID pagination cursor.
    :param limit: The maximum number of messages to return.
    :return: The projected messages, oldest first.
    """

    queryset = chat.messages.select_related("prediction").order_by("-created_on", "-id")
    if last_message_id is not None:
        queryset = queryset.filter(id__lt=last_message_id)
    newest_first = list(queryset[:limit])
    return [
        to_assistant_message(
            message, latest=last_message_id is None and message is newest_first[0]
        )
        for message in reversed(newest_first)
    ]
