import os
import re

from django.conf import settings

from baserow.core.generative_ai.exceptions import AIFileError, GenerativeAIPromptError
from baserow.core.generative_ai.types import FileId

from .registries import GenerativeAIModelType, GenerativeAIWithFilesModelType


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

    def get_client(self, workspace=None, settings_override=None):
        from openai import OpenAI

        api_key = self.get_api_key(workspace, settings_override)
        organization = self.get_organization(workspace, settings_override)
        base_url = self.get_base_url(workspace, settings_override)
        return OpenAI(api_key=api_key, organization=organization, base_url=base_url)

    def get_settings_serializer(self):
        from baserow.api.generative_ai.serializers import BaseOpenAISettingsSerializer

        return BaseOpenAISettingsSerializer

    def prompt(
        self, model, prompt, workspace=None, temperature=None, settings_override=None
    ):
        from openai import APIStatusError as OpenAIAPIStatusError
        from openai import OpenAIError

        try:
            client = self.get_client(workspace, settings_override)
            kwargs = {}
            if temperature:
                kwargs["temperature"] = temperature
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                stream=False,
                **kwargs,
            )
        except (OpenAIError, OpenAIAPIStatusError) as exc:
            raise GenerativeAIPromptError(str(exc)) from exc
        return chat_completion.choices[0].message.content


class OpenAIGenerativeAIModelType(
    GenerativeAIWithFilesModelType, BaseOpenAIGenerativeAIModelType
):
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
        # See supported files at:
        # https://platform.openai.com/docs/assistants/tools/file-search/supported-files
        supported_file_extensions = {
            ".doc",
            ".docx",
            ".html",
            ".json",
            ".md",
            ".pdf",
            ".pptx",
            ".txt",
            ".tex",
        }

        _, ext = os.path.splitext(file_name)
        if ext not in supported_file_extensions:
            return False
        return True

    def get_max_file_size(self) -> int:
        return min(512, settings.BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB)

    def upload_file(self, file_name: str, file: bytes, workspace=None) -> FileId:
        from openai import APIStatusError as OpenAIAPIStatusError
        from openai import OpenAIError

        try:
            client = self.get_client(workspace=workspace)
            openai_file = client.files.create(
                file=(file_name, file, None), purpose="assistants"
            )
            return openai_file.id
        except (OpenAIError, OpenAIAPIStatusError) as exc:
            raise AIFileError(str(exc)) from exc

    def delete_files(self, file_ids: list[FileId], workspace=None):
        from openai import APIStatusError as OpenAIAPIStatusError
        from openai import OpenAIError

        try:
            client = self.get_client(workspace=workspace)
            for file_id in file_ids:
                client.files.delete(file_id)
        except (OpenAIError, OpenAIAPIStatusError) as exc:
            raise AIFileError(str(exc)) from exc

    def prompt_with_files(
        self, model, prompt, file_ids: list[FileId], workspace=None, temperature=None
    ):
        from openai import APIStatusError as OpenAIAPIStatusError
        from openai import OpenAIError

        run, thread, assistant = None, None, None
        try:
            client = self.get_client(workspace)
            kwargs = {}
            if temperature:
                kwargs["temperature"] = temperature

            assistant = client.beta.assistants.create(
                name="Assistant that have access to user files",
                instructions="",
                model=model,
                tools=[{"type": "file_search"}],
                **kwargs,
            )
            thread = client.beta.threads.create()
            attachments = [
                {"file_id": file_id, "tools": [{"type": "file_search"}]}
                for file_id in file_ids
            ]
            message = client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=prompt,
                attachments=attachments,
            )
            run = client.beta.threads.runs.create_and_poll(
                thread_id=thread.id,
                assistant_id=assistant.id,
                poll_interval_ms=2000,  # 2 seconds
                timeout=60.0,  # 1 minute
            )
            if run.status == "completed":
                messages = client.beta.threads.messages.list(thread_id=thread.id)
                try:
                    message = messages.data[0].content[0].text.value
                except Exception:
                    raise GenerativeAIPromptError(
                        "The OpenAI model didn't respond with an answer."
                    )

                # remove references from the output
                regex = r"【[0-9:]{1,}†source】"
                message = re.sub(regex, "", message, 0)

                return message
            else:
                raise GenerativeAIPromptError(
                    "The OpenAI model didn't respond with an answer."
                )
        except (OpenAIError, OpenAIAPIStatusError) as exc:
            raise GenerativeAIPromptError(str(exc)) from exc
        finally:
            if run and thread:
                if run.status in [
                    "queued",
                    "in_progress",
                    "requires_action",
                    "incomplete",
                ]:
                    client.beta.threads.runs.cancel(run.id, thread_id=thread.id)
            if thread:
                # Deleting the thread should delete all messages within
                client.beta.threads.delete(thread_id=thread.id)
            if assistant:
                client.beta.assistants.delete(assistant_id=assistant.id)


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

    def get_client(self, workspace=None, settings_override=None):
        from anthropic import Anthropic

        api_key = self.get_api_key(workspace, settings_override)
        return Anthropic(api_key=api_key)

    def get_settings_serializer(self):
        from baserow.api.generative_ai.serializers import AnthropicSettingsSerializer

        return AnthropicSettingsSerializer

    def prompt(
        self, model, prompt, workspace=None, temperature=None, settings_override=None
    ):
        from anthropic import APIStatusError

        try:
            client = self.get_client(workspace, settings_override)
            kwargs = {}
            if temperature:
                # Because some LLMs can have a temperature of 2, this is the maximum by
                # default. We're changing it to a maximum of 1 because Anthropic only
                # accepts 1.
                kwargs["temperature"] = min(temperature, 1)
            message = client.messages.create(
                messages=[
                    {"role": "user", "content": [{"type": "text", "text": prompt}]}
                ],
                model=model,
                max_tokens=4096,
                stream=False,
                **kwargs,
            )
            return message.content[0].text
        except APIStatusError as exc:
            raise GenerativeAIPromptError(str(exc)) from exc


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

    def get_client(self, workspace=None, settings_override=None):
        from mistralai import Mistral

        api_key = self.get_api_key(workspace, settings_override)
        return Mistral(api_key=api_key)

    def get_settings_serializer(self):
        from baserow.api.generative_ai.serializers import MistralSettingsSerializer

        return MistralSettingsSerializer

    def prompt(
        self, model, prompt, workspace=None, temperature=None, settings_override=None
    ):
        from mistralai.models import HTTPValidationError, SDKError

        try:
            client = self.get_client(workspace, settings_override)
            kwargs = {}
            if temperature:
                # Because some LLMs can have a temperature of 2, this is the maximum by
                # default. We're changing it to a maximum of 1 because Mistral only
                # accepts 1.
                kwargs["temperature"] = min(temperature, 1)
            response = client.chat.complete(
                messages=[
                    {"role": "user", "content": [{"type": "text", "text": prompt}]}
                ],
                model=model,
                **kwargs,
            )
            return response.choices[0].message.content
        except (HTTPValidationError, SDKError) as exc:
            raise GenerativeAIPromptError(str(exc)) from exc


