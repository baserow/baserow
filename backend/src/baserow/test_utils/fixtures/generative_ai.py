import random
from typing import Optional

from baserow.api.generative_ai.serializers import GenerativeAIModelsSerializer
from baserow.core.generative_ai.exceptions import GenerativeAIPromptError
from baserow.core.generative_ai.registries import (
    GenerativeAIModelType,
    GenerativeAIWithFilesModelType,
    generative_ai_model_type_registry,
)
from baserow.core.generative_ai.types import FileId
from baserow.core.models import Workspace


class TestGenerativeAINoModelType(GenerativeAIModelType):
    type = "test_generative_ai_no_model"

    def is_enabled(self, workspace=None):
        return False

    def get_enabled_models(self, workspace=None):
        return []

    def prompt(self, model, prompt, workspace=None, temperature=None):
        return ""

    def get_settings_serializer(self):
        return GenerativeAIModelsSerializer


class TestGenerativeAIModelType(GenerativeAIModelType):
    type = "test_generative_ai"

    def is_enabled(self, workspace=None):
        return True

    def get_enabled_models(self, workspace=None):
        models = self.get_workspace_setting(workspace, "models")
        return models if models else ["test_1"]

    def prompt(self, model, prompt, workspace=None, temperature=None):
        return f"Generated with temperature {temperature}: {prompt}"

    def get_settings_serializer(self):
        return GenerativeAIModelsSerializer


class TestGenerativeAIWithFilesModelType(
    GenerativeAIWithFilesModelType, GenerativeAIModelType
):
    type = "test_generative_ai_with_files"

    def is_enabled(self, workspace=None):
        return True

    def get_enabled_models(self, workspace=None):
        models = self.get_workspace_setting(workspace, "models")
        return models if models else ["test_1"]

    def prompt(self, model, prompt, workspace=None, temperature=None):
        return f"Generated with temperature {temperature}: {prompt}"

    def get_settings_serializer(self):
        return GenerativeAIModelsSerializer

    def is_file_compatible(self, file_name: str) -> bool:
        return True

    def get_max_file_size(self):
        return 1  # 1 megabyte

    def upload_file(
        self, file_name: str, file: bytes, workspace: Optional[Workspace] = None
    ):
        if getattr(self, "_files", None) is None:
            self._files = {}

        gen_id = str(random.randint(0, 1000))
        self._files[gen_id] = {
            "file_name": file_name,
            "file": file,
        }
        return gen_id

    def delete_files(
        self, file_ids: list[FileId], workspace: Optional[Workspace] = None
    ):
        for file_id in file_ids:
            del self._files[file_id]

    def prompt_with_files(
        self,
        model: str,
        prompt: str,
        file_ids: list[FileId],
        workspace: Optional[Workspace] = None,
        temperature: Optional[float] = None,
    ):
        return f"Generated with files {str(file_ids)} and temperature {temperature}: {prompt}"


class TestGenerativeAIModelTypePromptError(GenerativeAIModelType):
    type = "test_generative_ai_prompt_error"

    def is_enabled(self, workspace=None):
        return True

    def get_enabled_models(self, workspace=None):
        return ["test_1"]

    def prompt(self, model, prompt, workspace=None, temperature=None):
        raise GenerativeAIPromptError("Test error")

    def get_settings_serializer(self):
        return GenerativeAIModelsSerializer


class GenerativeAIFixtures:
    def register_fake_generate_ai_type(self, **kwargs):
        try:
            generative_ai_model_type_registry.register(TestGenerativeAINoModelType())
            generative_ai_model_type_registry.register(TestGenerativeAIModelType())
            generative_ai_model_type_registry.register(
                TestGenerativeAIModelTypePromptError()
            )
            generative_ai_model_type_registry.register(
                TestGenerativeAIWithFilesModelType()
            )
        except generative_ai_model_type_registry.already_registered_exception_class:
            pass
