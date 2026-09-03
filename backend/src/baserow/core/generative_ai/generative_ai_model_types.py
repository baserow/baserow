from __future__ import annotations

import re
from functools import cached_property
from typing import TYPE_CHECKING, Any, Optional

from django.conf import settings

from baserow.core.ai_provider.resolution import ScopedAIProviderState
from baserow.core.models import Workspace

from .registries import FileHandler, GenerativeAIModelType, get_known_model_names

if TYPE_CHECKING:
    from baserow_premium.fields.ai_file import AIFile


_IMAGE_EXTENSIONS = {".gif", ".jpg", ".jpeg", ".png", ".webp"}
_TEXT_EXTENSIONS = {".csv", ".html", ".json", ".md", ".txt", ".tex"}
_GOOGLE_DISCOVERY_EXCLUDED_MODELS = {
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-preview-09-2025",
    "gemini-3-pro-preview",
}
_GROQ_DISCOVERY_EXCLUDED_MODELS = {
    # Retired for Groq's free and developer tiers on 2026-08-16. Customers
    # with a committed-spend agreement can still enter these IDs manually.
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
}
_GOOGLE_SAMPLING_SETTINGS = {"temperature", "top_p", "top_k"}
_GOOGLE_MODEL_VERSION_PATTERN = re.compile(
    r"^gemini-(?P<major>\d+)(?:\.(?P<minor>\d+))?"
)


def google_model_requires_default_sampling(model_name: str) -> bool:
    """Return whether Gemini requires its provider-default sampling settings."""

    identifier = model_name.rsplit("/", 1)[-1].lower()
    match = _GOOGLE_MODEL_VERSION_PATTERN.match(identifier)
    if match is not None:
        return int(match.group("major")) >= 3
    return identifier.endswith("-latest")


def sanitize_google_model_settings(
    model_name: str, model_settings: dict[str, Any]
) -> dict[str, Any]:
    """Strip sampling parameters unsupported by current/future Gemini models."""

    if not google_model_requires_default_sampling(model_name):
        return model_settings
    return {
        key: value
        for key, value in model_settings.items()
        if key not in _GOOGLE_SAMPLING_SETTINGS
    }


class EmbedOnlyFileHandler(FileHandler):
    """For providers that only support embedding/inlining (no upload API).
    Images and PDFs are embedded; small text files are inlined."""

    _EMBEDDABLE_EXTENSIONS = _IMAGE_EXTENSIONS | {".pdf"}
    _INLINEABLE_EXTENSIONS = _TEXT_EXTENSIONS


class GoogleFileHandler(EmbedOnlyFileHandler):
    """Inline Gemini files with headroom for base64 and the rest of the request."""

    # Gemini inline image requests must stay below 20 MB including base64-encoded
    # files, prompts, and system instructions. Apply the conservative cumulative
    # raw-byte budget to PDFs too so mixed image/document requests remain safe.
    _MAX_EMBED_PAYLOAD_BYTES = 14 * 1024 * 1024


