from enum import StrEnum
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.types import Command

from baserow_enterprise.assistant.checkpointer import get_checkpointer
from baserow_enterprise.assistant.models import AssistantChat
from baserow_enterprise.assistant.nodes.root.nodes import RootNode
from baserow_enterprise.assistant.nodes.title_generator.nodes import TitleGeneratorNode
from baserow_enterprise.assistant.types import AssistantState


class Node(StrEnum):
    START = "start"
    TITLE_GENERATOR = "title_generator"
    ROOT = "root"


class AssistantGraph:
    def __init__(self, chat: AssistantChat):
        self.chat = chat
        self.user = chat.user
        self.workspace = chat.workspace
        self.builder = StateGraph[AssistantState](AssistantState)

    def add_nodes(self):
        """
        Setup the nodes for the assistant graph.
        """

        title_generator_node = TitleGeneratorNode(self.chat)
        self.builder.add_node(Node.TITLE_GENERATOR, title_generator_node)

        root_node = RootNode(self.chat)
        self.builder.add_node(Node.ROOT, root_node)

        def start_dispatcher(
            state: AssistantState,
        ) -> Command[Literal[Node.TITLE_GENERATOR, Node.ROOT]]:
            return [
                Command(goto=Node.TITLE_GENERATOR),
                Command(goto=Node.ROOT),
            ]

        self.builder.add_node(Node.START, start_dispatcher)

    def add_edges(self):
        """
        Setup the edges for the assistant graph.
        """

        self.builder.set_entry_point(Node.START)

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

        self.add_nodes()
        self.add_edges()
        checkpointer = checkpointer or await get_checkpointer()

        return self.builder.compile(checkpointer=checkpointer)
