import secrets
import string
from typing import TYPE_CHECKING, Optional, Sequence, TypeVar
from uuid import uuid4

from langchain_core.messages import AIMessage as LCAIMessage
from langchain_core.messages import BaseMessage as LCBaseMessage
from langchain_core.messages import HumanMessage as LCHumanMessage
from langchain_core.messages import ToolCall as LCToolCall
from langchain_core.messages import ToolMessage as LCToolMessage

if TYPE_CHECKING:
    from baserow_enterprise.assistant.types import AssistantMessageUnion, UIContext


T = TypeVar("T", bound="AssistantMessageUnion")


def uuid4_str() -> str:
    """
    Generate a new UUID4 and return it as a string.
    """

    return str(uuid4())


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


def get_message_buffer(
    messages: Sequence["AssistantMessageUnion"],
    limit_human_messages: Optional[int] = None,
) -> list[LCBaseMessage]:
    """
    Converts a list of AssistantMessageUnion to a list of LangChain BaseMessage,
    limiting the number of messages if a limit is provided.

    :param messages: The messages to convert.
    :param limit_human_messages: The maximum number of human messages to include. If
        None, include all.
    :return: The list of LangChain BaseMessage.
    """

    from baserow_enterprise.assistant.types import (
        AiMessage,
        HumanMessage,
        ToolCallMessage,
    )

    if limit_human_messages is not None:
        human_msg_count, i = 0, -1
        for msg in reversed(messages):
            i -= 1
            if isinstance(msg, HumanMessage):
                human_msg_count += 1
                if human_msg_count >= limit_human_messages:
                    break
    else:
        i = 0

    last_messages = messages[i:]

    # Gather tool call responses for pairing with their calls.
    # Unpaired calls will cause downstream LLM invocations to fail.
    tool_message_by_call_id: dict[str, LCToolMessage] = {}
    for msg in last_messages:
        if isinstance(msg, ToolCallMessage):
            tool_message_by_call_id[msg.tool_call_id] = LCToolMessage(
                content=msg.content, tool_call_id=msg.tool_call_id
            )

    def _get_human_message(msg: HumanMessage) -> LCHumanMessage:
        return LCHumanMessage(content=msg.content)

    def _get_ai_message(msg: AiMessage) -> LCAIMessage | None:
        tool_calls = [
            LCToolCall(id=tc.id, name=tc.name, args=tc.args)
            for tc in msg.tool_calls
            if tc.id in tool_message_by_call_id
        ]
        if msg.tool_calls and not tool_calls:
            return None  # Ignore all the tool calls without a response, as the AI will fail

        return LCAIMessage(content=msg.content, tool_calls=tool_calls)

    def _get_tool_call_message(msg: ToolCallMessage) -> LCToolMessage | None:
        if msg.tool_call_id not in tool_message_by_call_id:
            return None

        return LCToolMessage(
            id=msg.id, content=msg.content, tool_call_id=msg.tool_call_id
        )

    lc_messages = []
    for msg in last_messages:
        if isinstance(msg, HumanMessage):
            message = _get_human_message(msg)
        elif isinstance(msg, AiMessage):
            message = _get_ai_message(msg)
        elif isinstance(msg, ToolCallMessage):
            message = _get_tool_call_message(msg)
        else:
            continue

        if message:
            lc_messages.append(message)

    return lc_messages


def generate_tool_call_id() -> str:
    """
    Generate a tool call ID in the OpenAI/LangChain format.

    Returns a string in the format 'call_' followed by 24 random alphanumeric
    characters. This matches the format used by OpenAI's function calling API and
    LangChain tool execution.

    :return: A tool call ID like 'call_R3Yg96lL2DGofo7IOgbRsxL1'

    Example:
        >>> generate_tool_call_id()
        'call_A1B2C3D4E5F6G7H8I9J0K1L2'
    """

    # Define the character set: uppercase, lowercase, and digits
    chars = string.ascii_letters + string.digits

    # Generate 24 random characters using cryptographically secure random
    random_part = "".join(secrets.choice(chars) for _ in range(24))

    return f"call_{random_part}"
