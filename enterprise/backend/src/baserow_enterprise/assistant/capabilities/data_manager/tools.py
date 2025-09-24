import json
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

from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_batch_row_serializer_class,
    get_row_serializer_class,
)
from baserow.contrib.database.api.rows.views import build_response_with_metadata
from baserow.contrib.database.models import Database, Table
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.models import User, Workspace
from baserow_enterprise.assistant.capabilities.base import AssistantBaseTool

from .row_model_generator import (
    get_dynamic_components_for_table,
)
from baserow_enterprise.assistant.capabilities.database_architect.utils import (
    get_database_schema,
    get_table_schema,
    get_workspace_schema,
)
from baserow_enterprise.assistant.utils.helpers import (
    find_last_message_of_type,
    find_last_ui_context,
)

from .types import (
    DataManagerToolArgsSchema,
    GetDatabaseSchemaToolArgsSchema,
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
        table_id: int,
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

        if not table_id:
            raise ValueError("Table ID must be provided or available in UI context.")

        table = Table.objects.get(id=table_id)
        table_schema = get_table_schema(table)

        # Get all dynamic components for this table
        dynamic_components = get_dynamic_components_for_table(table_schema)
        DynamicOutputSchema = dynamic_components["output_schema"]

        table_model = table.get_model()
        response_row_serializer_class = get_row_serializer_class(
            table_model, RowSerializer, is_response=True, user_field_names=True
        )
        response_serializer_class = get_batch_row_serializer_class(
            response_row_serializer_class
        )

        example_rows = response_serializer_class(
            {"items": table_model.objects.all()[:10]}
        ).data

        # Initialize the model with the dynamic schema
        model = init_chat_model(
            "openai:gpt-5-mini",
            # temperature=0.2,
            reasoning={
                "effort": "low",  # 'low', 'medium', or 'high'
                # "summary": "auto",  # 'detailed', 'auto', or None
            },
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
                "example_rows": example_rows,
            }
        )

        # If clarification is needed, interrupt for user input
        if result.need_clarification and result.question:
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
            success_message += f"\n\n**Done!**: {rows_affected} rows affected."

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


class GetDatabaseSchemaTool(AssistantBaseTool):
    name: str = "get_database_schema"
    description: str = (
        "Get the schema of a database, including IDs and names of tables and fields."
    )
    usage_instructions: str = """
Use this tool to retrieve the schema of a specific database, including IDs and names of tables and fields.

Make sure to have a valid database ID from the current workspace before calling this tool.
You can get the database ID by using the get_workspace_schema tool.
"""
    args_schema: type[BaseModel] = GetDatabaseSchemaToolArgsSchema

    def _run_impl(
        self,
        tool_call_id: Annotated[str, InjectedToolCallId],
        state: Annotated[AssistantState, InjectedState],
        relations_only: bool = False,
    ) -> Command:
        user = User.objects.get(id=self._context.chat.user.id)
        workspace_id = self._context.chat.workspace.id
        workspace = Workspace.objects.get(id=self._context.chat.workspace.id)
        workspace_schema = get_workspace_schema(workspace)

        ui_context = state.ui_context or find_last_ui_context(state.messages)
        if (
            ui_context
            and ui_context.application
            and ui_context.application.type == "database"
        ):
            database_id = ui_context.application.id

            database = Database.objects.filter(
                id=database_id, workspace_id=workspace_id
            ).first()
            if database:
                database_schema = get_database_schema(
                    database, relations_only=relations_only
                )
                workspace_schema.current_database = database_schema

        return Command(
            update=PartialAssistantState(
                messages=[
                    ToolCallMessage(
                        tool_call_id=tool_call_id,
                        content=workspace_schema.model_dump_json(indent=2),
                        artifact=workspace_schema,
                    )
                ],
            ),
        )
