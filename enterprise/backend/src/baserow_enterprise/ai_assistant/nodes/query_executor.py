"""
Node for executing queries against Baserow API.
"""
from typing import Optional
from langchain_core.runnables import RunnableConfig

from ..graph.base import AssistantNode
from ..utils.types import (
    AssistantState,
    PartialAssistantState,
    AssistantMessage,
    VisualizationMessage,
)


class QueryExecutorNode(AssistantNode[AssistantState, PartialAssistantState]):
    """Executes queries against the Baserow API."""

    async def arun(
        self, state: AssistantState, config: RunnableConfig
    ) -> Optional[PartialAssistantState]:
        """Execute the prepared query."""
        if not state.current_query:
            return PartialAssistantState(
                messages=[AssistantMessage(content="No query to execute.")]
            )

        # In a real implementation, this would:
        # 1. Connect to Baserow API
        # 2. Execute the query/operation
        # 3. Return the results

        # For this example, we'll simulate execution
        query_type = state.query_type or "unknown"

        # Simulate API response
        mock_response = {
            "status": "success",
            "type": query_type,
            "message": f"Successfully executed {query_type} operation",
            "details": state.current_query,
        }

        # Find the last visualization message and update it
        viz_message = None
        for msg in reversed(state.messages):
            if isinstance(msg, VisualizationMessage):
                viz_message = msg
                break

        if viz_message:
            # Update the existing visualization with the answer
            viz_message.answer = mock_response
            return PartialAssistantState(
                messages=[
                    viz_message,
                    AssistantMessage(content=f"✅ {mock_response['message']}"),
                ]
            )
        else:
            return PartialAssistantState(
                messages=[
                    AssistantMessage(
                        content=f"✅ Executed query: {mock_response['message']}"
                    )
                ]
            )
