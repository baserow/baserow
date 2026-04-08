from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from loguru import logger
from pydantic_ai.messages import UserContent

from baserow.core.models import Workspace
from baserow.core.registry import Instance, Registry

from .exceptions import GenerativeAITypeDoesNotExist

if TYPE_CHECKING:
    from pydantic_ai import Agent

    from baserow_premium.fields.ai_file import AIFile


class GenerativeAIModelType(Instance):
    supports_files: bool = False

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

    def is_enabled(self, workspace: Optional[Workspace] = None) -> bool:
        return False

    def get_enabled_models(self, workspace: Optional[Workspace] = None) -> list[str]:
        return []

    def prepare_files(
        self,
        files: list[AIFile],
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> list[AIFile]:
        """Process files into prompt content. Each provider implements its
        own logic for deciding what to embed, what to upload, and which files
        to skip.

        Providers set ``content`` and optionally ``provider_file_id`` on each
        accepted file. Only processed files (those with ``content`` set) are
        returned; skipped files are filtered out.

        :param files: List of AIFile instances with metadata and lazy
            ``read_content()`` method.
        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        :return: The processed files with content/provider_file_id set.
        """

        return []

    def delete_file(
        self,
        ai_file: AIFile,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Delete a single uploaded file from the provider. Override in
        subclasses that upload files in ``prepare_files``.

        :param ai_file: The AIFile instance representing the file to delete.
        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        """

    def cleanup_files(
        self,
        files: list[AIFile],
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Clean up provider-uploaded files. Only files with a
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
                    f"Failed to delete file {ai_file.provider_file_id} from "
                    f"provider {self.type}."
                )

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
            raise GenerativeAIPromptError(str(e)) from e

    def get_settings_serializer(self) -> type:
        raise NotImplementedError(
            "The get_settings_serializer function must be implemented."
        )

    def get_serializer(self) -> type:
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
