"""
Converter between custom Baserow message types and LangChain message types
"""

from typing import List, Union
from langchain_core.messages import (
    HumanMessage as LangChainHumanMessage,
    AIMessage as LangChainAIMessage,
    SystemMessage as LangChainSystemMessage,
    BaseMessage as LangChainBaseMessage,
)
from baserow_enterprise.ai_assistant.utils.types import (
    HumanMessage as BaserowHumanMessage,
    AssistantMessage as BaserowAssistantMessage,
    VisualizationMessage,
    FailureMessage,
    AnyAssistantMessage,
)


def baserow_to_langchain_message(
    message: AnyAssistantMessage,
) -> LangChainBaseMessage:
    """Convert a Baserow message to a LangChain message."""
    
    if isinstance(message, BaserowHumanMessage):
        return LangChainHumanMessage(
            content=message.content,
            id=message.id,
        )
    elif isinstance(message, BaserowAssistantMessage):
        return LangChainAIMessage(
            content=message.content,
            id=message.id,
        )
    elif isinstance(message, VisualizationMessage):
        # Convert visualization to AI message with structured content
        content = f"Query: {message.query}"
        if message.answer:
            content += f"\nAnswer: {message.answer}"
        return LangChainAIMessage(
            content=content,
            id=message.id,
        )
    elif isinstance(message, FailureMessage):
        # Convert failure to system message
        return LangChainSystemMessage(
            content=f"Error: {message.content}",
            id=message.id,
        )
    else:
        raise ValueError(f"Unknown message type: {type(message)}")


def langchain_to_baserow_message(
    message: LangChainBaseMessage,
) -> AnyAssistantMessage:
    """Convert a LangChain message to a Baserow message."""
    
    if isinstance(message, LangChainHumanMessage):
        return BaserowHumanMessage(
            content=message.content,
            id=message.id if hasattr(message, 'id') else None,
        )
    elif isinstance(message, LangChainAIMessage):
        return BaserowAssistantMessage(
            content=message.content,
            id=message.id if hasattr(message, 'id') else None,
        )
    else:
        # Default to assistant message for other types
        return BaserowAssistantMessage(
            content=str(message.content),
            id=message.id if hasattr(message, 'id') else None,
        )


def convert_messages_for_langchain(
    messages: List[AnyAssistantMessage],
) -> List[LangChainBaseMessage]:
    """Convert a list of Baserow messages to LangChain messages."""
    return [baserow_to_langchain_message(msg) for msg in messages]


def convert_messages_from_langchain(
    messages: List[LangChainBaseMessage],
) -> List[AnyAssistantMessage]:
    """Convert a list of LangChain messages to Baserow messages."""
    return [langchain_to_baserow_message(msg) for msg in messages]


class MessageAdapter:
    """Adapter to use with the Assistant class to handle message conversion."""
    
    @staticmethod
    def prepare_state_for_langchain(state: dict) -> dict:
        """Prepare state for LangChain by converting messages."""
        if "messages" in state and state["messages"]:
            # Check if messages need conversion
            if state["messages"] and not isinstance(
                state["messages"][0], LangChainBaseMessage
            ):
                state = {
                    **state,
                    "messages": convert_messages_for_langchain(state["messages"]),
                }
        return state
    
    @staticmethod
    def prepare_result_for_baserow(result: dict) -> dict:
        """Convert LangChain result back to Baserow format."""
        if "messages" in result:
            if isinstance(result["messages"], LangChainBaseMessage):
                # Single message
                result = {
                    **result,
                    "messages": langchain_to_baserow_message(result["messages"]),
                }
            elif isinstance(result["messages"], list):
                # List of messages
                result = {
                    **result,
                    "messages": convert_messages_from_langchain(result["messages"]),
                }
        return result