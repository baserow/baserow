from enum import StrEnum

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph, StateGraph, END

from baserow_enterprise.assistant.checkpointer import get_checkpointer
from baserow_enterprise.assistant.graph.tool import tools_condition
from baserow_enterprise.assistant.models import AssistantChat
from .root.nodes import RootNode, RootToolsNode
from .title_generator.nodes import (
    TitleGeneratorNode,
)

from baserow_enterprise.assistant.types import AssistantState


class Node(StrEnum):
    TITLE_GENERATOR = "title_generator"
    ROOT = "root"
    ROOT_TOOLS = "root_tools"
    TABLE_ARCHITECT_PLANNER = "table_architect_planner"
    TABLE_ARCHITECT_EXECUTOR = "table_architect_executor"
    TABLE_ARCHITECT_TOOLS = "table_architect_tools"


class AssistantGraphBuilder:
    def __init__(self, chat: AssistantChat):
        self._chat = chat
        self._user = chat.user
        self._workspace = chat.workspace
        self._builder = StateGraph[AssistantState](AssistantState)

    def build(self):
        """
        Setup the nodes for the assistant graph.
        """

        # Add nodes
        title_generator_node = TitleGeneratorNode(self._chat)
        self._builder.add_node(Node.TITLE_GENERATOR, title_generator_node)

        root_node = RootNode(self._chat)
        self._builder.add_node(Node.ROOT, root_node)

        root_tools_node = RootToolsNode(self._chat)
        self._builder.add_node(Node.ROOT_TOOLS, root_tools_node)

        # Define the start node and all the edges
        self._builder.set_entry_point(Node.TITLE_GENERATOR)
        self._builder.add_edge(Node.TITLE_GENERATOR, Node.ROOT)

        # General purpose agent: root <--> tools
        self._builder.add_conditional_edges(
            Node.ROOT,
            tools_condition,
            {"tools": Node.ROOT_TOOLS, "__end__": END},
        )

        self._builder.add_edge(Node.ROOT_TOOLS, Node.ROOT)

    async def compile_full_graph(
        self, checkpointer: BaseCheckpointSaver = None
    ) -> CompiledStateGraph[AssistantState]:
        """
        Compile the full assistant graph setting the checkpointer to persist state. Once
        all the nodes and edges have been added, this method compiles the graph into a
        `CompiledStateGraph` that can be executed. It also sets up the checkpointer to
        ensure that the state of the graph is saved and can be resumed in case of
        failures or interruptions for human-like interactions.

        :param checkpointer: The checkpoint saver to use for persisting state.
        :return: The compiled state graph to use for the assistant.
        """

        self.build()
        checkpointer = checkpointer or await get_checkpointer()

        return self._builder.compile(checkpointer=checkpointer)