class OpenAIFileHandler(FileHandler):
    """OpenAI file handler with Files API upload support."""

    _EMBEDDABLE_EXTENSIONS = _IMAGE_EXTENSIONS
    _INLINEABLE_EXTENSIONS = _TEXT_EXTENSIONS
    _UPLOADABLE_EXTENSIONS = {
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
    # https://developers.openai.com/api/docs/guides/file-inputs
    _MAX_EMBED_PAYLOAD_BYTES = 45 * 1024 * 1024  # 50 MB minus headroom
    _MAX_EMBEDS_PER_REQUEST = 500

    def __init__(self, model_type: OpenAIGenerativeAIModelType):
        self._model_type = model_type

    def _get_max_upload_bytes(self) -> int:
        """
        Return the maximum upload size in bytes, capped at 512 MB.

        :return: Max upload size in bytes.
        """

        return (
            min(512, settings.BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB) * 1024 * 1024
        )

    def _can_upload_file(self, ext: str, size: int) -> bool:
        return (
            ext in self._UPLOADABLE_EXTENSIONS and size <= self._get_max_upload_bytes()
        )

    def _get_upload_client(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Return a synchronous OpenAI client for file operations.

        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        :return: An ``openai.OpenAI`` client instance.
        """

        from openai import OpenAI

        mt = self._model_type
        api_key = mt.get_api_key(workspace, settings_override)
        organization = mt.get_organization(workspace, settings_override)
        base_url = mt.get_base_url(workspace, settings_override)
        return OpenAI(api_key=api_key, organization=organization, base_url=base_url)

    def _upload(
        self,
        ai_file: "AIFile",
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> None:
        from pydantic_ai import UploadedFile

        data = ai_file.read_content()
        with self._get_upload_client(workspace, settings_override) as client:
            uploaded = client.files.create(
                file=(ai_file.name, data), purpose="user_data"
            )
        ai_file.provider_file_id = uploaded.id
        ai_file.content = UploadedFile(
            file_id=uploaded.id,
            provider_name="openai",
            media_type=ai_file.mime_type,
            identifier=ai_file.original_name,
        )

    def delete_file(
        self,
        ai_file: "AIFile",
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> None:
        with self._get_upload_client(workspace, settings_override) as client:
            client.files.delete(ai_file.provider_file_id)


class AnthropicFileHandler(FileHandler):
    """Anthropic file handler with beta Files API upload for PDFs."""

    # https://platform.claude.com/docs/en/docs/build-with-claude/vision
    # https://platform.claude.com/docs/en/docs/build-with-claude/pdf-support
    # https://docs.anthropic.com/en/docs/build-with-claude/files
    _EMBEDDABLE_EXTENSIONS = _IMAGE_EXTENSIONS
    _INLINEABLE_EXTENSIONS = _TEXT_EXTENSIONS
    _UPLOADABLE_EXTENSIONS = {".pdf"}
    # 5 MB per image, 32 MB per request, 600 images/request, 600 pages
    _MAX_EMBED_PAYLOAD_BYTES = 30 * 1024 * 1024  # 32 MB minus headroom
    _MAX_EMBEDS_PER_REQUEST = 600

    def __init__(self, model_type: AnthropicGenerativeAIModelType):
        self._model_type = model_type

    def _get_sync_client(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Return a synchronous Anthropic client for file operations.

        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        :return: An ``anthropic.Anthropic`` client instance.
        """

        import anthropic

        api_key = self._model_type.get_api_key(workspace, settings_override)
        return anthropic.Anthropic(api_key=api_key)

    def _upload(
        self,
        ai_file: "AIFile",
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> None:
        from pydantic_ai import UploadedFile

        data = ai_file.read_content()
        with self._get_sync_client(workspace, settings_override) as client:
            uploaded = client.beta.files.upload(file=(ai_file.name, data))
        ai_file.provider_file_id = uploaded.id
        ai_file.content = UploadedFile(
            file_id=uploaded.id,
            provider_name="anthropic",
            media_type=ai_file.mime_type,
            identifier=ai_file.original_name,
        )

    def delete_file(
        self,
        ai_file: "AIFile",
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> None:
        with self._get_sync_client(workspace, settings_override) as client:
            client.beta.files.delete(ai_file.provider_file_id)


# ---------------------------------------------------------------------------
# Model types
# ---------------------------------------------------------------------------


class BaseOpenAIGenerativeAIModelType(GenerativeAIModelType):
    def get_api_key(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> Optional[str]:
        configured, value = self.get_configured_setting(
            workspace, "api_key", settings_override, state=state
        )
        return value if configured else settings.BASEROW_OPENAI_API_KEY

    def get_enabled_models(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        feature_type: str | None = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> list[str]:
        configured, value = self.get_configured_setting(
            workspace, "models", settings_override, feature_type, state
        )
        return value if configured else settings.BASEROW_OPENAI_MODELS

    def get_organization(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        configured, value = self.get_configured_setting(
            workspace, "organization", settings_override
        )
        return value if configured else settings.BASEROW_OPENAI_ORGANIZATION

    def get_base_url(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        return None

    def get_ai_model(
        self,
        model_name: str,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        from pydantic_ai.models.openai import OpenAIResponsesModel
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = self.get_api_key(workspace, settings_override)
        organization = self.get_organization(workspace, settings_override)
        base_url = self.get_base_url(workspace, settings_override)
        provider = OpenAIProvider(api_key=api_key, base_url=base_url)
        # No provider takes an organization, and passing our own client would move
        # its lifecycle out of the provider.
        provider.client.organization = organization
        return OpenAIResponsesModel(model_name, provider=provider)

    def get_settings_serializer(self) -> type:
        from baserow.api.generative_ai.serializers import BaseOpenAISettingsSerializer

        return BaseOpenAISettingsSerializer


class OpenAIGenerativeAIModelType(BaseOpenAIGenerativeAIModelType):
    type = "openai"

    def get_known_models(self) -> list[str]:
        from pydantic_ai.models.openai import OpenAIModelName

        return get_known_model_names(OpenAIModelName)

    @cached_property
    def file_handler(self) -> OpenAIFileHandler:
        return OpenAIFileHandler(self)

    def get_settings_serializer(self) -> type:
        from baserow.api.generative_ai.serializers import OpenAISettingsSerializer

        return OpenAISettingsSerializer

    def get_base_url(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        configured, value = self.get_configured_setting(
            workspace, "base_url", settings_override
        )
        return value if configured else settings.BASEROW_OPENAI_BASE_URL


class AnthropicGenerativeAIModelType(GenerativeAIModelType):
    type = "anthropic"

    _FILES_API_BETA = "files-api-2025-04-14"

    @cached_property
    def file_handler(self) -> AnthropicFileHandler:
        return AnthropicFileHandler(self)

    def get_api_key(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> Optional[str]:
        configured, value = self.get_configured_setting(
            workspace, "api_key", settings_override, state=state
        )
        return value if configured else settings.BASEROW_ANTHROPIC_API_KEY

    def get_enabled_models(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        feature_type: str | None = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> list[str]:
        configured, value = self.get_configured_setting(
            workspace, "models", settings_override, feature_type, state
        )
        return value if configured else settings.BASEROW_ANTHROPIC_MODELS

    def get_ai_model(
        self,
        model_name: str,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        api_key = self.get_api_key(workspace, settings_override)
        return AnthropicModel(model_name, provider=AnthropicProvider(api_key=api_key))

    def get_known_models(self) -> list[str]:
        from pydantic_ai.models.anthropic import AnthropicModelName

        return get_known_model_names(AnthropicModelName)

    def _prepare_model_settings(
        self, temperature: Optional[float] = None
    ) -> dict[str, Any]:
        model_settings: dict[str, Any] = {
            "extra_headers": {"anthropic-beta": self._FILES_API_BETA},
        }
        if temperature is not None:
            model_settings["temperature"] = min(temperature, 1)
        return model_settings

    def get_settings_serializer(self) -> type:
        from baserow.api.generative_ai.serializers import AnthropicSettingsSerializer

        return AnthropicSettingsSerializer


class GoogleGenerativeAIModelType(GenerativeAIModelType):
    type = "google"
    supports_legacy_workspace_settings = False

    @cached_property
    def file_handler(self) -> GoogleFileHandler:
        return GoogleFileHandler()

    def get_api_key(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> Optional[str]:
        configured, value = self.get_configured_setting(
            workspace, "api_key", settings_override, state=state
        )
        return value if configured else None

    def get_enabled_models(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        feature_type: str | None = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> list[str]:
        configured, value = self.get_configured_setting(
            workspace, "models", settings_override, feature_type, state
        )
        return value if configured else []

    def get_ai_model(
        self,
        model_name: str,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        api_key = self.get_api_key(workspace, settings_override)
        if not api_key:
            raise ValueError("A Google Gemini API key is required.")
        return GoogleModel(
            model_name,
            provider=GoogleProvider(api_key=api_key),
        )

    def get_known_models(self) -> list[str]:
        from pydantic_ai.models.google import GoogleModelName

        return [
            name
            for name in get_known_model_names(GoogleModelName)
            if "-image" not in name and name not in _GOOGLE_DISCOVERY_EXCLUDED_MODELS
        ]

    def prepare_model_settings(
        self, model: str, temperature: Optional[float] = None
    ) -> dict[str, Any]:
        return self.sanitize_model_settings(
            model, super().prepare_model_settings(model, temperature)
        )

    def sanitize_model_settings(
        self, model: str, model_settings: dict[str, Any]
    ) -> dict[str, Any]:
        return sanitize_google_model_settings(model, model_settings)

    def get_settings_serializer(self) -> type:
        from baserow.api.generative_ai.serializers import GoogleSettingsSerializer

        return GoogleSettingsSerializer


class GroqGenerativeAIModelType(GenerativeAIModelType):
    type = "groq"
    supports_legacy_workspace_settings = False

    def get_api_key(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> Optional[str]:
        configured, value = self.get_configured_setting(
            workspace, "api_key", settings_override, state=state
        )
        return value if configured else None

    def get_enabled_models(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        feature_type: str | None = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> list[str]:
        configured, value = self.get_configured_setting(
            workspace, "models", settings_override, feature_type, state
        )
        return value if configured else []

    def get_ai_model(
        self,
        model_name: str,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        from pydantic_ai.models.groq import GroqModel
        from pydantic_ai.providers.groq import GroqProvider

        api_key = self.get_api_key(workspace, settings_override)
        if not api_key:
            raise ValueError("A Groq API key is required.")
        return GroqModel(model_name, provider=GroqProvider(api_key=api_key))

    def get_known_models(self) -> list[str]:
        from pydantic_ai.models.groq import ProductionGroqModelNames

        return [
            name
            for name in get_known_model_names(ProductionGroqModelNames)
            if name not in _GROQ_DISCOVERY_EXCLUDED_MODELS
            and not any(
                category in name
                for category in ("whisper", "playai-tts", "guard", "safeguard")
            )
        ]

    def get_settings_serializer(self) -> type:
        from baserow.api.generative_ai.serializers import GroqSettingsSerializer

        return GroqSettingsSerializer


class MistralGenerativeAIModelType(GenerativeAIModelType):
    # https://docs.mistral.ai/capabilities/vision/
    type = "mistral"

    @cached_property
    def file_handler(self) -> EmbedOnlyFileHandler:
        return EmbedOnlyFileHandler()

    def get_api_key(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> Optional[str]:
        configured, value = self.get_configured_setting(
            workspace, "api_key", settings_override, state=state
        )
        return value if configured else settings.BASEROW_MISTRAL_API_KEY

    def get_enabled_models(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        feature_type: str | None = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> list[str]:
        configured, value = self.get_configured_setting(
            workspace, "models", settings_override, feature_type, state
        )
        return value if configured else settings.BASEROW_MISTRAL_MODELS

    def get_ai_model(
        self,
        model_name: str,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        from pydantic_ai.models.mistral import MistralModel
        from pydantic_ai.providers.mistral import MistralProvider

        api_key = self.get_api_key(workspace, settings_override)
        return MistralModel(model_name, provider=MistralProvider(api_key=api_key))

    def get_known_models(self) -> list[str]:
        from pydantic_ai.models.mistral import MistralModelName

        return get_known_model_names(MistralModelName)

    def _prepare_model_settings(
        self, temperature: Optional[float] = None
    ) -> dict[str, Any]:
        model_settings: dict[str, Any] = {}
        if temperature is not None:
            model_settings["temperature"] = min(temperature, 1)
        return model_settings

    def get_settings_serializer(self) -> type:
        from baserow.api.generative_ai.serializers import MistralSettingsSerializer

        return MistralSettingsSerializer


class OllamaGenerativeAIModelType(BaseOpenAIGenerativeAIModelType):
    type = "ollama"

    @cached_property
    def file_handler(self) -> EmbedOnlyFileHandler:
        return EmbedOnlyFileHandler()

    def get_host(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> Optional[str]:
        configured, value = self.get_configured_setting(
            workspace, "host", settings_override, state=state
        )
        return value if configured else settings.BASEROW_OLLAMA_HOST

    def get_api_key(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> str:
        return "ollama"

    def get_organization(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> None:
        return None

    def get_base_url(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> str:
        host = self.get_host(workspace, settings_override)
        return f"{host}/v1"

    def get_enabled_models(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        feature_type: str | None = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> list[str]:
        configured, value = self.get_configured_setting(
            workspace, "models", settings_override, feature_type, state
        )
        return value if configured else settings.BASEROW_OLLAMA_MODELS

    def is_enabled(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> bool:
        host = self.get_host(workspace, settings_override, state)
        return bool(host) and bool(
            self.call_get_enabled_models(workspace, settings_override, state=state)
        )

    def get_ai_model(
        self,
        model_name: str,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.ollama import OllamaProvider

        host = self.get_host(workspace, settings_override)
        return OpenAIChatModel(
            model_name, provider=OllamaProvider(base_url=f"{host}/v1")
        )

    def get_settings_serializer(self) -> type:
        from baserow.api.generative_ai.serializers import OllamaSettingsSerializer

        return OllamaSettingsSerializer


class OpenRouterGenerativeAIModelType(BaseOpenAIGenerativeAIModelType):
    """
    The OpenRouter API is compatible with the OpenAI API.
    """

    type = "openrouter"

    @cached_property
    def file_handler(self) -> EmbedOnlyFileHandler:
        return EmbedOnlyFileHandler()

    def get_api_key(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> Optional[str]:
        configured, value = self.get_configured_setting(
            workspace, "api_key", settings_override, state=state
        )
        return value if configured else settings.BASEROW_OPENROUTER_API_KEY

    def get_enabled_models(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
        feature_type: str | None = None,
        state: Optional[ScopedAIProviderState] = None,
    ) -> list[str]:
        configured, value = self.get_configured_setting(
            workspace, "models", settings_override, feature_type, state
        )
        return value if configured else settings.BASEROW_OPENROUTER_MODELS

    def get_organization(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        configured, value = self.get_configured_setting(
            workspace, "organization", settings_override
        )
        return value if configured else settings.BASEROW_OPENROUTER_ORGANIZATION

    def get_base_url(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> str:
        return "https://openrouter.ai/api/v1"

    def get_ai_model(
        self,
        model_name: str,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openrouter import OpenRouterProvider

        api_key = self.get_api_key(workspace, settings_override)
        organization = self.get_organization(workspace, settings_override)
        provider = OpenRouterProvider(api_key=api_key)
        # No provider takes an organization, and passing our own client would move
        # its lifecycle out of the provider.
        provider.client.organization = organization
        return OpenAIChatModel(model_name, provider=provider)

    def get_settings_serializer(self) -> type:
        from baserow.api.generative_ai.serializers import OpenRouterSettingsSerializer

        return OpenRouterSettingsSerializer
