from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Optional

from django.conf import settings

from loguru import logger

from baserow.core.models import Workspace

from .registries import GenerativeAIModelType

if TYPE_CHECKING:
    from baserow_premium.fields.ai_file import AIFile


class BaseOpenAIGenerativeAIModelType(GenerativeAIModelType):
    def get_api_key(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        return (
            self.get_workspace_setting(workspace, "api_key", settings_override)
            or settings.BASEROW_OPENAI_API_KEY
        )

    def get_enabled_models(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> list[str]:
        workspace_models = self.get_workspace_setting(
            workspace, "models", settings_override
        )
        return workspace_models or settings.BASEROW_OPENAI_MODELS

    def get_organization(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        return (
            self.get_workspace_setting(workspace, "organization", settings_override)
            or settings.BASEROW_OPENAI_ORGANIZATION
        )

    def get_base_url(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        return None

    def is_enabled(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> bool:
        api_key = self.get_api_key(workspace, settings_override)
        return bool(api_key) and bool(
            self.get_enabled_models(
                workspace=workspace, settings_override=settings_override
            )
        )

    def get_ai_model(
        self,
        model_name: str,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        from openai import AsyncOpenAI
        from pydantic_ai.models.openai import OpenAIResponsesModel
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = self.get_api_key(workspace, settings_override)
        organization = self.get_organization(workspace, settings_override)
        base_url = self.get_base_url(workspace, settings_override)
        client = AsyncOpenAI(
            api_key=api_key, organization=organization, base_url=base_url
        )
        return OpenAIResponsesModel(
            model_name, provider=OpenAIProvider(openai_client=client)
        )

    def get_settings_serializer(self) -> type:
        from baserow.api.generative_ai.serializers import BaseOpenAISettingsSerializer

        return BaseOpenAISettingsSerializer


class OpenAIGenerativeAIModelType(BaseOpenAIGenerativeAIModelType):
    type = "openai"

    def get_settings_serializer(self) -> type:
        from baserow.api.generative_ai.serializers import OpenAISettingsSerializer

        return OpenAISettingsSerializer

    def get_base_url(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        return (
            self.get_workspace_setting(workspace, "base_url", settings_override)
            or settings.BASEROW_OPENAI_BASE_URL
        )

    supports_files = True

    _EMBEDDABLE_EXTENSIONS = {".gif", ".jpg", ".jpeg", ".png", ".webp"}
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
    # Below this limit, uploadable files are sent inline.
    _INLINE_UPLOAD_THRESHOLD_BYTES = 10 * 1024  # 10 KB

    def _get_max_upload_bytes(self) -> int:
        return (
            min(512, settings.BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB) * 1024 * 1024
        )

    def _can_embed(self, file_size: int, embed_count: int, embed_payload: int) -> bool:
        return (
            embed_count < self._MAX_EMBEDS_PER_REQUEST
            and embed_payload + file_size <= self._MAX_EMBED_PAYLOAD_BYTES
        )

    @staticmethod
    def _embed(ai_file: "AIFile", data: bytes) -> None:
        from pydantic_ai import BinaryContent

        ai_file.content = BinaryContent(
            data=data,
            media_type=ai_file.mime_type,
            identifier=ai_file.original_name,
        )

    @staticmethod
    def _inline_text(ai_file: "AIFile", data: bytes) -> bool:
        """Try to inline file content as TextContent. Returns False if the
        content is not valid UTF-8."""

        from pydantic_ai import TextContent

        try:
            text = data.decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            return False
        ai_file.content = TextContent(
            content=(
                f"[Content of file '{ai_file.original_name}']\n{text}\n[End of file]"
            ),
            metadata={"source": ai_file.original_name},
        )
        return True

    def _upload(
        self,
        ai_file: "AIFile",
        data: bytes,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> None:
        from pydantic_ai import UploadedFile

        file_id = self._upload_file(ai_file.name, data, workspace, settings_override)
        ai_file.provider_file_id = file_id
        ai_file.content = UploadedFile(
            file_id=file_id,
            provider_name="openai",
            media_type=ai_file.mime_type,
            identifier=ai_file.original_name,
        )

    def prepare_files(
        self,
        files: list[AIFile],
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> list[AIFile]:
        embed_payload = 0
        embed_count = 0
        max_upload = self._get_max_upload_bytes()

        for ai_file in files:
            _, ext = os.path.splitext(ai_file.name)
            ext = ext.lower()

            try:
                if ext in self._EMBEDDABLE_EXTENSIONS:
                    if not self._can_embed(ai_file.size, embed_count, embed_payload):
                        continue
                    self._embed(ai_file, ai_file.read_content())
                    embed_payload += ai_file.size
                    embed_count += 1

                elif ext in self._UPLOADABLE_EXTENSIONS:
                    if ai_file.size > max_upload:
                        continue
                    data = ai_file.read_content()

                    if (
                        ai_file.size <= self._INLINE_UPLOAD_THRESHOLD_BYTES
                        and self._can_embed(ai_file.size, embed_count, embed_payload)
                    ):
                        if not self._inline_text(ai_file, data):
                            self._embed(ai_file, data)
                        embed_payload += ai_file.size
                        embed_count += 1
                    else:
                        self._upload(ai_file, data, workspace, settings_override)
            except Exception as exc:
                logger.warning(f"Skipping file {ai_file.name}: {exc}")
                continue

        return [f for f in files if f.content is not None]

    def _get_upload_client(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Return a sync OpenAI client for file upload/delete operations."""

        from openai import OpenAI

        api_key = self.get_api_key(workspace, settings_override)
        organization = self.get_organization(workspace, settings_override)
        base_url = self.get_base_url(workspace, settings_override)
        return OpenAI(api_key=api_key, organization=organization, base_url=base_url)

    def _upload_file(
        self,
        file_name: str,
        file_bytes: bytes,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> str:
        client = self._get_upload_client(workspace, settings_override)
        uploaded = client.files.create(
            file=(file_name, file_bytes), purpose="user_data"
        )
        return uploaded.id

    def delete_file(
        self,
        ai_file: AIFile,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> None:
        """Delete an uploaded file from OpenAI."""

        client = self._get_upload_client(workspace, settings_override)
        client.files.delete(ai_file.provider_file_id)


class AnthropicGenerativeAIModelType(GenerativeAIModelType):
    type = "anthropic"

    def get_api_key(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        return (
            self.get_workspace_setting(workspace, "api_key", settings_override)
            or settings.BASEROW_ANTHROPIC_API_KEY
        )

    def get_enabled_models(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> list[str]:
        workspace_models = self.get_workspace_setting(
            workspace, "models", settings_override
        )
        return workspace_models or settings.BASEROW_ANTHROPIC_MODELS

    def is_enabled(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> bool:
        api_key = self.get_api_key(workspace, settings_override)
        return bool(api_key) and bool(
            self.get_enabled_models(
                workspace=workspace, settings_override=settings_override
            )
        )

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

    def _prepare_model_settings(
        self, temperature: Optional[float] = None
    ) -> dict[str, Any]:
        settings: dict[str, Any] = {}
        if temperature is not None:
            # Anthropic only accepts temperature up to 1.0
            settings["temperature"] = min(temperature, 1)
        return settings

    def get_settings_serializer(self) -> type:
        from baserow.api.generative_ai.serializers import AnthropicSettingsSerializer

        return AnthropicSettingsSerializer


class MistralGenerativeAIModelType(GenerativeAIModelType):
    type = "mistral"

    def get_api_key(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        return (
            self.get_workspace_setting(workspace, "api_key", settings_override)
            or settings.BASEROW_MISTRAL_API_KEY
        )

    def get_enabled_models(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> list[str]:
        workspace_models = self.get_workspace_setting(
            workspace, "models", settings_override
        )
        return workspace_models or settings.BASEROW_MISTRAL_MODELS

    def is_enabled(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> bool:
        api_key = self.get_api_key(workspace, settings_override)
        return bool(api_key) and bool(
            self.get_enabled_models(
                workspace=workspace, settings_override=settings_override
            )
        )

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

    def _prepare_model_settings(
        self, temperature: Optional[float] = None
    ) -> dict[str, Any]:
        settings: dict[str, Any] = {}
        if temperature is not None:
            # Mistral only accepts temperature up to 1.0
            settings["temperature"] = min(temperature, 1)
        return settings

    def get_settings_serializer(self) -> type:
        from baserow.api.generative_ai.serializers import MistralSettingsSerializer

        return MistralSettingsSerializer


class OllamaGenerativeAIModelType(BaseOpenAIGenerativeAIModelType):
    type = "ollama"

    def get_host(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        return (
            self.get_workspace_setting(workspace, "host", settings_override)
            or settings.BASEROW_OLLAMA_HOST
        )

    def get_api_key(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
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
    ) -> list[str]:
        workspace_models = self.get_workspace_setting(
            workspace, "models", settings_override
        )
        return workspace_models or settings.BASEROW_OLLAMA_MODELS

    def is_enabled(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> bool:
        host = self.get_host(workspace, settings_override)
        return bool(host) and bool(
            self.get_enabled_models(workspace, settings_override)
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

    def get_api_key(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        return (
            self.get_workspace_setting(workspace, "api_key", settings_override)
            or settings.BASEROW_OPENROUTER_API_KEY
        )

    def get_enabled_models(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> list[str]:
        workspace_models = self.get_workspace_setting(
            workspace, "models", settings_override
        )
        return workspace_models or settings.BASEROW_OPENROUTER_MODELS

    def get_organization(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        return (
            self.get_workspace_setting(workspace, "organization", settings_override)
            or settings.BASEROW_OPENROUTER_ORGANIZATION
        )

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

    def get_settings_serializer(self) -> type:
        from baserow.api.generative_ai.serializers import OpenRouterSettingsSerializer

        return OpenRouterSettingsSerializer
