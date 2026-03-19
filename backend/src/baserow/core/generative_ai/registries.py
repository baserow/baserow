from __future__ import annotations

from typing import Any, Callable, Optional

from pydantic_ai.messages import UserContent

from baserow.core.models import Workspace
from baserow.core.registry import Instance, Registry

from .exceptions import GenerativeAITypeDoesNotExist


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
        files: list[tuple[str, int, str]],
        read_file: Callable[[str], bytes],
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> tuple[list[UserContent], list[str]]:
        """Process files into prompt content. Each provider implements its
        own logic: what to embed, what to upload, limits, rules.

        :param files: List of (name, size_bytes, media_type) tuples — metadata
            only, no data read yet.
        :param read_file: Callback to lazily read file data by name. Only call
            for files the provider decides to accept.
        :param workspace: The workspace for settings resolution.
        :param settings_override: Optional provider settings override.
        :return: Tuple of (content_parts, uploaded_file_ids_for_cleanup).
        """

        return [], []

    def get_ai_model(
        self,
        model_name: str,
        workspace: Optional[Workspace] = None,
        settings_override: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Return a pydantic-ai Model instance configured with provider credentials."""

        raise NotImplementedError("The get_ai_model function must be implemented.")

    def _prepare_model_settings(
        self, temperature: Optional[float] = None
    ) -> dict[str, Any]:
        """Build model settings dict. Override in subclasses for provider quirks."""

        settings: dict[str, Any] = {}
        if temperature is not None:
            settings["temperature"] = temperature
        return settings

    def _is_choices(self, output_type: Any) -> bool:
        return isinstance(output_type, list) and all(
            isinstance(c, str) for c in output_type
        )

    def _build_user_prompt(
        self,
        prompt: str,
        output_type: Any = None,
        content: Optional[list[UserContent]] = None,
    ) -> str | list[UserContent]:
        """Build the user prompt, optionally adding choice constraints and
        multi-modal content."""

        import json

        if self._is_choices(output_type):
            choices_json = json.dumps(output_type)
            prompt = (
                f"{prompt}\n\n"
                f"Select exactly one option from: {choices_json}\n"
                f"Respond with only the option name, nothing else."
            )

        if content:
            return [prompt] + content

        return prompt

    def _build_agent(self, output_type: Any = None) -> Any:
        """Create a pydantic-ai Agent with the appropriate output type."""

        from pydantic_ai import Agent, PromptedOutput

        if output_type is not None and not self._is_choices(output_type):
            return Agent(
                output_type=PromptedOutput(output_type),
                output_retries=3,
            )

        return Agent(output_type=str)

    def _resolve_choices(self, text: str, choices: list[str]) -> Optional[str]:
        """Fuzzy-match the model's text response against the valid choices."""

        from difflib import get_close_matches

        closest = get_close_matches(text.strip(), choices, n=1, cutoff=0.6)
        return closest[0] if closest else None

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
        Prompt the AI model and return the result.

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
