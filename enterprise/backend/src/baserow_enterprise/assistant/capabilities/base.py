from typing import Annotated, Any, Generic, Literal, Tuple

from django.contrib.auth.models import AbstractUser

from asgiref.sync import sync_to_async
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langsmith import traceable

from baserow.core.models import Workspace
from baserow_enterprise.assistant.models import AssistantChat
from baserow_enterprise.assistant.types import (
    AssistantExecutionContext,
    PartialStateType,
    StateType,
    UIContext,
)
from baserow_enterprise.assistant.utils.helpers import find_last_ui_context


class AssistantBaseTool(BaseTool):
    usage_instructions: str | None = None
    """
    Instructions on how and when to use this tool that will be injected in the prompt of
    the LLM binding this tool.
    """

    _context: AssistantExecutionContext

    def _init_run(self, config: RunnableConfig) -> None:
        """Initialize the tool with user and workspace from the config."""

        configurable = config.get("configurable", {})
        self._context = configurable.get("context")
        if self._context is None:
            self._chat = self._context.get("chat")

    def _run(self, *args, config: RunnableConfig, **kwargs) -> Tuple[str, Any]:
        """
        Returns the result of the tool run and a tool-specific artifact.
        """

        self._init_run(config)
        return self._run_impl(*args, **kwargs)

    async def _arun(self, *args, config: RunnableConfig, **kwargs) -> Tuple[str, Any]:
        """
        Returns the result of the tool run and a tool-specific artifact.
        """

        self._init_run(config)
        return await sync_to_async(self._run_impl)(*args, **kwargs)

    @traceable
    def _run_impl(self, *args, **kwargs):
        raise NotImplementedError()

    def can_be_used(self) -> bool:
        """
        Returns whether the tool can be used in the current context.
        """

        return True


class AssistantNode(Generic[StateType, PartialStateType]):
    """
    Base class for assistant nodes. Nodes defines a synchronous `run` function or the
    asynchronous `arun` function to implement the logic of a given node in the assistant
    graph. A node receive the current state as input, perform some computation or
    side-effect, and return an updated state. They are interconnected via edges defined
    in the AssistantGraphBuilder. Sometimes nodes can directly jump to other nodes in
    the graph without going through the usual edges, via the `langgraph.types.Command`
    class.
    """

    def __init__(self, context: AssistantExecutionContext):
        self._context = context

    def _get_ui_context(self, state: StateType) -> UIContext | None:
        """
        Extracts the UI context from the latest human message.
        """

        return find_last_ui_context(state.messages)

    @traceable
    async def __call__(
        self, state: StateType, config: RunnableConfig
    ) -> PartialStateType | None:
        """
        Run the assistant node logic. If available, the asynchronous `arun` function
        will be used, otherwise the synchronous `run` function will be called.

        :param state: The current state of the assistant.
        :param config: The configuration for the runnable.
        :return: The updated state of the assistant or None if the node was not run.
        """

        try:
            return await self.arun(state, config)
        except NotImplementedError:
            return await sync_to_async(self.run)(state, config)

    def run(self, state: StateType, config: RunnableConfig) -> PartialStateType | None:
        """
        Synchronous node logic. Used when async `arun` isn't provided.

        :param state: The current state of the assistant. Usually the AssistantState,
            but nodes can customize their input state schema when needed.
        :param config: The configuration for the runnable.
        :return: The updated state of the assistant or None if the node was not run.
            Usually a PartialAssistantState, but nodes can customize their output state
            schema when needed.
        """

        raise NotImplementedError

    async def arun(
        self, state: StateType, config: RunnableConfig
    ) -> PartialStateType | None:
        """
        Asynchronous node logic. If implemented, it takes precedence over `run`.

        :param state: The current state of the assistant. Usually the AssistantState,
            but nodes can customize their input state schema when needed.
        :param config: The configuration for the runnable.
        :return: The updated state of the assistant or None if the node was not run.
            Usually a PartialAssistantState, but nodes can customize their output state
            schema when needed.
        """

        raise NotImplementedError