class OllamaGenerativeAIModelType(GenerativeAIModelType):
    type = "ollama"

    def get_host(self, workspace=None, settings_override=None):
        return (
            self.get_workspace_setting(workspace, "host", settings_override)
            or settings.BASEROW_OLLAMA_HOST
        )

    def get_enabled_models(self, workspace=None, settings_override=None):
        workspace_models = self.get_workspace_setting(
            workspace, "models", settings_override
        )
        return workspace_models or settings.BASEROW_OLLAMA_MODELS

    def is_enabled(self, workspace=None, settings_override=None):
        ollama_host = self.get_host(workspace, settings_override)
        return bool(ollama_host) and bool(
            self.get_enabled_models(workspace, settings_override)
        )

    def get_client(self, workspace=None, settings_override=None):
        from ollama import Client as OllamaClient

        ollama_host = self.get_host(workspace, settings_override)
        return OllamaClient(host=ollama_host)

    def prompt(
        self, model, prompt, workspace=None, temperature=None, settings_override=None
    ):
        from ollama import RequestError as OllamaRequestError
        from ollama import ResponseError as OllamaResponseError

        client = self.get_client(workspace, settings_override)
        options = {}
        if temperature:
            # Because some LLMs can have a temperature of 2, this is the maximum by
            # default. We're changing it to a maximum of 1 because Ollama only
            # accepts 1.
            options["temperature"] = min(temperature, 1)
        try:
            response = client.generate(
                model=model, prompt=prompt, stream=False, options=options
            )
        except (OllamaRequestError, OllamaResponseError) as exc:
            raise GenerativeAIPromptError(str(exc)) from exc

        return response["response"]

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

    def get_settings_serializer(self):
        from baserow.api.generative_ai.serializers import OpenRouterSettingsSerializer

        return OpenRouterSettingsSerializer

    def is_file_compatible(self, file_name):
        return False
