from langchain_core.runnables.config import RunnableConfig
from baserow_enterprise.assistant.capabilities.base import AssistantNode
from baserow_enterprise.assistant.types import (
    AiMessage,
    AssistantState,
    PartialAssistantState,
    ToolCall,
    ToolCallMessage,
)

from .graph import DatabaseArchitectGraph
from .types import DatabaseArchitectState


class DatabaseArchitectNode(AssistantNode):
    async def arun(self, state: AssistantState, config: RunnableConfig):
        subgraph = DatabaseArchitectGraph().compile()

        result = await subgraph.ainvoke(
            DatabaseArchitectState(instructions=state.database_architect_instructions),
            config,
        )

        # Simulate a tool call to re-enter the main graph
        tool_call = ToolCall(name="handoff_to_database_architect", args={})

        return PartialAssistantState(
            database_architect_instructions="",
            messages=result["messages"]
            + [
                AiMessage(tool_calls=[tool_call]),
                ToolCallMessage(tool_call_id=tool_call.id, content="All done!"),
            ],
        )
