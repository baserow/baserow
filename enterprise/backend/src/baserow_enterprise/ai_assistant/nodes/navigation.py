"""Navigation node for table navigation assistance."""
from typing import Optional
from langchain_core.runnables import RunnableConfig

from ..graph.base import AssistantNode
from ..utils.types import AssistantState, PartialAssistantState, AssistantMessage
from ..agents.navigation_agent import create_navigation_agent


class NavigationNode(AssistantNode[AssistantState, PartialAssistantState]):
    """Node that handles navigation requests using the navigation agent."""

    async def arun(
        self, state: AssistantState, config: RunnableConfig
    ) -> Optional[PartialAssistantState]:
        """Handle navigation requests."""
        
        # Get the last human message
        user_message = self._get_last_human_message(state)
        if not user_message:
            return None

        # Create navigation agent
        navigation_agent = create_navigation_agent(self.workspace_id)
        
        # Process the navigation request
        result = await navigation_agent.ainvoke(user_message, config)
        
        # Create response message
        response_message = AssistantMessage(content=result["message"])
        
        # Prepare the partial state
        partial_state = PartialAssistantState(
            messages=[response_message]
        )
        
        # Add ui_context if available
        if result.get("ui_context"):
            partial_state.ui_context = result["ui_context"]
        
        return partial_state