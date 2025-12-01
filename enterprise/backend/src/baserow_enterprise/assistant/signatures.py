from typing import Literal

import udspy

from .prompts import AGENT_SYSTEM_PROMPT, REQUEST_ROUTER_PROMPT


class ChatSignature(udspy.Signature):
    __doc__ = AGENT_SYSTEM_PROMPT

    question: str = udspy.InputField()
    context: str = udspy.InputField(
        description="Context and facts extracted from the history to help answer the question."
    )
    ui_context: str | None = udspy.InputField(
        default=None,
        description=(
            "The JSON serialized context the user is currently in. "
            "It contains information about the user, the timezone, the workspace, etc."
            "Whenever make sense, use it to ground your answer."
        ),
    )
    answer: str = udspy.OutputField()


class RequestRouter(udspy.Signature):
    __doc__ = REQUEST_ROUTER_PROMPT

    question: str = udspy.InputField(desc="The current user question to route")
    conversation_history: list[str] = udspy.InputField(
        desc="Previous messages formatted as '[index] (role): content', ordered chronologically"
    )

    routing_decision: Literal[
        "delegate_to_agent", "search_user_docs"
    ] = udspy.OutputField(
        desc="Must be one of: 'delegate_to_agent' or 'search_user_docs'"
    )
    extracted_context: str = udspy.OutputField(
        desc=(
            "Relevant context extracted from conversation history. "
            "The agent won't see the full history, only the question and this extracted context. "
            "Always fill with comprehensive details (IDs, names, actions, specifications). "
            "Be verbose - include all relevant information to help understand the request."
        ),
    )
    search_query: str = udspy.OutputField(
        desc=(
            "The search query in English to use with search_user_docs if routing_decision='search_user_docs'. "
            "Should be a clear, well-formulated question using Baserow terminology. "
            "Empty string if routing_decision='delegate_to_agent'. "
            "If the question is in another language, make sure to mention in which "
            "language the answer should be."
        )
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
