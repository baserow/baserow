from collections import defaultdict
from typing import Literal
from typing_extensions import Annotated
from operator import add

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig

from django.db import transaction
from baserow.contrib.database.fields.actions import (
    CreateFieldActionType,
    UpdateFieldActionType,
)
from baserow.contrib.database.table.actions import CreateTableActionType
from baserow.core.actions import CreateApplicationActionType
from baserow_enterprise.assistant.graph.node import AssistantNode

from baserow_enterprise.assistant.types import (
    THINKING_MESSAGES,
    AiMessage,
    AiNavigationMessage,
    AiThinkingMessage,
    AssistantState,
    NavigateToTableArtifact,
    PartialAssistantState,
    ToolCall,
    ToolCallMessage,
)
from pydantic import BaseModel, Field
from .types import TableSchema
from .prompts import (
    PLANNER_SYSTEM_PROMPT,
    PLANNER_USER_PROMPT,
    format_previous_clarifications,
)
from langgraph.types import interrupt, Command
from langgraph.config import get_stream_writer
from langgraph.graph import StateGraph, END


def get_tools():
    return []


class DatabaseArchitectSubgraph:
    def __init__(self):
        self._builder = self.build()
        self._graph = self.compile_graph()

    def build(self):
        builder = StateGraph(DatabaseArchitectState)
        builder.add_node("planner_node", planner_node)
        builder.add_node("wait_for_clarification", wait_for_clarification)
        builder.add_node("wait_for_approval", wait_for_approval)
        builder.add_node("execute", execute)

        builder.set_entry_point("planner_node")

        # Add edges to define transitions between nodes
        # planner_node decides whether to clarify, get approval, or execute
        # wait_for_clarification goes back to planner_node
        # wait_for_approval can go to planner_node, execute, or end
        # execute ends the subgraph
        builder.add_edge("execute", END)

        return builder

    def compile_graph(self):
        return self._builder.compile()


class PlannerNodeSchema(BaseModel):
    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question to better understand their request.",
    )
    question: str = Field(
        default="",
        description="A question to ask the user to clarify the request. Only used if need_clarification is true.",
    )
    name: str = Field(
        default="New Database",
        description="Max 20 character name for the database to create.",
        max_length=20,
    )
    plan: list[TableSchema] | None = Field(
        default=None,
        description="The proposed or example database schema plan. When need_clarification is true, this is an example to help the user understand. When false, this is the final plan.",
    )
    markdown_description: str = Field(
        default="",
        description="A markdown formatted brief description of the proposed plan, to help the user understand the overall structure and ask for clarifications or approvals.",
    )
    need_approval: bool = Field(
        default=True,
        description="Whether the proposed plan needs user approval before proceeding. Always true unless explicitly asked not to.",
    )


class DatabaseArchitectState(BaseModel):
    instructions: str | None = Field(
        default=None,
        description="The user's instructions for the database schema design.",
    )

    question: str | None = Field(
        default=None,
        description="The clarifying question to ask the user. Only used if need_clarification is true.",
    )

    clarifications: Annotated[list[tuple[str, str]] | None, add] = Field(
        default=None,
        description="A list of previous (AI questions, user response) pairs to help clarify the request.",
    )

    name: str | None = Field(
        default=None,
        description="A very concise name for the database to create.",
    )

    plan: list[TableSchema] | None = Field(
        default=None,
        description="The proposed database schema plan, including tables and fields. Only used if need_clarification is false.",
    )

    markdown_description: str | None = Field(
        default=None,
        description="A markdown formatted brief description of the proposed plan, to help the user understand the overall structure and ask for clarifications or approvals.",
    )

    created_database_id: int | None = Field(
        default=None,
        description="The ID of the created database after execution.",
    )


def wait_for_clarification(
    state: DatabaseArchitectState,
) -> Command[Literal["planner_node"]]:
    """
    A placeholder node that represents waiting for user clarification.

    This node does not perform any operations. It simply returns the current state,
    indicating that the system is waiting for the user to provide additional information
    before proceeding with the database design.
    """

    user_response = interrupt(
        {
            "type": "user_input",
            "message": f"{state.markdown_description}\n\n{state.question}",
        }
    )

    return Command(
        goto="planner_node",
        update=DatabaseArchitectState(
            instructions=state.instructions,
            question="",
            clarifications=[(state.question, user_response)],
        ),
    )


def planner_node(
    state: DatabaseArchitectState, config: RunnableConfig
) -> Command[Literal["wait_for_clarification", "wait_for_approval"]]:
    """
    Main planner node that generates database schema plans.

    This node:
    1. Examines the instructions and any previous clarifications
    2. Determines if the requirements are clear enough to proceed
    3. Either asks a clarification question with an example plan, or provides the final plan
    """

    stream_writer = get_stream_writer()

    model = init_chat_model(
        model="openai:gpt-4.1-mini",
        temperature=0.3,
    )

    # Format previous clarifications if they exist
    previous_clarifications_text = ""
    if state.clarifications:
        previous_clarifications_text = format_previous_clarifications(
            state.clarifications
        )
        stream_writer(AiThinkingMessage(content=THINKING_MESSAGES.THINKING))
    else:
        stream_writer(AiThinkingMessage(content=THINKING_MESSAGES.ARCHITECTING))

    # Create the prompt
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PLANNER_SYSTEM_PROMPT),
            ("user", PLANNER_USER_PROMPT),
        ]
    )

    # Create the chain
    chain = prompt | model.with_structured_output(PlannerNodeSchema)

    # Invoke the chain
    result: PlannerNodeSchema = chain.invoke(
        {
            "instructions": state.instructions,
            "previous_clarifications": previous_clarifications_text,
        },
        config=config,
    )

    if result.need_clarification:
        return Command(
            goto="wait_for_clarification",
            update=DatabaseArchitectState(
                question=result.question,
                name=result.name,
                plan=result.plan,
                markdown_description=result.markdown_description,
            ),
        )
    elif result.need_approval:
        question = "Can I proceed with this plan? (yes/no). \n\nIf no, please provide further clarifications or write 'stop' to end the process."
        return Command(
            goto="wait_for_approval",
            update=DatabaseArchitectState(
                question=question,
                name=result.name,  # Name of the new database
                plan=result.plan,  # Final proposed plan
                markdown_description=result.markdown_description,
            ),
        )
    else:
        return Command(
            goto="execute",
            update=DatabaseArchitectState(
                question="",
                plan=result.plan,
                name=result.name,
                markdown_description=result.markdown_description,
            ),
        )


