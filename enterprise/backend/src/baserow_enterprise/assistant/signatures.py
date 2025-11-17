from typing import Any, Literal

import udspy

from .prompts import AGENT_SYSTEM_PROMPT, SMART_ROUTER_TASK_PROMPT


class ChatSignature(udspy.Signature):
    __doc__ = AGENT_SYSTEM_PROMPT

    question: str = udspy.InputField()
    context: str = udspy.InputField(
        description="Context and facts extracted from the history to help answer the question."
    )
    ui_context: dict[str, Any] | None = udspy.InputField(
        default=None,
        description=(
            "The context the user is currently in. "
            "It contains information about the user, the workspace, open table, view, etc."
            "Whenever make sense, use it to ground your answer."
        ),
    )
    answer: str = udspy.OutputField()


class SmartRequestRouter(udspy.Signature):
    __doc__ = SMART_ROUTER_TASK_PROMPT

    question: str = udspy.InputField(desc="The current user question to route")
    conversation_history: list[str] = udspy.InputField(
        desc="Previous messages formatted as '[index] (role): content', ordered chronologically"
    )
    agent_tools: list[dict[str, str]] = udspy.InputField(
        desc="List of tools available to the agent, each with 'name' and 'description'"
    )
    ui_context: dict[str, Any] | None = udspy.InputField(
        default=None,
        description=(
            "The context the user is currently in. "
            "It contains information about the user, the workspace, open table, view, etc."
            "Whenever make sense, use it to ground your answer."
        ),
    )

    routing_decision: Literal["search_docs", "delegate_to_agent"] = udspy.OutputField(
        desc="Must be one of: 'search_docs' or 'delegate_to_agent'"
    )
    search_query: str = udspy.OutputField(
        desc=(
            "The search query in English to use with search_docs if routing_decision='search_docs'. "
            "Should be a clear, well-formulated question using Baserow terminology. "
            "Empty string if routing_decision='delegate_to_agent'."
        )
    )
    extracted_context: str = udspy.OutputField(
        desc=(
            "Relevant context extracted from conversation history. "
            "Always fill with comprehensive details (IDs, names, actions, specifications). "
            "Be verbose - include all relevant information to help understand the request."
        ),
    )

    @classmethod
    def format_conversation_history(cls, history: udspy.History) -> list[str]:
        """
        Format the conversation history into a list of strings for the signature.
        """

        formatted_history = []
        for i, msg in enumerate(history.messages):
            formatted_history.append(f"[{i}] ({msg['role']}): {msg['content']}")

        return formatted_history

    @classmethod
    def format_agent_tools(cls, tools: list[udspy.Tool]) -> list[dict[str, str]]:
        """Format tools list into name/description pairs for the signature."""

        formatted_tools = []
        for tool in tools:
            formatted_tools.append(
                {
                    "name": tool.name,
                    "description": tool.desc,
                }
            )
        return formatted_tools
