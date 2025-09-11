import secrets
import string
from typing import TYPE_CHECKING, Optional, Sequence, TypeVar, Union

from langchain_core.messages.base import BaseMessage
from langchain_core.messages.system import SystemMessage

if TYPE_CHECKING:
    from baserow_enterprise.assistant.types import AssistantMessageUnion, UIContext

T = TypeVar("T", bound="AssistantMessageUnion")


def find_last_message_of_type(
    messages: Sequence["AssistantMessageUnion"], message_type: type[T]
) -> Optional[T]:
    return next(
        (msg for msg in reversed(messages) if isinstance(msg, message_type)), None
    )


def find_last_ui_context(
    messages: Sequence["AssistantMessageUnion"],
) -> Optional["UIContext"]:
    """Returns the last recorded UI context from all messages."""

    from baserow_enterprise.assistant.types import HumanMessage

    for message in reversed(messages):
        if isinstance(message, HumanMessage) and message.ui_context is not None:
            return message.ui_context
    return None


def get_buffer_string(
    messages: Sequence[Union["AssistantMessageUnion", BaseMessage]],
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

    from baserow_enterprise.assistant.types import (
        AiMessage,
        HumanMessage,
        ToolCallMessage,
    )

    string_messages = []
    for m in messages:
        if isinstance(m, HumanMessage):
            role = human_prefix
        elif isinstance(m, AiMessage):
            role = ai_prefix
        elif isinstance(m, SystemMessage):
            role = "System"
        elif isinstance(m, ToolCallMessage):
            role = "Tool"
        else:
            msg = f"Got unsupported message type: {m}"
            raise ValueError(msg)  # noqa: TRY004
        message = f"{role}: {m.content}"
        if isinstance(m, AiMessage) and m.tool_calls:
            message += f"{m.tool_calls}"
        string_messages.append(message)

    return "\n".join(string_messages)


def generate_tool_call_id() -> str:
    """
    Generate a tool call ID in the OpenAI/LangChain format.

    Returns a string in the format 'call_' followed by 24 random alphanumeric characters.
    This matches the format used by OpenAI's function calling API and LangChain tool execution.

    Returns:
        str: A tool call ID like 'call_R3Yg96lL2DGofo7IOgbRsxL1'

    Example:
        >>> generate_tool_call_id()
        'call_A1B2C3D4E5F6G7H8I9J0K1L2'
    """
    # Define the character set: uppercase, lowercase, and digits
    chars = string.ascii_letters + string.digits

    # Generate 24 random characters using cryptographically secure random
    random_part = "".join(secrets.choice(chars) for _ in range(24))

    return f"call_{random_part}"
