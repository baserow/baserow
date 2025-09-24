from dataclasses import replace
from datetime import datetime
from typing import List, Literal, Optional
from zoneinfo import ZoneInfo

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage as LCAIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig

from baserow_enterprise.assistant.capabilities.base import (
    AssistantBaseTool,
    AssistantNode,
)
from baserow_enterprise.assistant.capabilities.database_architect.tools import (
    DatabaseArchitectTool,
)
from baserow_enterprise.assistant.capabilities.knowledge_retrieval.tools import (
    RetrieveKnowledgeTool,
)
from baserow_enterprise.assistant.capabilities.data_manager.tools import (
    DataManagerTool,
    GetDatabaseSchemaTool,
)
from baserow_enterprise.assistant.capabilities.planner.tools import (
    TaskPlannerTool,
)
from baserow_enterprise.assistant.types import (
    AiInterruptMessage,
    AiMessage,
    AssistantState,
    HumanMessage,
    PartialAssistantState,
    TaskPlan,
    ToolCall,
    ToolCallMessage,
    ASSISTANT_GRAPH_NODE,
)
from baserow_enterprise.assistant.utils.helpers import (
    LCHumanMessage,
    generate_tool_call_id,
    get_message_buffer,
)
from .prompts import CONTEXT_PROMPT, ROOT_SYSTEM_PROMPT

from langgraph.types import Command, interrupt
from langgraph.prebuilt import ToolNode


ROOT_TOOLS = None


def get_root_tools() -> list[AssistantBaseTool]:
    """
    Get the root tools available for the assistant.

    :param config: The runnable config containing user and workspace information.
    :return: A list of AssistantBaseTool instances that can be used in the current
        context.
    """

    global ROOT_TOOLS

    if ROOT_TOOLS is None:
        tools: list[AssistantBaseTool] = [
            RetrieveKnowledgeTool(),
            DatabaseArchitectTool(),
            DataManagerTool(),
            GetDatabaseSchemaTool(),
            TaskPlannerTool(),
        ]
        ROOT_TOOLS = [tool for tool in tools if tool.can_be_used()]

    return ROOT_TOOLS


def root_tools_condition(
    state: AssistantState,
) -> Literal["tools", "__end__"]:
    ai_message = state.messages[-1]
    if isinstance(ai_message, AiMessage) and ai_message.tool_calls:
        return "tools"
    return "__end__"


class RootNode(AssistantNode):
    @property
    def tools(self) -> list[AssistantBaseTool]:
        return get_root_tools()

    def _handle_tool_calls(
        self, message: LCAIMessage, state: AssistantState, update: PartialAssistantState
    ) -> PartialAssistantState:
        """
        Handles the tool calls returned by the AI message.
        It won't be shown to the user in the chat interface.
        """

        update.messages.append(
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
        )
        return update

    def _handle_ai_response(
        self, message: LCAIMessage, state: AssistantState, update: PartialAssistantState
    ) -> PartialAssistantState:
        """
        Handles a final AI message response without tool calls. This message will be
        shown to the user in the chat interface. All the sources collected during the
        conversation will be attached to the message and reset in the state.
        """

        update.sources = None
        update.messages.append(
            AiMessage(
                content=str(message.content),
                sources=state.sources,
            )
        )
        return update

    def _get_next_plan_task(self, task_plan: list[TaskPlan]) -> TaskPlan | None:
        """Get the next task to execute from the plan."""
        for task in task_plan:
            # Skip completed or failed tasks
            if task.status in ["completed", "failed"]:
                continue

            # Check if all dependencies are completed
            dependencies_met = True
            for dep_id in task.dependencies:
                dep_task = next((t for t in task_plan if t.id == dep_id), None)
                if not dep_task or dep_task.status != "completed":
                    dependencies_met = False
                    break

            # If this task is pending and dependencies are met, return it
            if task.status == "pending" and dependencies_met:
                return task

            # If this task is in progress, return it (resume execution)
            if task.status == "in_progress":
                return task

        return None

    def _format_tool_usage_instructions(self, tools: list[AssistantBaseTool]) -> str:
        """
        Formats the usage instructions for the given tools to be included in the system
        prompt.

        :param tools: The list of tools to format.
        :return: A formatted string containing the usage instructions for the tools.
        """

        return "\n\n".join(
            [
                f"<{tool.name}>\n{tool.usage_instructions}\n</{tool.name}>"
                for tool in tools
                if tool.usage_instructions
            ]
        )

    async def arun(self, state: AssistantState, config: RunnableConfig):
        # Check if we have an active plan to execute
        message_history = get_message_buffer(state.messages, limit_human_messages=30)
        tools = self.tools

        update = PartialAssistantState()

        if (
            state.plan_mode_active
            and state.task_plan
            and (next_task := self._get_next_plan_task(state.task_plan))
        ):
            # Update task status to in_progress
            next_task.status = "in_progress"
            update.task_plan = state.task_plan

            message_history.append(
                LCHumanMessage(content=f"Task: {next_task.description}")
            )

            # Remove the planner tool to avoid re-planning
            tools = [t for t in self.tools if not isinstance(t, TaskPlannerTool)]

        # Build the prompt
        prompt_messages = [
            ("system", ROOT_SYSTEM_PROMPT),
            ("system", CONTEXT_PROMPT),
        ]

        prompt_messages.extend(message_history)

        prompt = ChatPromptTemplate.from_messages(
            prompt_messages,
            template_format="mustache",
        )

        model = self._model
        if tools:
            model = model.bind_tools(tools)
            tools_usage_instructions = self._format_tool_usage_instructions(tools)
        else:
            tools_usage_instructions = ""

        chain = prompt | model

        ui_context = self._get_ui_context(state)
        timezone = ui_context.timezone if ui_context else "UTC"

        message: LCAIMessage = await chain.ainvoke(
            {
                "tools_usage_instructions": tools_usage_instructions,
                "ui_context": str(ui_context) if ui_context else "",
                "user": self._context.chat.user,
                "current_date": datetime.now(tz=ZoneInfo(timezone)).isoformat(),
                "timezone": timezone,
            },
            config=config,
        )

        if message.tool_calls:
            return self._handle_tool_calls(message, state, update)
        else:
            return self._handle_ai_response(message, state, update)

    @property
    def _model(self):
        return init_chat_model(
            model="openai:gpt-5",
            # temperature=0,
            reasoning={
                "effort": "low",  # 'low', 'medium', or 'high'
                # "summary": "auto",  # 'detailed', 'auto', or None
            },
            streaming=True,
        )


