from collections import defaultdict
from typing import Annotated, Any
from langgraph.types import Command
from baserow.contrib.database.models import Database
from baserow.core.handler import CoreHandler
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
from django.db import transaction
from baserow.core.models import User, Workspace

from baserow_enterprise.assistant.utils.helpers import (
    find_last_message_of_type,
    find_last_ui_context,
)

from .types import (
    AnySchemaOperation,
    DatabaseArchitectToolArgsSchema,
    DatabaseArchitectToolOutputSchema,
)
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
    TableOperation,
    UiNavigationMessage,
    AiThinkingMessage,
    AssistantState,
    HumanMessage,
    NavigateToOperation,
    PartialAssistantState,
    StreamableOperation,
    ToolCallMessage,
    UIContext,
)


class DatabaseArchitectTool(AssistantBaseTool):
    name: str = "database_architect"
    description: str = DATABASE_ARCHITECT_TOOL_DESCRIPTION
    usage_instructions: str = DATABASE_ARCHITECT_TOOL_USAGE_INSTRUCTIONS
    args_schema: type[BaseModel] = DatabaseArchitectToolArgsSchema

    def _execute_plan(
        self,
        plan: list[AnySchemaOperation],
        ui_context: UIContext | None = None,
        new_database_name: str | None = None,
    ) -> None:
        """
        Placeholder for executing the schema operations plan.
        In a real implementation, this would interact with Baserow's backend to
        apply the schema changes.
        """

        stream_writer = get_stream_writer()
        stream_writer(AiThinkingMessage(code=THINKING_MESSAGES.IMPLEMENT_SCHEMA))

        user = User.objects.get(id=self._context.chat.user.id)
        workspace = Workspace.objects.get(id=self._context.chat.workspace.id)

        database = None
        if (
            not new_database_name
            and ui_context
            and ui_context.application
            and ui_context.application.type == "database"
        ):
            database = Database.objects.filter(id=ui_context.application.id).first()

        if not database:
            with transaction.atomic():
                database = CoreHandler().create_application(
                    user,
                    workspace,
                    "database",
                    name=new_database_name or "New Database",
                )

        resource_mapping = defaultdict(dict)
        resource_mapping["database"][database.name] = database
        resource_mapping["workspace"][workspace.name] = workspace

        table_operations = []
        field_operations = []

        def _reorder_plan():
            for operation in plan:
                if isinstance(operation, TableOperation):
                    table_operations.append(operation)
                else:
                    field_operations.append(operation)
            return table_operations + field_operations

        navigate_args = None
        for operation in _reorder_plan():
            if isinstance(operation, StreamableOperation):
                message = operation.get_streaming_message()
                stream_writer(
                    AiThinkingMessage(code=THINKING_MESSAGES.CUSTOM, content=message)
                )
            operation.execute(user, resource_mapping)
            if not navigate_args and isinstance(operation, NavigateToOperation):
                navigate_args = operation.get_navigation_args(resource_mapping)

        if navigate_args:
            stream_writer(UiNavigationMessage(args=navigate_args))

    def _run_impl(
        self,
        instructions: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
        state: Annotated[AssistantState, InjectedState],
    ) -> Any:
        stream_writer = get_stream_writer()
        stream_writer(AiThinkingMessage(code=THINKING_MESSAGES.DESIGN_SCHEMA))

        model = init_chat_model(
            "openai:gpt-4.1-mini",
            temperature=0.3,
        )
        model = model.bind_tools(
            [{"type": "web_search_preview"}]
        ).with_structured_output(DatabaseArchitectToolOutputSchema)

        conversation_messages = []

        ui_context = find_last_ui_context(state.messages)
        if (
            ui_context
            and ui_context.application
            and ui_context.application.type == "database"
        ):
            conversation_messages.append(
                LCAIMessage(
                    content=(
                        "## Current database schema:\n\n"
                        f"{format_current_schema(ui_context)}\n\n"
                    )
                )
            )

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
            }
        )

        # Don't keep asking for clarification if we already did
        if result.need_clarification and not state.dba_needs_clarification:
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
                    dba_needs_clarification=True,
                    dba_schema_operations_plan=result.schema_operations_plan,
                ),
            )

        # No clarification needed, let's execute the plan
        self._execute_plan(
            result.schema_operations_plan, ui_context, result.new_database_name
        )

        return Command(
            update=PartialAssistantState(
                messages=[
                    ToolCallMessage(
                        tool_call_id=tool_call_id,
                        content=("Done. Follow-up questions:\n" f"{result.question}"),
                        artifact=result,
                    )
                ],
                dba_schema_operations_plan=None,
                dba_needs_clarification=None,
            ),
        )
