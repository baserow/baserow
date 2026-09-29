from pydantic_ai import ModelProfile
from pydantic_ai.profiles import merge_profile
from pydantic_ai.profiles.grok import grok_model_profile
from pydantic_ai.profiles.openai import OpenAIJsonSchemaTransformer, OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider

XAI_BASE_URL = "https://api.x.ai/v1"


class XaiChatProvider(OpenAIProvider):
    """xAI's OpenAI-compatible Chat Completions API, owning its HTTP client."""

    def __init__(self, *, api_key: str) -> None:
        super().__init__(base_url=XAI_BASE_URL, api_key=api_key)
        # The SDK fills these from OPENAI_ORG_ID/OPENAI_PROJECT_ID and sends them.
        self.client.organization = None
        self.client.project = None

    @property
    def name(self) -> str:
        return "xai"

    @staticmethod
    def model_profile(model_name: str) -> ModelProfile | None:
        """
        Layer the Grok profile between OpenAI's schema handling and Chat
        Completions' lack of document input, as pydantic-ai does for Grok on
        other OpenAI-compatible providers.

        :param model_name: The xAI model identifier.
        :return: The merged model profile.
        """

        return merge_profile(
            OpenAIModelProfile(json_schema_transformer=OpenAIJsonSchemaTransformer),
            grok_model_profile(model_name),
            OpenAIModelProfile(openai_chat_supports_document_input=False),
        )
