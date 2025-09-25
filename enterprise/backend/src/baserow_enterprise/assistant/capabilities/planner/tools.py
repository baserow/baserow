from typing import Annotated, Any
from pydantic import BaseModel
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langgraph.config import get_stream_writer

from baserow_enterprise.assistant.capabilities.base import AssistantBaseTool
from baserow_enterprise.assistant.utils.helpers import find_last_ui_context

from .types import (
    TaskPlannerToolArgsSchema,
    TaskPlannerToolOutputSchema,
)
from .prompts import (
    TASK_PLANNER_SYSTEM_PROMPT,
    TASK_PLANNER_TOOL_DESCRIPTION,
    TASK_PLANNER_TOOL_USAGE_INSTRUCTIONS,
)

from baserow_enterprise.assistant.types import (
    THINKING_MESSAGES,
    AiThinkingMessage,
    AssistantState,
    PartialAssistantState,
    TaskPlan,
    ToolCallMessage,
)


class TaskPlannerTool(AssistantBaseTool):
    name: str = "task_planner"
    description: str = TASK_PLANNER_TOOL_DESCRIPTION
    usage_instructions: str = TASK_PLANNER_TOOL_USAGE_INSTRUCTIONS
    args_schema: type[BaseModel] = TaskPlannerToolArgsSchema

    def _run_impl(
        self,
        instructions: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
        state: Annotated[AssistantState, InjectedState],
    ) -> Any:
        stream_writer = get_stream_writer()
        stream_writer(
            AiThinkingMessage(
                code=THINKING_MESSAGES.CUSTOM,
                content="Analyzing request and creating task plan...",
            )
        )

        # Get UI context for additional information
        ui_context = find_last_ui_context(state.messages)

        # Initialize the model for planning
        model = init_chat_model(
            "groq:openai/gpt-oss-120b",
            temperature=0,
            max_retries=3,
        )
        model = model.with_structured_output(
            TaskPlannerToolOutputSchema, method="json_schema"
        )

        # Create the prompt
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", TASK_PLANNER_SYSTEM_PROMPT),
                ("human", "User request: {{{instructions}}}"),
            ],
            template_format="mustache",
        )

        # Get the plan from the LLM
        chain = prompt | model
        result: TaskPlannerToolOutputSchema = chain.invoke(
            {
                "instructions": instructions,
            }
        )

        # Activate plan mode and set the task plan
        stream_writer(
            AiThinkingMessage(
                code=THINKING_MESSAGES.CUSTOM,
                content=f"Created plan with {len(result.task_plan)} tasks",
            )
        )

        task_plan = [
            TaskPlan(
                id=task.id,
                description=task.description,
                status=task.status,
                dependencies=task.dependencies,
            )
            for task in result.task_plan
        ]

        # Create a progress message showing all planned tasks
        task_list = "\n".join(
            [f"{i+1}. {task.description}" for i, task in enumerate(task_plan)]
        )

        return Command(
            update=PartialAssistantState(
                messages=[
                    ToolCallMessage(
                        tool_call_id=tool_call_id,
                        content=f"**Task Plan Created**\n\n{result.summary}\n\n**Tasks to execute:**\n{task_list}\n\nStarting execution...",
                        artifact=result,
                    )
                ],
                task_plan=task_plan,
                plan_mode_active=True,
                current_task_id=None,
            ),
        )