class UserFeedback(BaseModel):
    approve: bool = Field(
        description="Whether the user approves the proposed database schema plan.",
    )
    stop: bool = Field(
        description="Whether the user wants to stop the database design process.",
    )
    feedback: str = Field(
        description="Any additional feedback or clarifications from the user.",
    )


def wait_for_approval(
    state: DatabaseArchitectState,
) -> Command[Literal["planner_node", "__end__", "execute"]]:
    """
    A placeholder node that represents waiting for user approval of the proposed plan.

    This node does not perform any operations. It simply returns the current state,
    indicating that the system is waiting for the user to approve the proposed database
    schema plan before proceeding with implementation.
    """

    user_response = interrupt(
        {
            "type": "user_input",
            "message": f"{state.markdown_description}\n\n{state.question}",
        }
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Parse the user's response on the schema plan into: approve (yes/no), stop, or feedback.",
            ),
            ("user", "{user_response}"),
        ]
    )
    model = init_chat_model(
        model="openai:gpt-4.1-nano",
        temperature=0.1,
    )
    chain = prompt | model.with_structured_output(UserFeedback)
    result: UserFeedback = chain.invoke(
        {
            "user_response": user_response,
        }
    )
    if result.stop:
        return Command(
            goto="__end__",
            update=state,
        )
    elif result.approve:
        return Command(goto="execute")
    else:
        return Command(
            goto="planner_node",
            update=DatabaseArchitectState(
                question="",
                clarifications=[("Previous plan feedback", result.feedback)],
            ),
        )


def execute(
    state: DatabaseArchitectState, config: RunnableConfig
) -> DatabaseArchitectState:
    stream_writer = get_stream_writer()

    print("Executing database schema plan:")
    for table in state.plan:
        print(f" - Table: {table.name}")
        for field in table.fields:
            print(f"   - Field: {field.name} ({field.type})")

    # First let's create a new database
    configurable = config.get("configurable", {})
    user = configurable.get("user")
    workspace = configurable.get("workspace")

    database = CreateApplicationActionType.do(
        user, name=state.name, workspace=workspace, application_type="database"
    )
    table_by_name = {}
    fields_per_table = defaultdict(set)
    for table_schema in state.plan:
        stream_writer(
            AiThinkingMessage(content=f"Creating table '{table_schema.name}'...")
        )
        with transaction.atomic():
            table, _ = CreateTableActionType.do(
                user, database, table_schema.name, fill_example=False
            )
            table_by_name[table_schema.name] = table
        stream_writer(
            AiNavigationMessage(
                content=f"Created table '{table_schema.name}'.",
                artifact=NavigateToTableArtifact(
                    database_id=database.id,
                    table_id=table.id,
                    table_name=table.name,
                ),
            )
        )
        # create the primary field
        with transaction.atomic():
            primary_field = table.get_primary_field()
            UpdateFieldActionType.do(
                user,
                primary_field.specific,
                name=table_schema.primary_field.name,
            )
        fields_per_table[table_schema.name].add(table_schema.primary_field.name)
        for field in table_schema.fields:
            if field.name in fields_per_table[table_schema.name]:
                continue
            kwargs = {"name": field.name}
            if field.type == "link_row":
                linked_table = table_by_name.get(field.linked_table_name)
                if not linked_table:
                    continue
                kwargs["link_row_table"] = linked_table
            with transaction.atomic():
                CreateFieldActionType.do(user, table, field.type, **kwargs)
            fields_per_table[table_schema.name].add(field.name)

    return DatabaseArchitectState(created_database_id=database.id)


class DatabaseArchitectNode(AssistantNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._subgraph = DatabaseArchitectSubgraph().compile_graph()

    def run(
        self, state: AssistantState, config: RunnableConfig
    ) -> PartialAssistantState:
        result = self._subgraph.invoke(
            DatabaseArchitectState(instructions=state.database_architect_instructions),
            config=config,
        )

        # Create appropriate message based on what was accomplished
        content = ""
        if result.get("created_database_id"):
            content = f"Successfully created database '{result.get('name', '')}' with {len(result.get('plan', []))} tables."
            if result.get("markdown_description"):
                content += f"\n\n{result['markdown_description']}"
        elif result.get("markdown_description"):
            content = result["markdown_description"]
        else:
            content = "Database architecture planning completed."

        tool_call = ToolCall(
            name="create_database",
            args={"schema": result.get("plan", [])},
        )
        return PartialAssistantState(
            database_architect_instructions="",
            messages=[
                AiMessage(tool_calls=[tool_call], content=""),
                ToolCallMessage(content=content, tool_call_id=tool_call.id),
            ],
        )
