from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from asgiref.sync import sync_to_async
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage as LCAIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig

from baserow_enterprise.assistant.capabilities.base import (
    AssistantBaseTool,
    AssistantNode,
)
from baserow_enterprise.assistant.capabilities.knowledge_retrieval.tools import (
    RetrieveKnowledgeTool,
)
from baserow_enterprise.assistant.types import (
    AiMessage,
    AssistantState,
    PartialAssistantState,
    ToolCall,
    ToolCallMessage,
)
from baserow_enterprise.assistant.utils.helpers import get_message_buffer

from .prompts import ROOT_SYSTEM_PROMPT


@sync_to_async
def get_root_tools(config: RunnableConfig) -> list[AssistantBaseTool]:
    """
    Get the root tools available for the assistant.

    :param config: The runnable config containing user and workspace information.
    :return: A list of AssistantBaseTool instances that can be used in the current
        context.
    """

    tools = [RetrieveKnowledgeTool()]
    return [tool for tool in tools if tool.can_be_used(config)]


def root_tools_condition(
    state: AssistantState,
) -> Literal["tools", "__end__"]:
    ai_message = state.messages[-1]
    if isinstance(ai_message, AiMessage) and ai_message.tool_calls:
        return "tools"
    return "__end__"


class RootNode(AssistantNode):
    def _handle_tool_calls(
        self, message: LCAIMessage, state: AssistantState
    ) -> PartialAssistantState:
        """
        Handles the tool calls returned by the AI message.
        This message will be followed by a RootToolsNode to execute the tool calls.
        It won't be shown to the user in the chat interface.
        """

        return PartialAssistantState(
            messages=[
                AiMessage(
                    tool_calls=[
                        ToolCall(
                            id=tool_call["id"],
                            name=tool_call["name"],
                            args=tool_call["args"],
                        )
                        for tool_call in message.tool_calls
                    ],
                )
            ]
        )

    def _handle_ai_response(
        self, message: LCAIMessage, state: AssistantState
    ) -> PartialAssistantState:
        """
        Handles a final AI message response without tool calls. This message will be
        shown to the user in the chat interface. All the sources collected during the
        conversation will be attached to the message and reset in the state.
        """

        return PartialAssistantState(
            sources=None,
            messages=[
                AiMessage(
                    content=str(message.content),
                    sources=state.sources,
                )
            ],
        )

    async def arun(self, state: AssistantState, config: RunnableConfig):
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", ROOT_SYSTEM_PROMPT),
                *get_message_buffer(state.messages, limit_human_messages=50),
            ],
            template_format="mustache",
        )
        tools = await get_root_tools(config)
        chain = prompt | self._model.bind_tools(tools)

        ui_context = self._get_ui_context(state)
        timezone = ui_context.timezone or "UTC"
        tools_usage_instructions = "\n".join(
            [
                f"<{tool.name}>\n{tool.usage_instructions}\n</{tool.name}>"
                for tool in tools
                if tool.usage_instructions
            ]
        )

        message: LCAIMessage = await chain.ainvoke(
            {
                "tools_usage_instructions": tools_usage_instructions,
                "ui_context": ui_context,
                "user_id": self._user.id,
                "user_name": self._user.first_name,
                "user_email": self._user.email,
                "current_date": datetime.now(tz=ZoneInfo(timezone)).isoformat(),
                "timezone": timezone,
            },
            config=config,
        )

        if message.tool_calls:
            return self._handle_tool_calls(message, state)
        else:
            return self._handle_ai_response(message, state)

    @property
    def _model(self):
        return init_chat_model(
            model="openai:gpt-4.1-mini",
            temperature=0.3,
            streaming=True,
        )


class RootToolsNode(AssistantNode):
    async def arun(
        self, state: AssistantState, config: RunnableConfig
    ) -> PartialAssistantState | None:
        last_message = state.messages[-1]
        if not isinstance(last_message, AiMessage) or not last_message.tool_calls:
            return None

        tools = await get_root_tools(config)

        messages = []
        update = {"messages": messages}
        for tool_call in last_message.tool_calls:
            tool = next((t for t in tools if t.name == tool_call.name), None)
            if not tool:
                continue

            tool_args = tool_call.args
            result = await tool.arun(
                tool_args, config=config, tool_call_id=tool_call.id
            )
            messages.append(
                ToolCallMessage(
                    tool_call_id=tool_call.id,
                    content=result.content,
                    artifact=result.artifact,
                )
            )

            if result.artifact and (
                new_sources := getattr(result.artifact, "sources", None)
            ):
                if update.get("sources") is None:
                    update["sources"] = set()
                update["sources"].update(set(new_sources))

        return PartialAssistantState(**update)
