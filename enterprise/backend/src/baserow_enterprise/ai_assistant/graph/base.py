"""
Base classes for assistant nodes.
"""
from abc import ABC, abstractmethod
from typing import Optional, TypeVar, Generic
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from baserow_enterprise.ai_assistant.utils.types import (
    AssistantState,
    PartialAssistantState,
)


StateType = TypeVar("StateType", bound=BaseModel)
PartialStateType = TypeVar("PartialStateType", bound=BaseModel)


class BaseAssistantNode(ABC, Generic[StateType, PartialStateType]):
    """Base class for all assistant nodes."""

    def __init__(self, workspace_id: Optional[int] = None):
        self.workspace_id = workspace_id

    async def __call__(
        self, state: StateType, config: RunnableConfig
    ) -> Optional[PartialStateType]:
        """Main entry point for the node."""
        return await self.arun(state, config)

    @abstractmethod
    async def arun(
        self, state: StateType, config: RunnableConfig
    ) -> Optional[PartialStateType]:
        """Async run method to be implemented by subclasses."""
        pass

    def router(self, state: StateType) -> str:
        """Default router - can be overridden by subclasses."""
        return "next"

    def _get_last_human_message(self, state) -> Optional[str]:
        """Extract the last human message from state."""
        if not hasattr(state, "messages") or not state.messages:
            return None

        for message in reversed(state.messages):
            if hasattr(message, "type") and message.type == "human":
                return message.content
        return None

    def _get_context_from_config(self, config: RunnableConfig) -> dict:
        """Extract context from the runnable config."""
        return config.get("configurable", {})


class AssistantNode(BaseAssistantNode[StateType, PartialStateType]):
    """Concrete base class with common functionality."""

    def _get_last_human_message(self, state) -> Optional[str]:
        """Extract the last human message from state."""
        if not hasattr(state, "messages") or not state.messages:
            return None

        for message in reversed(state.messages):
            if hasattr(message, "type") and message.type == "human":
                return message.content
        return None

    def _get_context_from_config(self, config: RunnableConfig) -> dict:
        """Extract context from the runnable config."""
        return config.get("configurable", {})

    async def arun(
        self, state: StateType, config: RunnableConfig
    ) -> Optional[PartialStateType]:
        """Default implementation - override in subclasses."""
        return None
