import dspy

from .prompts import ASSISTANT_SYSTEM_PROMPT


class ChatAdapter(dspy.ChatAdapter):
    def format_field_description(self, signature: type[dspy.Signature]) -> str:
        """
        This is the first part of the prompt the LLM sees, so we prepend our custom
        system prompt to it to give it the personality and context of Baserow.
        """

        field_description = super().format_field_description(signature)
        return ASSISTANT_SYSTEM_PROMPT + "## TASK INSTRUCTIONS:\n\n" + field_description
