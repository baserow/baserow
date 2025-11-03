from abc import ABC, abstractmethod
from typing import Optional

from baserow.core.generative_ai.types import FileId
from baserow.core.models import Workspace
from baserow.core.registry import Instance, Registry

from .exceptions import GenerativeAITypeDoesNotExist


class GenerativeAIWithFilesModelType(ABC):
    @abstractmethod
    def is_file_compatible(self, file_name: str) -> bool:
        """
        Method to determine whether provided file can be used
        for processing.

        :param file_name: The name of the file.
        """

        raise NotImplementedError(
            "The is_file_compatible function must be implemented."
        )

    @abstractmethod
    def get_max_file_size(self) -> int:
        """
        Returns the maximum size of the file in MB that can be used.
        """

        raise NotImplementedError("The get_max_file_size function must be implemented.")

    @abstractmethod
    def upload_file(
        self, file_name: str, file: bytes, workspace: Optional[Workspace] = None
    ) -> FileId:
        """
        Method to upload files for processing.

        :param file_name: The name for the uploaded file including file extension.
        :param file: File to upload as bytes.
        :param workspace: Workspace where the processing happens.
        :raises AIFileError: If the file has not been uploaded.
        :return: List of file ids to keep as a reference to processed files.
        """

        raise NotImplementedError("The upload_file function must be implemented.")

    @abstractmethod
    def delete_files(
        self, file_ids: list[FileId], workspace: Optional[Workspace] = None
    ):
        """
        Method to clean up processed files that are no longer needed.

        :param file_ids: File ids of files to delete.
        :param workspace: Workspace where the processing happens.
        :raises AIFileError: If the file has not been deleted.
        """

        raise NotImplementedError("The delete_files function must be implemented.")

    @abstractmethod
    def prompt_with_files(
        self,
        model: str,
        prompt: str,
        file_ids: list[FileId],
        workspace: Optional[Workspace] = None,
        temperature: Optional[float] = None,
    ):
        """
        Prompt AI model for an answer using the provided files as file ids as the
        knowledge base.

        :param model: The name of the model to use.
        :param prompt: The model's prompt to use.
        :param file_ids: File ids of files to use as the knowledge base.
        :param workspace: The workspace related to the prompt.
        :param temperature: The temperature that must be used when executing the prompt.
        """

        raise NotImplementedError("The prompt_with_files function must be implemented.")


class GenerativeAIModelType(Instance):
    def get_workspace_setting(self, workspace, key, settings_override=None):
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

    def is_enabled(self, workspace=None):
        return False

    def get_enabled_models(self, workspace=None):
        return []

    def prompt(self, model, prompt, workspace=None, temperature=None):
        raise NotImplementedError("The prompt function must be implemented.")

    def get_settings_serializer(self):
        raise NotImplementedError(
            "The get_settings_serializer function must be implemented."
        )

    def get_serializer(self):
        from baserow.api.generative_ai.serializers import GenerativeAIModelsSerializer

        return GenerativeAIModelsSerializer


class GenerativeAIModelTypeRegistry(Registry):
    name = "generative_ai_model_type"
    does_not_exist_exception_class = GenerativeAITypeDoesNotExist

    def get_enabled_models_per_type(self, workspace=None):
        return {
            key: model_type.get_enabled_models(workspace)
            for key, model_type in self.registry.items()
            if model_type.is_enabled(workspace)
        }


generative_ai_model_type_registry: GenerativeAIModelTypeRegistry = (
    GenerativeAIModelTypeRegistry()
)
