"""Preserve GPT-OSS reasoning in Groq's native conversation format."""

from dataclasses import replace

from groq.types import chat
from pydantic_ai.messages import ModelMessage, ModelResponse, ThinkingPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.groq import GroqModel


class GroqGPTOSSModel(GroqModel):
    async def _map_messages(
        self,
        messages: list[ModelMessage],
        model_request_parameters: ModelRequestParameters,
    ) -> list[chat.ChatCompletionMessageParam]:
        # Pydantic AI currently places ThinkingPart inside <think> tags in content.
        # GPT-OSS has a separate reasoning channel: replaying it as visible text
        # can produce malformed final/tool responses. Keep the typed history intact
        # and let the SDK map everything except reasoning as usual.
        without_reasoning = [
            replace(
                message,
                parts=[
                    part for part in message.parts if not isinstance(part, ThinkingPart)
                ],
            )
            if isinstance(message, ModelResponse)
            else message
            for message in messages
        ]
        mapped = await super()._map_messages(
            without_reasoning, model_request_parameters
        )
        responses = (
            message for message in messages if isinstance(message, ModelResponse)
        )
        assistants = (message for message in mapped if message["role"] == "assistant")
        for response, assistant in zip(responses, assistants, strict=True):
            reasoning = [
                part.content
                for part in response.parts
                if isinstance(part, ThinkingPart)
            ]
            if reasoning:
                assistant["reasoning"] = "\n\n".join(reasoning)
        return mapped
