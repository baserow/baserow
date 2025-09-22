from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import END, CompiledStateGraph, StateGraph
from baserow_enterprise.assistant.capabilities.conversation.nodes import (
    RootNode,
    RootToolNode,
    root_tools_condition,
)

from baserow_enterprise.assistant.capabilities.title_generator.nodes import (
    TitleGeneratorNode,
)

from .checkpointer import get_checkpointer

from .types import AssistantExecutionContext, AssistantState, ASSISTANT_GRAPH_NODE


class AssistantGraphBuilder:
    def __init__(self, context: AssistantExecutionContext):
        self._context = context
        self._builder = StateGraph[AssistantState](AssistantState)
        self.build()

    def build(self):
        """
        Setup the nodes for the assistant graph.
        """

        # Add nodes
        title_generator_node = TitleGeneratorNode(self._context)
        self._builder.add_node(
            ASSISTANT_GRAPH_NODE.TITLE_GENERATOR, title_generator_node
        )

        root_node = RootNode(self._context)
        self._builder.add_node(ASSISTANT_GRAPH_NODE.ROOT, root_node)

        root_tools_node = RootToolNode(self._context, tools=root_node.tools)
        self._builder.add_node(ASSISTANT_GRAPH_NODE.ROOT_TOOLS, root_tools_node)

        # Define the start node and all the edges
        self._builder.set_entry_point(ASSISTANT_GRAPH_NODE.TITLE_GENERATOR)
        self._builder.add_edge(
            ASSISTANT_GRAPH_NODE.TITLE_GENERATOR, ASSISTANT_GRAPH_NODE.ROOT
        )

        # General purpose react agent: root <--> root tools
        self._builder.add_conditional_edges(
            ASSISTANT_GRAPH_NODE.ROOT,
            root_tools_condition,
            {"tools": ASSISTANT_GRAPH_NODE.ROOT_TOOLS, "__end__": END},
        )

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

        checkpointer = checkpointer or await get_checkpointer()

        return self._builder.compile(checkpointer=checkpointer)
