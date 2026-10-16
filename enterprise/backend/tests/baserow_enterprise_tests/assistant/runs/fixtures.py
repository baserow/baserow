from typing import Any
from unittest.mock import MagicMock

from pydantic_ai.messages import ModelMessagesTypeAdapter, TextPart, UserPromptPart

from baserow.core.chat_runs.models import ChatRun
from baserow_enterprise.assistant.models import AssistantChat, AssistantChatMessage


def ai_message(run: ChatRun) -> AssistantChatMessage:
    return AssistantChatMessage.objects.select_related("prediction").get(
        chat_id=run.chat_id, role=AssistantChatMessage.Role.AI
    )


def history_texts(run: ChatRun) -> list[str]:
    chat = AssistantChat.objects.get(id=run.chat_id)
    messages = ModelMessagesTypeAdapter.validate_json(bytes(chat.message_history))
    return [
        part.content
        for message in messages
        for part in message.parts
        if isinstance(part, (UserPromptPart, TextPart))
    ]


def traces(posthog_client: MagicMock) -> list[dict[str, Any]]:
    return [
        call.kwargs["properties"]
        for call in posthog_client.capture.call_args_list
        if call.kwargs["event"] == "$ai_trace"
    ]
