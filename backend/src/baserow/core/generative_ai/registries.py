from __future__ import annotations

import os
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, Optional, get_args, get_origin

from loguru import logger

from baserow.core.ai_provider.constants import AI_PROVIDER_CONFIGS_LOCAL_CACHE_KEY
from baserow.core.cache import local_cache
from baserow.core.models import Workspace
from baserow.core.registry import Instance, Registry

from .exceptions import GenerativeAITypeDoesNotExist, get_user_friendly_error_message

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.messages import UserContent

    from baserow_premium.fields.ai_file import AIFile


def get_known_model_names(model_name_type: Any) -> list[str]:
    """Extract the known string literals from a Pydantic AI model-name type."""

    names: list[str] = []

    def collect(type_value: Any) -> None:
        type_value = getattr(type_value, "__value__", type_value)
        if get_origin(type_value) is Literal:
            names.extend(
                value for value in get_args(type_value) if isinstance(value, str)
            )
            return
        for type_arg in get_args(type_value):
            collect(type_arg)

    collect(model_name_type)
    return list(dict.fromkeys(names))


class FileHandler:
    """Handles file processing for an AI provider.

    The cascade tries each strategy in order for every file:
    inline (text) -> embed (binary) -> upload (API) -> skip.

    Subclasses configure behavior via extension sets and by overriding
    ``_upload``, ``_can_upload_file``, and ``delete_file`` as needed.
    """

    _EMBEDDABLE_EXTENSIONS: set[str] = set()
    _INLINEABLE_EXTENSIONS: set[str] = set()
    _UPLOADABLE_EXTENSIONS: set[str] = set()

    _MAX_EMBED_PAYLOAD_BYTES = 45 * 1024 * 1024  # 50 MB minus headroom
    _MAX_EMBEDS_PER_REQUEST = 500
    _INLINE_UPLOAD_THRESHOLD_BYTES = 10 * 1024  # 10 KB

    def _has_embed_budget(
        self, file_size: int, embed_count: int, embed_payload_size: int
    ) -> bool:
        """
        Check whether adding a file of the given size would stay within the
        per-request embed limits.

        :param file_size: Size of the file in bytes.
        :param embed_count: Number of files already embedded in this request.
        :param embed_payload_size: Total bytes already embedded in this request.
        :return: True if the file fits within both count and payload limits.
        """

        return (
            embed_count < self._MAX_EMBEDS_PER_REQUEST
            and embed_payload_size + file_size <= self._MAX_EMBED_PAYLOAD_BYTES
        )

    def _can_inline_file(
        self, ext: str, size: int, embed_count: int, embed_payload_size: int
    ) -> bool:
        """
        Check whether a file can be inlined as text content.

        :param ext: Lowercase file extension including the dot.
        :param size: File size in bytes.
        :param embed_count: Number of files already embedded in this request.
        :param embed_payload_size: Total bytes already embedded in this request.
        :return: True if the file extension is inlineable, the file is small
            enough, and the embed budget has room.
        """

        return (
            ext in self._INLINEABLE_EXTENSIONS
            and size <= self._INLINE_UPLOAD_THRESHOLD_BYTES
            and self._has_embed_budget(size, embed_count, embed_payload_size)
        )

    def _can_embed_file(
        self, ext: str, size: int, embed_count: int, embed_payload_size: int
    ) -> bool:
        """
        Check whether a file can be embedded as binary content.

        :param ext: Lowercase file extension including the dot.
        :param size: File size in bytes.
        :param embed_count: Number of files already embedded in this request.
        :param embed_payload_size: Total bytes already embedded in this request.
        :return: True if the file extension is embeddable and the embed budget
            has room.
        """

        return ext in self._EMBEDDABLE_EXTENSIONS and self._has_embed_budget(
            size, embed_count, embed_payload_size
        )

    def _can_upload_file(self, ext: str, size: int) -> bool:
        """
        Check whether a file can be uploaded via the provider API.

        :param ext: Lowercase file extension including the dot.
        :param size: File size in bytes.
        :return: True if the file extension is uploadable.
        """

        return ext in self._UPLOADABLE_EXTENSIONS

    def _embed(self, ai_file: "AIFile") -> None:
        """
        Embed a file as binary content by reading its bytes and setting
        ``ai_file.content`` to a ``BinaryContent`` instance.

        :param ai_file: The file to embed.
        """

        from pydantic_ai import BinaryContent

        ai_file.content = BinaryContent(
            data=ai_file.read_content(),
            media_type=ai_file.mime_type,
            identifier=ai_file.original_name,
        )

    def _inline_text(self, ai_file: "AIFile") -> bool:
        """
        Try to inline file content as a ``TextContent`` instance. Sets
        ``ai_file.content`` on success.

        :param ai_file: The file to inline.
        :return: True if the file was valid UTF-8 and was inlined, False
            otherwise.
        """

        from pydantic_ai import TextContent

        try:
            text = ai_file.read_content().decode("utf-8")
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
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Upload a file via the provider API. Must be overridden by subclasses
        that declare ``_UPLOADABLE_EXTENSIONS``. Sets ``ai_file.content`` and
        ``ai_file.provider_file_id`` on success.

        :param ai_file: The file to upload.
        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        """

        raise NotImplementedError(
            f"{type(self).__name__} declares _UPLOADABLE_EXTENSIONS but does "
            f"not implement _upload()"
        )

    def prepare_files(
        self,
        files: list["AIFile"],
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> list["AIFile"]:
        """
        Process files into prompt content using the cascade:
        inline -> embed -> upload -> skip. Only files that were
        successfully processed (with ``content`` set) are returned.

        :param files: List of AIFile instances to process.
        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        :return: The subset of files that were successfully processed.
        """

        embed_payload_size = 0
        embed_count = 0

        for ai_file in files:
            _, ext = os.path.splitext(ai_file.name)
            ext = ext.lower()

            try:
                if self._can_inline_file(
                    ext, ai_file.size, embed_count, embed_payload_size
                ):
                    if self._inline_text(ai_file):
                        embed_payload_size += ai_file.size
                        embed_count += 1
                        continue

                if self._can_embed_file(
                    ext, ai_file.size, embed_count, embed_payload_size
                ):
                    self._embed(ai_file)
                    embed_payload_size += ai_file.size
                    embed_count += 1
                    continue

                if self._can_upload_file(ext, ai_file.size):
                    self._upload(ai_file, workspace, settings_override)
            except Exception as exc:
                logger.warning(f"Skipping file {ai_file.name}: {exc}")

        return [f for f in files if f.content is not None]

    def delete_file(
        self,
        ai_file: "AIFile",
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Delete a single uploaded file from the provider. Must be overridden
        by subclasses that upload files (i.e. that set ``provider_file_id``
        during ``_upload``).

        :param ai_file: The file to delete.
        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        """

        raise NotImplementedError(
            f"{type(self).__name__} does not implement delete_file()"
        )

    def cleanup_files(
        self,
        files: list["AIFile"],
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Delete all provider-uploaded files. Only files with a
        ``provider_file_id`` are processed. Safe to call with an empty list.

        :param files: List of AIFile instances returned by ``prepare_files``.
        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        """

        for ai_file in files:
            if not ai_file.provider_file_id:
                continue
            try:
                self.delete_file(ai_file, workspace, settings_override)
            except Exception:
                logger.warning(
                    f"Failed to delete provider file {ai_file.provider_file_id}."
                )


class GenerativeAIModelType(Instance):
    @cached_property
    def file_handler(self) -> FileHandler | None:
        """
        Return the file handler for this provider, or None if the provider
        does not support files. Override in subclasses to return a concrete
        ``FileHandler`` instance.
        """

        return None

    @property
    def supports_files(self) -> bool:
        """Return True if this provider supports file attachments."""

        return self.file_handler is not None

    def get_known_models(self) -> list[str] | None:
        """
        Return model identifiers known by the installed Pydantic AI client.

        ``None`` means that Pydantic AI has no static catalog for this provider.
        Known identifiers are suggestions only and can still be unavailable to the
        configured provider account.
        """

        return None

    def prepare_files(
        self,
        files: list["AIFile"],
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> list["AIFile"]:
        """
        Prepare files for prompting by processing them through the file handler,
        if available. Returns the list of AIFile instances that were
        successfully prepared (i.e. have their `content` attribute set). Should
        be called before prompting, and the returned files should be passed to
        the prompt via the `content` parameter for multi-modal input.

        :param files: The list of AIFile instances to prepare.
        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        """

        if self.file_handler is None:
            raise NotImplementedError(
                f"{type(self).__name__} does not support files. "
                f"Check supports_files before calling prepare_files()."
            )
        return self.file_handler.prepare_files(files, workspace, settings_override)

    def cleanup_files(
        self,
        files: list["AIFile"],
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Cleanup previously uploaded files via the file handler. Should be called
        in a finally block after prompting, to ensure cleanup happens even if
        prompting fails.

        :param files: The list of AIFile instances to clean up.
        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        """

        if self.file_handler is None:
            raise NotImplementedError(
                f"{type(self).__name__} does not support files. "
                f"Check supports_files before calling cleanup_files()."
            )
        self.file_handler.cleanup_files(files, workspace, settings_override)

    def get_workspace_setting(
        self,
        workspace: Optional[Workspace],
        key: str,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Get a setting for this AI model type.

        :param workspace: The workspace to get settings from.
        :param key: The setting key to retrieve.
        :param settings_override: Optional dict of settings to use instead of workspace
            settings. Format: {"api_key": "...", "models": [...]}
        :return: The setting value or None.
        """

        if settings_override is not None and key in settings_override:
            return settings_override[key]

        if not isinstance(workspace, Workspace):
            return None

        settings = workspace.generative_ai_models_settings or {}
        type_settings = settings.get(self.type, {})
        return type_settings.get(key, None)

    def get_configured_setting(
        self,
        workspace: Optional[Workspace],
        key: str,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> tuple[bool, Any]:
        """
        Resolve a non-environment setting and report whether it is authoritative.

        Explicit overrides come first. With database providers enabled, workspace
        models override matching instance models while non-overridden instance
        models remain inherited. Otherwise a complete legacy workspace JSON
        configuration is checked before an inherited instance provider and
        environment settings. Incomplete legacy settings are never combined with
        credentials from another scope.
        """

        from baserow.core.feature_flags import FF_AI_PROVIDERS, feature_flag_is_enabled

        providers_enabled = feature_flag_is_enabled(FF_AI_PROVIDERS)
        model_settings_override = None
        if settings_override is not None and key in settings_override:
            if not providers_enabled or key != "models":
                return True, settings_override[key]
            complete_override = self._get_complete_provider_settings(settings_override)
            if complete_override is not None:
                return True, complete_override["models"]
            model_settings_override = settings_override[key]

        if not providers_enabled:
            legacy_value = self.get_workspace_setting(workspace, key)
            if legacy_value:
                return True, legacy_value
            return False, None

        workspace_providers, instance_providers, disabled_provider_ids = (
            self._get_database_provider_configuration(workspace)
        )

        workspace_provider = workspace_providers.get(self.type)
        legacy_settings = None
        if workspace_provider is None and model_settings_override is None:
            legacy_settings = self._get_complete_legacy_workspace_settings(workspace)
            if legacy_settings is not None and key != "models":
                return True, legacy_settings.get(key)
        instance_provider = instance_providers.get(self.type)
        if workspace_provider is None and instance_provider is None:
            if model_settings_override is not None:
                return True, model_settings_override
            if legacy_settings is not None:
                return True, legacy_settings.get(key)
            return False, None

        if key == "models":
            workspace_models = []
            overridden_identifiers = set()
            if workspace_provider is not None and workspace_provider.is_active:
                workspace_model_rows = list(workspace_provider.models.all())
                overridden_identifiers = {
                    model.model_identifier for model in workspace_model_rows
                }
                workspace_models = [
                    model.model_identifier
                    for model in workspace_model_rows
                    if model.is_enabled
                ]

            instance_models = []
            if (
                instance_provider is not None
                and instance_provider.is_active
                and instance_provider.id not in disabled_provider_ids
            ):
                instance_models = [
                    model.model_identifier
                    for model in instance_provider.models.all()
                    if model.is_enabled
                    and model.model_identifier not in overridden_identifiers
                ]
            effective_models = workspace_models + instance_models
            models_to_limit = model_settings_override
            if models_to_limit is None and legacy_settings is not None:
                models_to_limit = legacy_settings["models"]
            if models_to_limit is not None:
                effective_model_set = set(effective_models)
                effective_models = [
                    model for model in models_to_limit if model in effective_model_set
                ]
            return True, effective_models

        provider = None
        if workspace_provider is not None and workspace_provider.is_active:
            provider = workspace_provider
        elif (
            instance_provider is not None
            and instance_provider.is_active
            and instance_provider.id not in disabled_provider_ids
        ):
            provider = instance_provider
        if provider is None:
            return True, None
        return True, self._get_provider_setting(provider, key)

    def _get_database_provider_configuration(
        self, workspace: Optional[Workspace]
    ) -> tuple[dict[str, Any], dict[str, Any], set[int]]:
        from baserow.core.ai_provider.models import (
            AIProviderConfig,
            AIProviderWorkspaceOverride,
        )

        workspace_id = workspace.id if isinstance(workspace, Workspace) else None

        def load_provider_configuration():
            providers = AIProviderConfig.objects.prefetch_related("models")
            if workspace_id is not None:
                from django.db.models import Q

                providers = providers.filter(
                    Q(workspace_id=workspace_id) | Q(workspace__isnull=True)
                )
            else:
                providers = providers.filter(workspace__isnull=True)
            providers = list(providers)
            instance_providers = {
                provider.provider_type: provider
                for provider in providers
                if provider.workspace_id is None
            }
            if workspace_id is None:
                return {}, instance_providers, set()
            workspace_providers = {
                provider.provider_type: provider
                for provider in providers
                if provider.workspace_id == workspace_id
            }
            disabled_instance_provider_ids = set(
                AIProviderWorkspaceOverride.objects.filter(
                    workspace_id=workspace_id
                ).values_list("provider_config_id", flat=True)
            )
            return (
                workspace_providers,
                instance_providers,
                disabled_instance_provider_ids,
            )

        cache_key = (
            f"{AI_PROVIDER_CONFIGS_LOCAL_CACHE_KEY}:{workspace_id or 'instance'}"
        )
        return local_cache.get(cache_key, load_provider_configuration)

    @staticmethod
    def _get_provider_setting(provider: Any, key: str) -> Any:
        if key == "api_key":
            return provider.api_key
        return provider.extra_settings.get(key)

    def _get_provider_settings(self, provider: Any) -> dict[str, Any]:
        from baserow.core.ai_provider.constants import PROVIDER_ENVIRONMENT_SETTINGS

        extra_setting_names = PROVIDER_ENVIRONMENT_SETTINGS[self.type]["extra_settings"]
        return {
            "api_key": provider.api_key,
            "models": [
                model.model_identifier
                for model in provider.models.all()
                if model.is_enabled
            ],
            **{name: provider.extra_settings.get(name) for name in extra_setting_names},
        }

    def _get_complete_legacy_workspace_settings(
        self, workspace: Optional[Workspace]
    ) -> Optional[dict[str, Any]]:
        """Return legacy settings only when they define their own connection."""

        if not isinstance(workspace, Workspace):
            return None

        values = (workspace.generative_ai_models_settings or {}).get(self.type)
        return self._get_complete_provider_settings(values)

    def _get_complete_provider_settings(self, values: Any) -> Optional[dict[str, Any]]:
        """Validate and normalize one complete provider settings dictionary."""

        from baserow.core.ai_provider.constants import PROVIDER_ENVIRONMENT_SETTINGS
        from baserow.core.ai_provider.exceptions import InvalidAIProviderSettings
        from baserow.core.ai_provider.provider_types import (
            normalize_model_identifiers,
            validate_provider_settings,
        )

        if not isinstance(values, dict):
            return None

        provider_config = PROVIDER_ENVIRONMENT_SETTINGS[self.type]
        api_key = str(values.get("api_key") or "")
        models = normalize_model_identifiers(values.get("models"))
        extra_settings = {
            name: values[name]
            for name in provider_config["extra_settings"]
            if values.get(name) not in (None, "")
        }
        try:
            validated_extra_settings = validate_provider_settings(
                self.type,
                api_key,
                extra_settings,
                models,
                require_credentials=True,
            )
        except InvalidAIProviderSettings:
            return None

        return {
            "api_key": api_key,
            "models": models,
            **validated_extra_settings,
        }

    def get_model_settings_override(
        self,
        model_name: str,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """Resolve the complete provider configuration owning ``model_name``."""

        if settings_override is not None:
            return settings_override

        from baserow.core.feature_flags import FF_AI_PROVIDERS, feature_flag_is_enabled

        if not feature_flag_is_enabled(FF_AI_PROVIDERS) or not isinstance(
            workspace, Workspace
        ):
            return None

        workspace_providers, instance_providers, disabled_provider_ids = (
            self._get_database_provider_configuration(workspace)
        )
        workspace_provider = workspace_providers.get(self.type)
        if workspace_provider is not None and workspace_provider.is_active:
            if any(
                model.model_identifier == model_name
                for model in workspace_provider.models.all()
            ):
                return self._get_provider_settings(workspace_provider)

        if workspace_provider is None:
            legacy_settings = self._get_complete_legacy_workspace_settings(workspace)
            if legacy_settings is not None:
                instance_provider = instance_providers.get(self.type)
                if instance_provider is None:
                    return (
                        legacy_settings
                        if model_name in legacy_settings["models"]
                        else None
                    )
                enabled_instance_models = [
                    model.model_identifier
                    for model in instance_provider.models.all()
                    if instance_provider.is_active
                    and instance_provider.id not in disabled_provider_ids
                    and model.is_enabled
                ]
                enabled_instance_model_set = set(enabled_instance_models)
                enabled_legacy_models = [
                    model
                    for model in legacy_settings["models"]
                    if model in enabled_instance_model_set
                ]
                if model_name not in enabled_legacy_models:
                    return None
                return {**legacy_settings, "models": enabled_legacy_models}

        instance_provider = instance_providers.get(self.type)
        if (
            instance_provider is not None
            and instance_provider.is_active
            and instance_provider.id not in disabled_provider_ids
            and any(
                model.model_identifier == model_name and model.is_enabled
                for model in instance_provider.models.all()
            )
        ):
            return self._get_provider_settings(instance_provider)
        return None

    def get_api_key(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Return the API key for this provider, or None if not configured.

        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        :return: The API key string, or None.
        """

        return None

    def is_enabled(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Return True if this provider has both an API key and at least one
        enabled model. Ollama overrides this to check the host instead.

        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        :return: True if the provider is enabled.
        """

        return bool(self.get_api_key(workspace, settings_override)) and bool(
            self.get_enabled_models(
                workspace=workspace, settings_override=settings_override
            )
        )

    def get_enabled_models(
        self,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> list[str]:
        """
        Return the list of enabled model names for this provider.

        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        :return: List of model name strings, empty if none configured.
        """

        return []

    def get_ai_model(
        self,
        model_name: str,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Return a pydantic-ai Model instance configured with provider credentials.

        :param model_name: The name of the model to retrieve.
        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        """

        raise NotImplementedError("The get_ai_model function must be implemented.")

    def _prepare_model_settings(
        self, temperature: Optional[float] = None
    ) -> dict[str, Any]:
        """
        Build model settings dict. Override in subclasses for provider quirks.

        :param temperature: Optional temperature override.
        :return: Dictionary of model settings.
        """

        settings: dict[str, Any] = {}
        if temperature is not None:
            settings["temperature"] = temperature
        return settings

    def _is_choices(self, output_type: Any) -> bool:
        """
        Determine if the output_type represents a list of string choices.

        :param output_type: The output_type to check.
        :return: True if output_type is a list of strings, False otherwise.
        """

        return isinstance(output_type, list) and all(
            isinstance(c, str) for c in output_type
        )

    def _build_user_prompt(
        self,
        prompt: str,
        output_type: Any = None,
        content: Optional[list[UserContent]] = None,
    ) -> str | list[UserContent]:
        """
        Build the user prompt, optionally adding choice constraints and
        multi-modal content.

        :param prompt: The base text prompt.
        :param output_type: The output_type to determine if choices should be added.
        :param content: Optional list of UserContent for multi-modal input.
        :return: The final prompt, either as a string or list of UserContent.
        """

        import json

        if self._is_choices(output_type):
            choices_json = json.dumps(output_type)
            prompt = (
                f"{prompt}\n\n"
                f"Select exactly one option from: {choices_json}\n"
                f"Respond with only the option name, nothing else."
            )

        if content:
            prompt = (
                f"{prompt}\n\n"
                "The following file contents are provided for context. "
                "Use them to answer the prompt above."
            )
            return [prompt] + content

        return prompt

    def _build_agent(self, output_type: Any = None) -> "Agent":
        """
        Create a pydantic-ai Agent with the appropriate output type.

        :param output_type: The output_type to determine the Agent's output format.
        :return: A configured Agent instance.
        """

        from pydantic_ai import Agent, PromptedOutput

        if output_type is not None and not self._is_choices(output_type):
            return Agent(
                output_type=PromptedOutput(output_type),
                output_retries=3,
            )

        return Agent(output_type=str)

    def _resolve_choices(
        self, text: str, choices: list[str], cutoff: float = 0.6
    ) -> Optional[str]:
        """
        Fuzzy-match the model's text response against the valid choices. If the
        best match is above the cutoff threshold, return it; otherwise return
        None.

        :param text: The model's raw text response.
        :param choices: The list of valid choice strings.
        :param cutoff: The similarity threshold for matching (0.0 to 1.0).
        :return: The matched choice string, or None if no good match is found.
        """

        import re
        from difflib import get_close_matches

        # Normalize common LLM formatting: quotes, markdown bold, trailing
        # punctuation, etc. Case-insensitive matching to handle ALL CAPS or
        # lowercase responses.
        normalized = re.sub(r"^[\s\"'`*]+|[\s\"'`*.!,]+$", "", text).lower()

        lower_choices = [c.lower() for c in choices]
        closest = get_close_matches(normalized, lower_choices, n=1, cutoff=cutoff)
        if closest:
            return choices[lower_choices.index(closest[0])]
        return None

    def prompt(
        self,
        model: str,
        prompt: str,
        workspace: Optional[Workspace] = None,
        temperature: Optional[float] = None,
        settings_override: Optional[dict[str, Any]] = None,
        output_type: Any = None,
        content: Optional[list[UserContent]] = None,
        model_settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Prompt the AI model and return the result. Handles model retrieval,
        prompt construction, agent execution, and choice resolution.

        If output_type is a list of strings, the model's response will be
        fuzzy-matched against those choices, and the matched choice will be
        returned (or None if no good match). If output_type is a Pydantic model,
        the response will be validated and returned as an instance of that model.

        If content is provided, it will be included as multi-modal input alongside
        the text prompt.

        :param model: The model name to use.
        :param prompt: The text prompt to send.
        :param workspace: The workspace for settings resolution.
        :param temperature: Optional temperature override.
        :param settings_override: Optional provider settings override.
        :param output_type: Controls the output format:
            - None (default): plain text response (str)
            - list[str]: choice selection — the model picks one, fuzzy-matched.
              Returns None if no match is found.
            - A Pydantic BaseModel or TypedDict: structured output via
              PromptedOutput. Returns a validated instance.
        :param content: A list of pydantic-ai content objects (BinaryContent, etc.)
            to include as multi-modal input alongside the text prompt.
        :param model_settings_override: Optional request settings merged over the
            provider defaults.
        :return: The model's response — a string, a matched choice, or a
            validated output_type instance.
        """

        from .exceptions import GenerativeAIPromptError

        try:
            settings_override = self.get_model_settings_override(
                model, workspace, settings_override
            )
            ai_model = self.get_ai_model(model, workspace, settings_override)
            model_settings = {
                **self._prepare_model_settings(temperature),
                **(model_settings_override or {}),
            }
            user_prompt = self._build_user_prompt(prompt, output_type, content)
            agent = self._build_agent(output_type)

            result = agent.run_sync(
                user_prompt, model=ai_model, model_settings=model_settings
            )

            if self._is_choices(output_type):
                return self._resolve_choices(result.output, output_type)

            return result.output
        except GenerativeAIPromptError:
            raise
        except Exception as e:
            raise GenerativeAIPromptError(get_user_friendly_error_message(e)) from e

    def get_settings_serializer(self) -> type:
        """
        Return the DRF serializer class for this provider's workspace-level
        settings (API key, models list, etc.).

        :return: A serializer class.
        """

        raise NotImplementedError(
            "The get_settings_serializer function must be implemented."
        )

    def get_serializer(self) -> type:
        """
        Return the DRF serializer class for the provider's public
        representation (type name, enabled models, etc.).

        :return: A serializer class.
        """

        from baserow.api.generative_ai.serializers import GenerativeAIModelsSerializer

        return GenerativeAIModelsSerializer


class GenerativeAIModelTypeRegistry(Registry):
    name = "generative_ai_model_type"
    does_not_exist_exception_class = GenerativeAITypeDoesNotExist

    def get_enabled_models_per_type(
        self, workspace: Optional[Workspace] = None
    ) -> dict[str, list[str]]:
        return {
            key: model_type.get_enabled_models(workspace)
            for key, model_type in self.registry.items()
            if model_type.is_enabled(workspace)
        }


generative_ai_model_type_registry: GenerativeAIModelTypeRegistry = (
    GenerativeAIModelTypeRegistry()
)
