from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig

from baserow_enterprise.assistant.graph.database_architect.tools import (
    DatabaseArchitectTool,
)
from baserow_enterprise.assistant.graph.database_architect.types import (
    DatabaseArchitectToolArgsSchema,
)
from baserow_enterprise.assistant.graph.doc_search.tools import DocSearchTool
from baserow_enterprise.assistant.graph.node import AssistantNode
from baserow_enterprise.assistant.graph.root.prompts import ROOT_SYSTEM_PROMPT

from baserow_enterprise.assistant.types import (
    AssistantState,
    HumanMessage,
    PartialAssistantState,
    ToolCall,
    ToolCallMessage,
    AiMessage,
)
from baserow_enterprise.assistant.utils.helpers import (
    find_last_message_of_type,
    get_buffer_string,
)
from langgraph.types import Command


def get_tools():
    return [DocSearchTool(), DatabaseArchitectTool()]


class RootNode(AssistantNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._root_tools = get_tools()

    def run(self, state: AssistantState, config: RunnableConfig):
        ui_context = self._get_ui_context(state)
        timezone = self._user.profile.timezone or "UTC"
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", ROOT_SYSTEM_PROMPT),
                *[
                    (
                        "system",
                        f"<{tool.name}>\n" f"{tool.description}\n" f"</{tool.name}>",
                    )
                    for tool in self._root_tools
                ],
            ],
            template_format="mustache",
        )
        chain = prompt | self._model

        message = chain.invoke(
            {
                "user_id": self._user.id,
                "user_name": self._user.first_name,
                "user_email": self._user.email,
                "current_date": datetime.now(tz=ZoneInfo(timezone)).isoformat(),
                "timezone": timezone,
                "messages": get_buffer_string(state.messages),
                "ui_context": ui_context,
            },
            config=config,
        )

        return PartialAssistantState(
            messages=[
                AiMessage(
                    content=str(message.content),
                    tool_calls=[
                        ToolCall(
                            id=tool_call["id"],
                            name=tool_call["name"],
                            args=tool_call["args"],
                        )
                        for tool_call in message.tool_calls
                    ],
                ),
            ],
        )

    @property
    def _model(self):
        return init_chat_model(
            model="openai:gpt-4.1-mini",
            temperature=0.3,
            streaming=True,
            stream_usage=True,
        ).bind_tools(self._root_tools)


class RootToolsNode(AssistantNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._root_tools = get_tools()

    async def arun(
        self, state: AssistantState, config: RunnableConfig
    ) -> Command[Literal["database_architect", "root"]]:
        last_message = state.messages[-1]
        if not isinstance(last_message, AiMessage) or not last_message.tool_calls:
            return PartialAssistantState()

        goto = "root"
        update = PartialAssistantState()

        messages = []
        for tool_call in last_message.tool_calls:
            tool = next((t for t in self._root_tools if t.name == tool_call.name), None)
            if not tool:
                continue

            tool_args = tool_call.args
            result = await tool.arun(
                tool_args, config=config, tool_call_id=tool_call.id
            )

            messages.append(
                ToolCallMessage(
                    content=result.content,
                    artifact=result.artifact,
                    tool_call_id=tool_call.id,
                )
            )
            update.messages = messages

            if isinstance(result.artifact, DatabaseArchitectToolArgsSchema):
                goto = "database_architect"
                update.database_architect_instructions = result.artifact.instructions

                last_human_msg = find_last_message_of_type(state.messages, HumanMessage)
                if last_human_msg:
                    update.database_architect_instructions = f"User request: {last_human_msg.content}\n\nIdea: {result.artifact.instructions}"

        return Command(goto=goto, update=update)