class RootToolNode(AssistantNode):
    def __init__(self, *args, tools: list[AssistantBaseTool] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tools: Optional[List[AssistantBaseTool]] = tools

    async def arun(
        self, state: AssistantState, config: RunnableConfig
    ) -> Command[Literal[ASSISTANT_GRAPH_NODE.ROOT]]:
        last_message = state.messages[-1]
        if not isinstance(last_message, AiMessage) or not last_message.tool_calls:
            return None

        update = PartialAssistantState()
        result = Command(goto=ASSISTANT_GRAPH_NODE.ROOT, update=update)

        # Check if we're executing a plan task
        current_plan_task = None
        if state.plan_mode_active and state.task_plan:
            # Find the in-progress task
            current_plan_task = next(
                (t for t in state.task_plan if t.status == "in_progress"), None
            )

        for tool_call in last_message.tool_calls:
            tool = next((t for t in self._tools if t.name == tool_call.name), None)
            if tool is None:
                # If this is a plan task, mark it as failed
                if current_plan_task:
                    current_plan_task.status = "failed"
                    update.task_plan = state.task_plan
                raise ValueError(f"Tool {tool_call.name} not found")

            tool_args = tool_call.args

            try:
                tool_result = await tool.arun(
                    {**tool_args, "state": state},
                    tool_call_id=tool_call.id,
                    config=config,
                )

                # If this is a plan task and it succeeded, mark it as completed
                if current_plan_task:
                    current_plan_task.status = "completed"
                    current_plan_task.result = "Done"
                    update.task_plan = state.task_plan

                if isinstance(tool_result, Command):
                    if not tool_result.goto:
                        tool_result = replace(
                            tool_result, goto=ASSISTANT_GRAPH_NODE.ROOT
                        )

                    return tool_result

                elif isinstance(tool_result, (list, tuple)) and len(tool_result) == 2:
                    # The tool returned a tuple of (str, artifact)
                    tool_msg = ToolCallMessage(
                        tool_call_id=tool_call.id,
                        content=tool_result[0],
                        artifact=tool_result[1],
                    )

                elif isinstance(tool_result, str):
                    tool_msg = ToolCallMessage(
                        tool_call_id=tool_call.id,
                        content=tool_result,
                    )

                else:
                    raise ValueError(f"Invalid result type {type(tool_result)}")

                update.messages.append(tool_msg)

            except Exception as e:
                # If this is a plan task and it failed, mark it as failed
                if current_plan_task:
                    current_plan_task.status = "failed"
                    current_plan_task.result = str(e)
                    update.task_plan = state.task_plan
                    update.plan_mode_active = False  # Exit plan mode on failure
                raise

        return result


class InterruptNode(AssistantNode):
    async def arun(
        self, state: AssistantState, config: RunnableConfig
    ) -> Command[Literal[ASSISTANT_GRAPH_NODE.ROOT]]:
        last_message = state.messages[-1]
        if not isinstance(last_message, AiInterruptMessage):
            return None

        user_response = interrupt(last_message)

        update = PartialAssistantState(messages=[HumanMessage(content=user_response)])

        if last_message.tool_call_id:
            for msg in reversed(state.messages):
                if (
                    isinstance(msg, AiMessage)
                    and msg.tool_calls
                    and (
                        tool_call := next(
                            (
                                tc
                                for tc in msg.tool_calls
                                if tc.id == last_message.tool_call_id
                            ),
                            None,
                        )
                    )
                ):
                    # Let's replay the tool call message that led to the interrupt,
                    # now with the updated user response
                    update.messages.append(
                        AiMessage(
                            tool_calls=[
                                tool_call.model_copy(
                                    update={"id": generate_tool_call_id()}
                                )
                            ],
                        )
                    )
                    return Command(goto=ASSISTANT_GRAPH_NODE.ROOT_TOOLS, update=update)

        return Command(update=update)
