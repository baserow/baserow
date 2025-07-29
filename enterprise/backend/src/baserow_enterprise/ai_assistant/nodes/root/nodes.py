"""
Root node for initial routing decisions.
"""
from typing import Optional
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from baserow_enterprise.ai_assistant.nodes.root.prompts import ROOT_SYSTEM_PROMPT

from ...graph.base import AssistantNode
from ...utils.types import AssistantState, PartialAssistantState, AssistantMessage


class RootNode(AssistantNode[AssistantState, PartialAssistantState]):
    """Analyzes user intent and determines routing."""

    def __init__(
        self, workspace_id: Optional[int] = None, message_window_size: int = 10
    ):
        """Initialize with configurable message window size."""
        super().__init__(workspace_id)
        self.message_window_size = message_window_size

    def _get_message_window(self, state: AssistantState) -> list:
        """Get the last N messages for context."""
        messages = state.messages or []
        # Return last N messages, maintaining chronological order
        return messages[-self.message_window_size :] if messages else []

    def _format_messages_for_prompt(self, messages: list) -> list:
        """Format message window for the prompt."""
        formatted_messages = []
        for msg in messages:
            if hasattr(msg, "role") and hasattr(msg, "content"):
                role = msg.role
            elif hasattr(msg, "__class__"):
                # Determine role from message type
                class_name = msg.__class__.__name__
                if "Human" in class_name:
                    role = "human"
                elif "Assistant" in class_name or "AI" in class_name:
                    role = "assistant"
                else:
                    role = "system"
            else:
                role = "human"

            formatted_messages.append((role, msg.content))

        return formatted_messages

    async def arun(
        self, state: AssistantState, config: RunnableConfig
    ) -> Optional[PartialAssistantState]:
        """Analyze the user's request with conversation context."""
        # Get message window for context
        message_window = self._get_message_window(state)
        if not message_window:
            return None

        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.2,
            streaming=True,
            stream_usage=True,
        )

        prompt_messages = [("system", ROOT_SYSTEM_PROMPT)]

        # Add conversation history
        formatted_history = self._format_messages_for_prompt(message_window)
        prompt_messages.extend(formatted_history)

        prompt = ChatPromptTemplate.from_messages(prompt_messages)

        chain = prompt | llm
        response = await chain.ainvoke({"ui_context": {}})

        # Check if this is a navigation request
        content_lower = response.content.lower()
        is_navigation = any(keyword in content_lower for keyword in [
            "navigate", "go to", "find table", "table", "show me", "take me to", 
            "open", "switch to", "access"
        ])
        
        partial_state = PartialAssistantState(
            messages=[AssistantMessage(content=response.content)],
        )
        
        # Set routing hint for navigation requests
        if is_navigation:
            partial_state.next_action = "navigation"
        
        return partial_state


class RootToolsNode(AssistantNode[AssistantState, PartialAssistantState]):
    """Executes tools based on the plan."""

    def router(self, state: AssistantState) -> str:
        """Route based on the plan content."""

        last_message = state.messages[-1]
        # if isinstance(last_message, AssistantToolCallMessage):
        #     return "root"  # Let the root either proceed or finish, since it now can see the tool call result

        if not state.plan:
            return "end"

        plan_lower = state.plan.lower()

        if "table" in plan_lower:
            return "table"
        elif "view" in plan_lower:
            return "view"
        elif "formula" in plan_lower:
            return "formula"
        elif "filter" in plan_lower:
            return "filter"
        elif "analyze" in plan_lower or "query" in plan_lower:
            return "planner"
        else:
            return "end"

    async def arun(
        self, state: AssistantState, config: RunnableConfig
    ) -> Optional[PartialAssistantState]:
        """Prepare for tool execution."""
        return PartialAssistantState(next_action=self.router(state))
