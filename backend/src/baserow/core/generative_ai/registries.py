from __future__ import annotations

import os
from functools import cached_property
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger
from pydantic_ai.messages import UserContent

from baserow.core.models import Workspace
from baserow.core.registry import Instance, Registry

from .exceptions import GenerativeAITypeDoesNotExist, get_user_friendly_error_message

if TYPE_CHECKING:
    from pydantic_ai import Agent

    from baserow_premium.fields.ai_file import AIFile


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
        :return: The model's response — a string, a matched choice, or a
            validated output_type instance.
        """

        from .exceptions import GenerativeAIPromptError

        try:
            ai_model = self.get_ai_model(model, workspace, settings_override)
            model_settings = self._prepare_model_settings(temperature)
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
