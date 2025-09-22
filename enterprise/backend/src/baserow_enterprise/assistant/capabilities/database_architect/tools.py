from typing import Annotated, Any
from langgraph.types import Command
from baserow_enterprise.assistant.capabilities.base import AssistantBaseTool
from pydantic import BaseModel
from langchain_core.tools import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import Command
from langgraph.config import get_stream_writer
from langchain_core.messages import AIMessage as LCAIMessage
from langchain_core.messages import HumanMessage as LCHumanMessage

from baserow_enterprise.assistant.utils.helpers import find_last_message_of_type

from .types import DatabaseArchitectToolArgsSchema, DatabaseArchitectToolOutputSchema
from .prompts import (
    DATABASE_ARCHITECT_TOOL_DESCRIPTION,
    DATABASE_ARCHITECT_TOOL_USAGE_INSTRUCTIONS,
    PLANNER_SYSTEM_PROMPT,
    format_current_schema,
)

from baserow_enterprise.assistant.types import (
    ASSISTANT_GRAPH_NODE,
    THINKING_MESSAGES,
    AiInterruptMessage,
    AiThinkingMessage,
    AssistantState,
    HumanMessage,
    PartialAssistantState,
    ToolCallMessage,
)


class DatabaseArchitectTool(AssistantBaseTool):
    name: str = "database_architect"
    description: str = DATABASE_ARCHITECT_TOOL_DESCRIPTION
    usage_instructions: str = DATABASE_ARCHITECT_TOOL_USAGE_INSTRUCTIONS
    args_schema: type[BaseModel] = DatabaseArchitectToolArgsSchema

    def _run_impl(
        self,
        instructions: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
        state: Annotated[AssistantState, InjectedState],
    ) -> Any:
        stream_writer = get_stream_writer()
        stream_writer(AiThinkingMessage(code=THINKING_MESSAGES.DESIGN_SCHEMA))

        model = init_chat_model(
            "openai:gpt-4.1",
            temperature=0.3,
        )
        model = model.with_structured_output(DatabaseArchitectToolOutputSchema)

        conversation_messages = []
        if state.dba_schema_operations_plan:
            formatted_operations = "\n".join(
                [
                    f"- {op.__class__.__name__}: {op.model_dump_json()}"
                    for op in state.dba_schema_operations_plan
                ]
            )
            conversation_messages.append(
                LCAIMessage(
                    content=(
                        "## Current proposed plan:\n\n" f"{formatted_operations}\n\n"
                    )
                )
            )
        if state.dba_needs_clarification:
            clarification_msg = find_last_message_of_type(
                state.messages, AiInterruptMessage
            )
            human_response = find_last_message_of_type(state.messages, HumanMessage)
            conversation_messages.extend(
                [
                    LCAIMessage(content=clarification_msg.content),
                    LCHumanMessage(content=human_response.content),
                ]
            )

        prompt = ChatPromptTemplate.from_messages(
            [
                PLANNER_SYSTEM_PROMPT,
                *conversation_messages,
            ],
            template_format="mustache",
        )
        chain = prompt | model

        result: DatabaseArchitectToolOutputSchema = chain.invoke(
            {
                "instructions": instructions,
                "current_schema": format_current_schema(state.dba_current_schema),
            }
        )

        if result.need_clarification:
            return Command(
                goto=ASSISTANT_GRAPH_NODE.INTERRUPT,
                update=PartialAssistantState(
                    messages=[
                        ToolCallMessage(
                            tool_call_id=tool_call_id,
                            content=(
                                "A clarification is needed before proceeding:\n"
                                f"{result.question}"
                            ),
                            artifact=result,
                        ),
                        AiInterruptMessage(
                            content=result.question,
                            tool_call_id=tool_call_id,
                        ),
                    ],
                ),
            )

        # No clarification needed, let's execute the plan

        stream_writer(AiThinkingMessage(code=THINKING_MESSAGES.IMPLEMENT_SCHEMA))

        return Command(
            update=PartialAssistantState(
                messages=[
                    ToolCallMessage(
                        tool_call_id=tool_call_id,
                        content=("Done. Follow-up questions:\n" f"{result.question}"),
                        artifact=result,
                    )
                ],
                dba_markdown_plan_description=None,
                dba_schema_operations_plan=None,
            ),
        )
