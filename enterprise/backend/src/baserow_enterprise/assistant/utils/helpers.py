from typing import Optional, Sequence, TypeVar

from langchain_core.messages.base import BaseMessage
from langchain_core.messages.system import SystemMessage

from baserow_enterprise.assistant.types import (
    AiMessage,
    AssistantMessageUnion,
    HumanMessage,
    ToolMessage,
    UIContext,
)

T = TypeVar("T", bound=AssistantMessageUnion)


def find_last_message_of_type(
    messages: Sequence[AssistantMessageUnion], message_type: type[T]
) -> Optional[T]:
    return next(
        (msg for msg in reversed(messages) if isinstance(msg, message_type)), None
    )


def find_last_ui_context(
    messages: Sequence[AssistantMessageUnion],
) -> UIContext | None:
    """Returns the last recorded UI context from all messages."""

    for message in reversed(messages):
        if isinstance(message, HumanMessage) and message.ui_context is not None:
            return message.ui_context
    return None


def get_buffer_string(
    messages: Sequence[AssistantMessageUnion | BaseMessage],
    human_prefix: str = "Human",
    ai_prefix: str = "AI",
) -> str:
    """Convert a sequence of Messages to strings and concatenate them into one string.

    Args:
        messages: Messages to be converted to strings.
        human_prefix: The prefix to prepend to contents of HumanMessages.
            Default is "Human".
        ai_prefix: THe prefix to prepend to contents of AIMessages. Default is "AI".

    Returns:
        A single string concatenation of all input messages.

    Raises:
        ValueError: If an unsupported message type is encountered.

    Example:
        .. code-block:: python

            from langchain_core import AIMessage, HumanMessage

            messages = [
                HumanMessage(content="Hi, how are you?"),
                AIMessage(content="Good, how are you?"),
            ]
            get_buffer_string(messages)
            # -> "Human: Hi, how are you?\nAI: Good, how are you?"
    """

    string_messages = []
    for m in messages:
        if isinstance(m, HumanMessage):
            role = human_prefix
        elif isinstance(m, AiMessage):
            role = ai_prefix
        elif isinstance(m, SystemMessage):
            role = "System"
        elif isinstance(m, ToolMessage):
            role = "Tool"
        else:
            msg = f"Got unsupported message type: {m}"
            raise ValueError(msg)  # noqa: TRY004
        message = f"{role}: {m.content}"
        if isinstance(m, AiMessage) and m.tool_calls:
            message += f"{m.tool_calls}"
        string_messages.append(message)

    return "\n".join(string_messages)
