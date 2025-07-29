"""
Type definitions for the Baserow Assistant.
"""
from typing import Annotated, Sequence, Optional, TypedDict, Union, Literal
from enum import StrEnum
from pydantic import BaseModel, Field
import uuid
from langgraph.graph import END, START, add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage


# Message types


class VisualizationMessage(BaseMessage):
    """Custom message type for visualizations that extends LangChain's BaseMessage."""

    type: Literal["visualization"] = "visualization"
    query: dict
    answer: Optional[dict] = None

    def __init__(self, query: dict, answer: Optional[dict] = None, **kwargs):
        # BaseMessage expects 'content' field
        content = {
            "type": "visualization",
            "query": query,
            "answer": answer or {},
        }
        super().__init__(content=content, **kwargs)


class FailureMessage(BaseModel):
    type: Literal["failure"] = "failure"
    content: str = "An error occurred"
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))


AnyAssistantMessage = Union[
    HumanMessage, AIMessage, VisualizationMessage, FailureMessage
]


class SharedAssistantState(TypedDict):
    undoable_action_group_id: str
    """
    The action group ID for the last undoable action.
    """


class AssistantState(SharedAssistantState):
    """Main state for the assistant."""

    messages: Annotated[Sequence[AnyAssistantMessage], add_messages] = Field(default=[])


class PartialAssistantState(SharedAssistantState):
    """Partial state updates from nodes."""

    messages: Sequence[AnyAssistantMessage] = Field(default=[])


class AssistantNodeName(StrEnum):
    """Node names in the graph."""

    START = START
    END = END
    ROOT = "root"
    ROOT_TOOLS = "root_tools"
    NAVIGATION = "navigation"
    PLANNER = "planner"
    TABLE_CREATOR = "table_creator"
    VIEW_CREATOR = "view_creator"
    FORMULA_GENERATOR = "formula_generator"
    FILTER_BUILDER = "filter_builder"
    QUERY_EXECUTOR = "query_executor"
