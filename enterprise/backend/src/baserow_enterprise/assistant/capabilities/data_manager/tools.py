from typing import Annotated, Any
from collections import defaultdict

from pydantic import BaseModel
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import InjectedToolCallId
from langchain_core.messages import AIMessage as LCAIMessage
from langchain_core.messages import HumanMessage as LCHumanMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langgraph.config import get_stream_writer
from django.db import transaction

from baserow.contrib.database.models import Database, Table
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.models import User, Workspace
from baserow_enterprise.assistant.capabilities.base import AssistantBaseTool
from .row_model_generator import (
    create_partial_row_model_from_schema,
    get_dynamic_components_for_table,
)
from baserow_enterprise.assistant.capabilities.database_architect.tools import (
    format_current_schema,
)
from baserow_enterprise.assistant.utils.helpers import (
    find_last_message_of_type,
    find_last_ui_context,
)

from .types import (
    DataManagerToolArgsSchema,
    DataManagerToolOutputSchema,
)
from .prompts import (
    DATA_MANAGER_SYSTEM_PROMPT,
    DATA_MANAGER_TOOL_DESCRIPTION,
    DATA_MANAGER_TOOL_USAGE_INSTRUCTIONS,
)

from baserow_enterprise.assistant.types import (
    ASSISTANT_GRAPH_NODE,
    THINKING_MESSAGES,
    AiInterruptMessage,
    AiThinkingMessage,
    AssistantState,
    DataExecutableOperation,
    HumanMessage,
    PartialAssistantState,
    ToolCallMessage,
    UIContext,
    CreateRowsOperation,
    UpdateRowsOperation,
    DeleteRowsOperation,
)


class DataManagerTool(AssistantBaseTool):
    name: str = "data_manager"
    description: str = DATA_MANAGER_TOOL_DESCRIPTION
    usage_instructions: str = DATA_MANAGER_TOOL_USAGE_INSTRUCTIONS
    args_schema: type[BaseModel] = DataManagerToolArgsSchema

    def _execute_data_operations(
        self,
        table: Table,
        operations: list[DataExecutableOperation],
    ) -> int:
        """
        Execute the data operations plan.
        Returns the number of rows affected.
        """

        stream_writer = get_stream_writer()
        stream_writer(
            AiThinkingMessage(
                code=THINKING_MESSAGES.CUSTOM, content="Executing data operations..."
            )
        )

        user = User.objects.get(id=self._context.chat.user.id)

        # Execute each operation
        count = 0
        for operation in operations:
            count += operation.execute(user, table)

        return count

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
                content="Analyzing data operation request...",
            )
        )

        conversation_messages = []

        # Get UI context for current database/table information
        ui_context = find_last_ui_context(state.messages)
        if ui_context and ui_context.table:
            table = Table.objects.get(id=ui_context.table.id)
            schema = format_current_schema(ui_context)
            table_schema = schema["tables"].get(ui_context.table.name)
        else:
            return Command(
                goto=ASSISTANT_GRAPH_NODE.INTERRUPT,
                update=PartialAssistantState(
                    messages=[
                        ToolCallMessage(
                            tool_call_id=tool_call_id,
                            content=(
                                "Please navigate to a specific table to perform data operations."
                            ),
                            artifact=result,
                        ),
                        AiInterruptMessage(
                            content=result.question,
                            tool_call_id=tool_call_id,
                        ),
                    ],
                    dma_needs_clarification=True,
                    dma_data_operations_plan=result.data_operations_plan,
                ),
            )

        # Get all dynamic components for this table
        dynamic_components = get_dynamic_components_for_table(table_schema)
        DynamicOutputSchema = dynamic_components["output_schema"]

        # Initialize the model with the dynamic schema
        model = init_chat_model(
            "openai:gpt-4.1-mini",
            temperature=0.2,
        )
        model = model.bind_tools(
            [{"type": "web_search_preview"}]
        ).with_structured_output(DynamicOutputSchema)

        # Check if this is a clarification response
        if state.dma_needs_clarification:
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

        # Create the prompt
        prompt = ChatPromptTemplate.from_messages(
            [
                DATA_MANAGER_SYSTEM_PROMPT,
                *conversation_messages,
            ],
            template_format="mustache",
        )

        # Create and invoke the chain
        chain = prompt | model
        result = chain.invoke(
            {
                "instructions": instructions,
            }
        )

        # If clarification is needed, interrupt for user input
        if result.need_clarification and not state.dma_needs_clarification:
            return Command(
                goto=ASSISTANT_GRAPH_NODE.INTERRUPT,
                update=PartialAssistantState(
                    messages=[
                        ToolCallMessage(
                            tool_call_id=tool_call_id,
                            content=(
                                "A clarification is needed:\n" f"{result.question}"
                            ),
                            artifact=result,
                        ),
                        AiInterruptMessage(
                            content=result.question,
                            tool_call_id=tool_call_id,
                        ),
                    ],
                    dma_needs_clarification=True,
                    dma_data_operations_plan=result.data_operations_plan,
                ),
            )

        # Execute the data operations
        rows_affected = 0
        if result.data_operations_plan:
            rows_affected = self._execute_data_operations(
                table, result.data_operations_plan
            )

        # Return success response
        success_message = result.markdown_description
        if rows_affected:
            success_message += f"\n\n**Rows affected**: {rows_affected}"

        return Command(
            update=PartialAssistantState(
                messages=[
                    ToolCallMessage(
                        tool_call_id=tool_call_id,
                        content=success_message,
                        artifact=result,
                    )
                ],
                dma_data_operations_plan=None,
                dma_needs_clarification=False,
            ),
        )
