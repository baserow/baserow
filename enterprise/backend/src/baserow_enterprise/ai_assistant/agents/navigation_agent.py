"""Navigation agent for helping users navigate to tables."""
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage
from langgraph.prebuilt import create_react_agent
from langchain_core.runnables import RunnableConfig

from baserow_enterprise.ai_assistant.agents.prompts import (
    NAVIGATION_AGENT_SYSTEM_PROMPT,
)
from baserow_enterprise.ai_assistant.tools.table_finder import (
    TableFinderTool,
)
from django.contrib.auth.models import AbstractUser
from baserow.core.models import Workspace


class NavigationAgent:
    """Agent to help users navigate to tables in their workspace."""

    def __init__(self, user: AbstractUser, workspace: Workspace):
        self._user = user
        self._workspace = workspace

        # Create LLM
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            streaming=False,
        )

        # Create tools
        self.tools = [TableFinderTool()]

        # Create ReAct agent
        self.agent = create_react_agent(
            model=self.llm, tools=self.tools, state_modifier=self._get_system_prompt()
        )

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the navigation agent."""
        return NAVIGATION_AGENT_SYSTEM_PROMPT.format(
            workspace_id=self.workspace.id,
            workspace_name=self.workspace.name,
            user_email=self.user.email,
            user_full_name=self.user.first_name,
        )

    async def ainvoke(
        self, message: str, config: Optional[RunnableConfig] = None
    ) -> Dict[str, Any]:
        """Process a navigation request."""
        try:
            # Invoke the ReAct agent
            result = await self.agent.ainvoke(
                {"messages": [("human", message)]}, config=config
            )

            # Extract the final message
            messages = result.get("messages", [])
            if messages:
                final_message = messages[-1]
                content = (
                    final_message.content
                    if hasattr(final_message, "content")
                    else str(final_message)
                )

                # Try to extract ui_context from the response
                ui_context = self._extract_ui_context(content)

                return {
                    "message": content,
                    "ui_context": ui_context,
                    "status": "success",
                }
            else:
                return {
                    "message": "I couldn't process your navigation request. Please try again.",
                    "ui_context": None,
                    "status": "error",
                }

        except Exception as e:
            return {
                "message": f"Sorry, I encountered an error while trying to help you navigate: {str(e)}",
                "ui_context": None,
                "status": "error",
            }

    def _extract_ui_context(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract ui_context JSON from the agent's response."""
        import json
        import re

        # Look for JSON blocks in the content
        json_pattern = r"```json\s*(\{.*?\})\s*```"
        matches = re.findall(json_pattern, content, re.DOTALL)

        for match in matches:
            try:
                ui_context = json.loads(match)
                # Validate that it has the expected navigation structure
                if (
                    ui_context.get("action") == "navigate_to_table"
                    and "table_id" in ui_context
                ):
                    return ui_context
            except json.JSONDecodeError:
                continue

        return None

    def invoke(
        self, message: str, config: Optional[RunnableConfig] = None
    ) -> Dict[str, Any]:
        """Synchronous version (not recommended, use ainvoke)."""
        import asyncio

        return asyncio.run(self.ainvoke(message, config))
