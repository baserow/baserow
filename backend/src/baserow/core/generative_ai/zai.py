from pydantic_ai import ModelProfile
from pydantic_ai.profiles import merge_profile
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.zai import ZaiProvider


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
