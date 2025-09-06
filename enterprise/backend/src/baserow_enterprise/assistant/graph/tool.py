from typing import Any, Literal, Tuple
from baserow.core.models import Workspace
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from django.contrib.auth.models import AbstractUser
from asgiref.sync import sync_to_async

from baserow_enterprise.assistant.models import AssistantChat
from baserow_enterprise.assistant.types import AiMessage, AssistantState


def tools_condition(
    state: AssistantState,
) -> Literal["tools", "__end__"]:
    ai_message = state.messages[-1]
    if isinstance(ai_message, AiMessage) and ai_message.tool_calls:
        return "tools"
    return "__end__"


class AssistantBaseTool(BaseTool):
    response_format: Literal["content_and_artifact"] = "content_and_artifact"

    _chat: AssistantChat
    _user: AbstractUser
    _workspace: Workspace

    def _init_run(self, config: RunnableConfig) -> None:
        """Initialize the tool with user and workspace from the config."""

        configurable = config.get("configurable", {})
        self._chat = configurable.get("chat")
        self._user = configurable.get("user")
        self._workspace = configurable.get("workspace")

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

    def _run_impl(self, *args, **kwargs):
        raise NotImplementedError()
