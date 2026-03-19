import os

from django.conf import settings

from .registries import GenerativeAIModelType


class BaseOpenAIGenerativeAIModelType(GenerativeAIModelType):
    def get_api_key(self, workspace=None, settings_override=None):
        return (
            self.get_workspace_setting(workspace, "api_key", settings_override)
            or settings.BASEROW_OPENAI_API_KEY
        )

    def get_enabled_models(self, workspace=None, settings_override=None):
        workspace_models = self.get_workspace_setting(
            workspace, "models", settings_override
        )
        return workspace_models or settings.BASEROW_OPENAI_MODELS

    def get_organization(self, workspace=None, settings_override=None):
        return (
            self.get_workspace_setting(workspace, "organization", settings_override)
            or settings.BASEROW_OPENAI_ORGANIZATION
        )

    def get_base_url(self, workspace=None, settings_override=None):
        return None

    def is_enabled(self, workspace=None, settings_override=None):
        api_key = self.get_api_key(workspace, settings_override)
        return bool(api_key) and bool(
            self.get_enabled_models(
                workspace=workspace, settings_override=settings_override
            )
        )

    def get_ai_model(self, model_name, workspace=None, settings_override=None):
        from openai import AsyncOpenAI
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = self.get_api_key(workspace, settings_override)
        organization = self.get_organization(workspace, settings_override)
        base_url = self.get_base_url(workspace, settings_override)
        client = AsyncOpenAI(
            api_key=api_key, organization=organization, base_url=base_url
        )
        return OpenAIChatModel(
            model_name, provider=OpenAIProvider(openai_client=client)
        )

    def get_settings_serializer(self):
        from baserow.api.generative_ai.serializers import BaseOpenAISettingsSerializer

        return BaseOpenAISettingsSerializer


class OpenAIGenerativeAIModelType(BaseOpenAIGenerativeAIModelType):
    type = "openai"

    def get_settings_serializer(self):
        from baserow.api.generative_ai.serializers import OpenAISettingsSerializer

        return OpenAISettingsSerializer

    def get_base_url(self, workspace=None, settings_override=None):
        return (
            self.get_workspace_setting(workspace, "base_url", settings_override)
            or settings.BASEROW_OPENAI_BASE_URL
        )

    def is_file_compatible(self, file_name: str) -> bool:
        supported_file_extensions = {
            ".csv",
            ".doc",
            ".docx",
            ".html",
            ".json",
            ".md",
            ".pdf",
            ".pptx",
            ".txt",
            ".tex",
            ".xlsx",
            ".xls",
        }

        _, ext = os.path.splitext(file_name)
        return ext in supported_file_extensions

    def get_max_file_size(self) -> int:
        return min(512, settings.BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB)


class AnthropicGenerativeAIModelType(GenerativeAIModelType):
    type = "anthropic"

    def get_api_key(self, workspace=None, settings_override=None):
        return (
            self.get_workspace_setting(workspace, "api_key", settings_override)
            or settings.BASEROW_ANTHROPIC_API_KEY
        )

    def get_enabled_models(self, workspace=None, settings_override=None):
        workspace_models = self.get_workspace_setting(
            workspace, "models", settings_override
        )
        return workspace_models or settings.BASEROW_ANTHROPIC_MODELS

    def is_enabled(self, workspace=None, settings_override=None):
        api_key = self.get_api_key(workspace, settings_override)
        return bool(api_key) and bool(
            self.get_enabled_models(
                workspace=workspace, settings_override=settings_override
            )
        )

    def get_ai_model(self, model_name, workspace=None, settings_override=None):
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        api_key = self.get_api_key(workspace, settings_override)
        return AnthropicModel(model_name, provider=AnthropicProvider(api_key=api_key))

    def _prepare_model_settings(self, temperature=None):
        settings = {}
        if temperature is not None:
            # Anthropic only accepts temperature up to 1.0
            settings["temperature"] = min(temperature, 1)
        return settings

    def get_settings_serializer(self):
        from baserow.api.generative_ai.serializers import AnthropicSettingsSerializer

        return AnthropicSettingsSerializer


