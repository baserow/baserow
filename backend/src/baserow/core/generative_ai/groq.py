"""Preserve GPT-OSS reasoning in Groq's native conversation format."""

from dataclasses import replace
from typing import Any

from groq.types import chat
from pydantic_ai.messages import ModelMessage, ModelResponse, ThinkingPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.groq import GroqModel

from .model_profiles import AGENT, DOCUMENTATION, SUBAGENT
from .output_validation import validate_tool_call_output
from .registries import GenerativeAIModelConfiguration


def sanitize_gpt_oss_model_settings(model_settings: dict[str, Any]) -> dict[str, Any]:
    """Send GPT-OSS reasoning effort without its unsupported reasoning format."""

    from pydantic_ai.profiles.groq import GROQ_GPT_OSS_REASONING_EFFORT_MAP

    result = dict(model_settings)
    thinking = result.pop("thinking", None)
    result.pop("groq_reasoning_format", None)
    if thinking is not None and result.get("groq_reasoning_effort") is None:
        # The SDK's unified setting also sends reasoning_format='parsed', which
        # GPT-OSS rejects. Preserve its effort mapping through the provider setting.
        if thinking is True:
            thinking = "medium"
        elif thinking is False:
            thinking = "low"
        result["groq_reasoning_effort"] = GROQ_GPT_OSS_REASONING_EFFORT_MAP[thinking]
    return result


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


_GPT_OSS_CONFIGURATION = GenerativeAIModelConfiguration(
    model_class=GroqGPTOSSModel,
    settings_overrides={AGENT: {"max_tokens": 16384}},
    output_validator=validate_tool_call_output,
    settings_sanitizer=sanitize_gpt_oss_model_settings,
)
_LEGACY_REASONING_OVERRIDES = {
    SUBAGENT: {"extra_body": {"reasoning_effort": "high"}},
    DOCUMENTATION: {"extra_body": {"reasoning_effort": "high"}},
}

MODEL_CONFIGURATIONS = {
    "openai/gpt-oss-20b": _GPT_OSS_CONFIGURATION,
    "openai/gpt-oss-120b": replace(
        _GPT_OSS_CONFIGURATION,
        settings_overrides={
            **_GPT_OSS_CONFIGURATION.settings_overrides,
            **_LEGACY_REASONING_OVERRIDES,
        },
    ),
}
# Kuma's historical settings lookup accepts shortened/custom-path model names.
# Those aliases retain settings only, without enabling the exact-model adapters.
LEGACY_MODEL_CONFIGURATIONS = {
    "gpt-oss-120b": GenerativeAIModelConfiguration(
        settings_overrides=_LEGACY_REASONING_OVERRIDES
    )
}
