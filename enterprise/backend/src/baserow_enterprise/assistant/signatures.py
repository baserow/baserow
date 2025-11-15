from typing import Any

import udspy

from .prompts import ASSISTANT_SYSTEM_PROMPT


class ChatSignature(udspy.Signature):
    __doc__ = f"{ASSISTANT_SYSTEM_PROMPT}\n TASK INSTRUCTIONS: \n"

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


class ExtractQuestionContext(udspy.Signature):
    __doc__ = (
        ASSISTANT_SYSTEM_PROMPT
        + """
    Extract relevant background information from conversation history to provide context for the current question.

    Your task:
    1. Identify facts from history that help understand or answer the current question
    2. Summarize only relevant context - omit unrelated information
    3. Preserve specific details (IDs, names, actions taken, entities created)
    4. Prioritize recent messages (higher index numbers) over older ones

    Do NOT:
    - Answer the question
    - Repeat or rephrase the question
    - Include the question in your output
    - Add information not present in the history

    Output format: A concise paragraph of relevant facts only.

    Examples:

    Question: "Add a status field to the tasks table"
    History:
      [0] user: Create a project database
      [1] assistant: Created database 'Projects' (id: 123)
      [2] user: Add a tasks table
      [3] assistant: Created table 'Tasks' (id: 456) with Name field
    Context: "Database 'Projects' (id: 123) exists. Table 'Tasks' (id: 456) was recently created with a Name field."

    Question: "Show me the latest orders"
    History:
      [0] user: Hi
      [1] assistant: Hello! How can I help?
      [2] user: What's the weather like?
      [3] assistant: I can't check weather, but I can help with Baserow.
    Context: "" (no relevant Baserow context for orders question)
    """
    )

    question: str = udspy.InputField(
        desc="The current user question needing historical context"
    )
    conversation_history: list[str] = udspy.InputField(
        desc="Previous messages formatted as '[index] (role): content', ordered chronologically"
    )
    relevant_context: str = udspy.OutputField(
        desc="Concise paragraph containing ONLY relevant facts from history. Empty string if no relevant context exists. Do not include the question itself."
    )

    @classmethod
    def format_conversation_history(cls, history: udspy.History) -> list[str]:
        formatted_history = []
        for i, msg in enumerate(history.messages):
            formatted_history.append(f"[{i}] ({msg['role']}): {msg['content']}")

        return formatted_history