class MistralGenerativeAIModelType(GenerativeAIModelType):
    type = "mistral"

    def get_api_key(self, workspace=None, settings_override=None):
        return (
            self.get_workspace_setting(workspace, "api_key", settings_override)
            or settings.BASEROW_MISTRAL_API_KEY
        )

    def get_enabled_models(self, workspace=None, settings_override=None):
        workspace_models = self.get_workspace_setting(
            workspace, "models", settings_override
        )
        return workspace_models or settings.BASEROW_MISTRAL_MODELS

    def is_enabled(self, workspace=None, settings_override=None):
        api_key = self.get_api_key(workspace, settings_override)
        return bool(api_key) and bool(
            self.get_enabled_models(
                workspace=workspace, settings_override=settings_override
            )
        )

    def get_ai_model(self, model_name, workspace=None, settings_override=None):
        from pydantic_ai.models.mistral import MistralModel
        from pydantic_ai.providers.mistral import MistralProvider

        api_key = self.get_api_key(workspace, settings_override)
        return MistralModel(model_name, provider=MistralProvider(api_key=api_key))

    def _prepare_model_settings(self, temperature=None):
        settings = {}
        if temperature is not None:
            # Mistral only accepts temperature up to 1.0
            settings["temperature"] = min(temperature, 1)
        return settings

    def get_settings_serializer(self):
        from baserow.api.generative_ai.serializers import MistralSettingsSerializer

        return MistralSettingsSerializer


class OllamaGenerativeAIModelType(BaseOpenAIGenerativeAIModelType):
    type = "ollama"

    def get_host(self, workspace=None, settings_override=None):
        return (
            self.get_workspace_setting(workspace, "host", settings_override)
            or settings.BASEROW_OLLAMA_HOST
        )

    def get_api_key(self, workspace=None, settings_override=None):
        return "ollama"

    def get_organization(self, workspace=None, settings_override=None):
        return None

    def get_base_url(self, workspace=None, settings_override=None):
        host = self.get_host(workspace, settings_override)
        return f"{host}/v1"

    def get_enabled_models(self, workspace=None, settings_override=None):
        workspace_models = self.get_workspace_setting(
            workspace, "models", settings_override
        )
        return workspace_models or settings.BASEROW_OLLAMA_MODELS

    def is_enabled(self, workspace=None, settings_override=None):
        host = self.get_host(workspace, settings_override)
        return bool(host) and bool(
            self.get_enabled_models(workspace, settings_override)
        )

    def get_ai_model(self, model_name, workspace=None, settings_override=None):
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.ollama import OllamaProvider

        host = self.get_host(workspace, settings_override)
        return OpenAIChatModel(
            model_name, provider=OllamaProvider(base_url=f"{host}/v1")
        )

    def get_settings_serializer(self):
        from baserow.api.generative_ai.serializers import OllamaSettingsSerializer

        return OllamaSettingsSerializer


class OpenRouterGenerativeAIModelType(BaseOpenAIGenerativeAIModelType):
    """
    The OpenRouter API is compatible with the OpenAI API.
    """

    type = "openrouter"

    def get_api_key(self, workspace=None, settings_override=None):
        return (
            self.get_workspace_setting(workspace, "api_key", settings_override)
            or settings.BASEROW_OPENROUTER_API_KEY
        )

    def get_enabled_models(self, workspace=None, settings_override=None):
        workspace_models = self.get_workspace_setting(
            workspace, "models", settings_override
        )
        return workspace_models or settings.BASEROW_OPENROUTER_MODELS

    def get_organization(self, workspace=None, settings_override=None):
        return (
            self.get_workspace_setting(workspace, "organization", settings_override)
            or settings.BASEROW_OPENROUTER_ORGANIZATION
        )

    def get_base_url(self, workspace=None, settings_override=None):
        return "https://openrouter.ai/api/v1"

    def get_ai_model(self, model_name, workspace=None, settings_override=None):
        from openai import AsyncOpenAI
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openrouter import OpenRouterProvider

        api_key = self.get_api_key(workspace, settings_override)
        organization = self.get_organization(workspace, settings_override)
        client = AsyncOpenAI(
            api_key=api_key,
            organization=organization,
            base_url="https://openrouter.ai/api/v1",
        )
        return OpenAIChatModel(
            model_name, provider=OpenRouterProvider(openai_client=client)
        )

    def get_settings_serializer(self):
        from baserow.api.generative_ai.serializers import OpenRouterSettingsSerializer

        return OpenRouterSettingsSerializer
