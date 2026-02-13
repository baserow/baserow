import udspy

from .prompts import AGENT_SYSTEM_PROMPT


class ChatSignature(udspy.Signature):
    __doc__ = AGENT_SYSTEM_PROMPT

    question: str = udspy.InputField()
    conversation_history: list[str] = udspy.InputField(
        desc="Previous messages formatted as '[index] (role): content', ordered chronologically"
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

    @classmethod
    def format_conversation_history(cls, history: udspy.History) -> list[str]:
        """
        Format the conversation history into a list of strings for the signature.
        """

        formatted_history = []
        for i, msg in enumerate(history.messages):
            formatted_history.append(f"[{i}] ({msg['role']}): {msg['content']}")

        return formatted_history
