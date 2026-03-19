from baserow.api.generative_ai.serializers import GenerativeAIModelsSerializer
from baserow.core.generative_ai.exceptions import GenerativeAIPromptError
from baserow.core.generative_ai.registries import (
    GenerativeAIModelType,
    generative_ai_model_type_registry,
)


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

    def prompt(
        self,
        model,
        prompt,
        workspace=None,
        temperature=None,
        settings_override=None,
        output_type=None,
        content=None,
    ):
        if isinstance(output_type, list):
            return output_type[0]
        if output_type is not None:
            raise GenerativeAIPromptError(
                "Test fixture does not support structured output."
            )
        return f"Generated with temperature {temperature}: {prompt}"

    def get_settings_serializer(self):
        return GenerativeAIModelsSerializer


class TestGenerativeAIWithFilesModelType(GenerativeAIModelType):
    type = "test_generative_ai_with_files"
    supports_files = True

    def is_enabled(self, workspace=None):
        return True

    def get_enabled_models(self, workspace=None):
        models = self.get_workspace_setting(workspace, "models")
        return models if models else ["test_1"]

    def prompt(
        self,
        model,
        prompt,
        workspace=None,
        temperature=None,
        settings_override=None,
        output_type=None,
        content=None,
    ):
        if isinstance(output_type, list):
            return output_type[0]
        if content:
            return f"Generated with files and temperature {temperature}: {prompt}"
        return f"Generated with temperature {temperature}: {prompt}"

    def get_settings_serializer(self):
        return GenerativeAIModelsSerializer

    def prepare_files(self, files, read_file, workspace=None, settings_override=None):
        from pydantic_ai import BinaryContent

        content_parts = []
        for name, size, media_type in files:
            if size > 1 * 1024 * 1024:  # 1 MB limit
                continue
            data = read_file(name)
            content_parts.append(BinaryContent(data=data, media_type=media_type))
            break  # first file only
        return content_parts, []

    def delete_file(self, file_id, workspace=None, settings_override=None):
        pass


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
