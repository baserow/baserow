from pydantic_ai import ModelProfile
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.zai import ZaiModel
from pydantic_ai.profiles import merge_profile
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.zai import ZaiProvider
from pydantic_ai.settings import ModelSettings, ThinkingLevel, merge_model_settings

# Covers Kuma's title and the 256-token model tests, not the agents' 4k+ budgets.
SHORT_ANSWER_MAX_TOKENS = 1024


class ZaiChatProvider(ZaiProvider):
    """Z.ai's pay-as-you-go GLM API, owning its HTTP client."""

    def __init__(self, *, api_key: str) -> None:
        super().__init__(api_key=api_key)
        # The SDK fills these from OPENAI_ORG_ID/OPENAI_PROJECT_ID and sends them.
        self.client.organization = None
        self.client.project = None

    @staticmethod
    def model_profile(model_name: str) -> ModelProfile | None:
        """
        Keep requests to what Z.ai documents: only automatic tool choice and
        max_tokens, no strict tool definitions, and no file parts, which cannot
        share a request with images.

        :param model_name: The Z.ai model identifier.
        :return: The merged model profile.
        """

        return merge_profile(
            ZaiProvider.model_profile(model_name),
            OpenAIModelProfile(
                openai_supports_tool_choice_required=False,
                openai_chat_supports_max_completion_tokens=False,
                openai_supports_strict_tool_definition=False,
                openai_chat_supports_document_input=False,
            ),
        )


class ZaiChatModel(ZaiModel):
    """
    Z.ai reasons at maximum effort by default, and the reasoning can use up a short
    token cap before any answer. Short capped requests reason as little as the model
    allows, unless the caller chose a thinking level.
    """

    def prepare_request(
        self,
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> tuple[ModelSettings | None, ModelRequestParameters]:
        settings = merge_model_settings(self.settings, model_settings) or {}
        max_tokens = settings.get("max_tokens")
        if (
            max_tokens is not None
            and max_tokens <= SHORT_ANSWER_MAX_TOKENS
            and "thinking" not in settings
        ):
            settings = ModelSettings(**settings, thinking=self._lowest_thinking_level())
        return super().prepare_request(settings, model_request_parameters)

    def _lowest_thinking_level(self) -> ThinkingLevel:
        """
        Always-thinking models such as glm-5.3 ignore ``False``, so they get the
        lowest effort level instead.

        :return: The unified thinking level to send.
        """

        return "low" if self.profile.get("thinking_always_enabled", False) else False
