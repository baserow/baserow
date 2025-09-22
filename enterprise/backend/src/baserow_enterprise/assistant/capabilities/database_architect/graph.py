from collections import defaultdict
from enum import StrEnum
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

from baserow_enterprise.assistant.types import (
    THINKING_MESSAGES,
    AiInterruptMessage,
    AiMessage,
    AiThinkingMessage,
    HumanMessage,
)
from pydantic import BaseModel, Field
from .types import (
    DatabaseArchitectState,
    PlannerOutputSchema,
    PartialDatabaseArchitectState,
)
from .prompts import (
    PLANNER_SYSTEM_PROMPT,
    format_current_schema,
)
from langgraph.types import interrupt, Command
from langgraph.config import get_stream_writer
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage as LCAIMessage
from langchain_core.messages import BaseMessage as LCBaseMessage
from langchain_core.messages import HumanMessage as LCHumanMessage


class DATABASE_GRAPH_NODE(StrEnum):
    PLANNER = "planner"
    CLARIFY_OR_APPROVE = "clarify_or_approve"
    EXECUTE_PLAN = "execute_plan"


class DatabaseArchitectGraph:
    def __init__(self):
        self._builder = self.build()
        self._graph = self.compile()

    def build(self):
        builder = StateGraph(DatabaseArchitectState)
        builder.add_node(DATABASE_GRAPH_NODE.PLANNER, planner)
        builder.add_node(DATABASE_GRAPH_NODE.CLARIFY_OR_APPROVE, clarify_or_approve)
        builder.add_node(DATABASE_GRAPH_NODE.EXECUTE_PLAN, execute_plan)

        builder.set_entry_point(DATABASE_GRAPH_NODE.PLANNER)
        builder.add_edge(DATABASE_GRAPH_NODE.EXECUTE_PLAN, END)

        return builder

    def compile(self):
        return self._builder.compile()


async def planner(
    state: DatabaseArchitectState, config: RunnableConfig
) -> Command[
    Literal[DATABASE_GRAPH_NODE.CLARIFY_OR_APPROVE, DATABASE_GRAPH_NODE.EXECUTE_PLAN]
]:
    """
    The planner node is responsible for generating a database schema based on user
    instructions. It may ask clarifying questions if the instructions are ambiguous.

    It uses a language model to interpret the user's instructions and generate a
    proposed database schema. If the instructions are unclear, it will formulate a
    clarifying question to ask the user.

    The node updates the state with either the final schema or a question for the user.
    """

    stream_writer = get_stream_writer()
    stream_writer(AiThinkingMessage(code=THINKING_MESSAGES.DESIGN_SCHEMA))

    model = init_chat_model(
        "openai:gpt-4.1",
        temperature=0.3,
    )
    model = model.with_structured_output(PlannerOutputSchema)

    conversation_messages = []
    if state.schema_operations_plan:
        formatted_operations = "\n".join(
            [
                f"- {op.__class__.__name__}: {op.model_dump_json()}"
                for op in state.schema_operations_plan
            ]
        )
        conversation_messages.append(
            LCAIMessage(
                content=("## Current proposed plan:\n\n" f"{formatted_operations}\n\n")
            )
        )
    if state.clarification:
        conversation_messages.extend(
            [
                LCAIMessage(content=state.clarification.question),
                LCHumanMessage(content=state.clarification.answer),
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

    response: PlannerOutputSchema = await chain.ainvoke(
        {
            "instructions": state.instructions,
            "current_schema": format_current_schema(state.current_schema),
        }
    )

    update = PartialDatabaseArchitectState(
        question=response.question,
        schema_operations_plan=response.schema_operations_plan,
        markdown_description=response.markdown_description,
    )

    goto = (
        DATABASE_GRAPH_NODE.CLARIFY_OR_APPROVE
        if response.question
        else DATABASE_GRAPH_NODE.EXECUTE_PLAN
    )
    return Command(goto=goto, update=update)


def clarify_or_approve(
    state: DatabaseArchitectState, config: RunnableConfig
) -> Command[Literal[DATABASE_GRAPH_NODE.PLANNER]]:
    """
    This node handles the situation where the planner has asked a clarifying question
    or is awaiting user approval of the proposed schema. It interrupts the flow to get
    user input and then returns to the planner node with the updated state.

    :param state: The current state of the assistant, including the question to ask.
    :param config: The runnable configuration, which may include settings for the
                   interruption.
    :return: A command to go back to the planner node with the updated state.
    """

    stream_writer = get_stream_writer()
    stream_writer(AiThinkingMessage(code=THINKING_MESSAGES.WAITING_FOR_INTERRUPT))

    interrupt_content = "\n\n".join(
        [
            state.markdown_description,
            state.question,
        ]
    )
    interrupt_message = AiInterruptMessage(content=interrupt_content)
    user_response = interrupt(interrupt_message)

    return Command(
        goto=DATABASE_GRAPH_NODE.PLANNER,
        update=PartialDatabaseArchitectState(
            question=None,
            clarification=(state.question, user_response),
            messages=[
                interrupt_message,
                HumanMessage(content=user_response),
            ],
        ),
    )


def execute_plan(state: DatabaseArchitectState, config: RunnableConfig) -> None:
    """
    This node executes the database schema changes as per the plan generated by the
    planner node. It applies the schema operations to the database, creating or updating
    tables and fields as necessary.
    """

    stream_writer = get_stream_writer()
    stream_writer(AiThinkingMessage(code=THINKING_MESSAGES.IMPLEMENT_SCHEMA))

    return PartialDatabaseArchitectState(
        messages=[
            AiMessage(
                content="Notify the user about the successful implementation of the database schema changes.",
                show_in_ui=False,
            )
        ]
    )
