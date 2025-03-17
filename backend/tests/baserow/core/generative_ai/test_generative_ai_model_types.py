import random
from dataclasses import dataclass
from unittest.mock import MagicMock, Mock

import pytest
from openai import OpenAIError

from baserow.core.generative_ai.exceptions import AIFileError, GenerativeAIPromptError
from baserow.core.generative_ai.generative_ai_model_types import (
    OpenAIGenerativeAIModelType,
)

base_module = "baserow.core.generative_ai.generative_ai_model_types"


class FilesAPIStub:
    """
    Stubbed OpenAI files API that can
    store and delete files.
    """

    @dataclass
    class OpenAIFileStub:
        id: str

    _files = {}

    def create(self, file, purpose):
        file_name, file, _ = file
        if OpenAIGenerativeAIModelType().is_file_compatible(file_name) is False:
            raise OpenAIError()

        ai_file_id = str(random.randint(0, 1000))
        self._files[ai_file_id] = {
            "file_name": file_name,
            "file": file,
            "purpose": purpose,
        }
        return self.OpenAIFileStub(id=ai_file_id)

    def delete(self, file_id):
        try:
            del self._files[file_id]
        except KeyError as exc:
            raise OpenAIError() from exc


@dataclass
class RunStub:
    status: str


class AssistantsAPIStub:
    """
    Stubbed OpenAI assistant API.
    """

    @dataclass
    class OpenAIAssistantStub:
        id: str

    def __init__(self):
        self._assistants = {}

    def create(self, name, instructions, model, tools):
        assistant = self.OpenAIAssistantStub(id=str(random.randint(0, 1000)))
        self._assistants[assistant.id] = {
            "name": name,
            "instructions": instructions,
            "model": model,
            "tools": tools,
        }
        return assistant

    def delete(self, assistant_id):
        del self._assistants[assistant_id]


class BetaAPIStub:
    """
    Stubbed OpenAI beta API.
    """

    def __init__(self):
        self.assistants = AssistantsAPIStub()
        self.threads = Mock()


class OpenAIStub:
    """
    Stubbed OpenAI API client.
    """

    def __init__(self):
        self.beta = BetaAPIStub()
        self.files = FilesAPIStub()


def test_openai_type_is_file_compatible():
    ai_model_type = OpenAIGenerativeAIModelType()

    assert ai_model_type.is_file_compatible("filename.txt") is True
    assert ai_model_type.is_file_compatible("filename.png") is False
    assert ai_model_type.is_file_compatible("filename") is False


def test_openai_type_upload_file():
    file_name = "filename.txt"
    file = "filestring".encode()
    openai_client = OpenAIStub()

    def get_client_stub(workspace=None):
        return openai_client

    ai_model_type = OpenAIGenerativeAIModelType()
    ai_model_type.get_client = get_client_stub

    file_id = ai_model_type.upload_file(file_name, file)

    assert openai_client.files._files[file_id] == {
        "file_name": file_name,
        "file": file,
        "purpose": "assistants",
    }


def test_openai_type_upload_file_error():
    file_name = "filename"  # not compatible
    file = "filestring".encode()
    openai_client = OpenAIStub()

    def get_client_stub(workspace=None):
        return openai_client

    ai_model_type = OpenAIGenerativeAIModelType()
    ai_model_type.get_client = get_client_stub

    with pytest.raises(AIFileError):
        ai_model_type.upload_file(file_name, file)


def test_openai_type_delete_files():
    file = "filestring".encode()
    openai_client = OpenAIStub()
    openai_client.files._files = {
        "1": {
            "file_name": "filename1.txt",
            "file": file,
            "purpose": "assistants",
        },
        "2": {
            "file_name": "filename2.txt",
            "file": file,
            "purpose": "assistants",
        },
        "3": {
            "file_name": "filename3.txt",
            "file": file,
            "purpose": "assistants",
        },
    }

    def get_client_stub(workspace=None):
        return openai_client

    ai_model_type = OpenAIGenerativeAIModelType()
    ai_model_type.get_client = get_client_stub
    ai_model_type.delete_files(file_ids=["1", "2"])

    assert len(openai_client.files._files) == 1
    assert openai_client.files._files["3"]["file_name"] == "filename3.txt"


def test_openai_type_delete_files_error():
    openai_client = OpenAIStub()

    def get_client_stub(workspace=None):
        return openai_client

    ai_model_type = OpenAIGenerativeAIModelType()
    ai_model_type.get_client = get_client_stub
    with pytest.raises(AIFileError):
        ai_model_type.delete_files(file_ids=["doesnt_exist"])


def test_openai_type_prompt_with_files():
    openai_client = OpenAIStub()

    def get_client_stub(workspace=None):
        return openai_client

    ai_model_type = OpenAIGenerativeAIModelType()
    ai_model_type.get_client = get_client_stub

    openai_client.beta.threads.runs.create_and_poll.return_value = RunStub(
        status="completed"
    )

    messages = MagicMock()
    messages.data[0].content[0].text.value = "test response\u30104:0\u2020source\u3011"

    openai_client.beta.threads.messages.list.return_value = messages

    response = ai_model_type.prompt_with_files("gpt-3.5", "test prompt", file_ids=[])
    assert response == "test response"  # reference was removed from the ouput
    assert (
        len(openai_client.beta.assistants._assistants) == 0
    ), "Assistant has been deleted"
    openai_client.beta.threads.delete.assert_called_once()
    assert len(openai_client.beta.assistants._assistants) == 0


def test_openai_type_prompt_with_files_error():
    openai_client = OpenAIStub()

    def get_client_stub(workspace=None):
        return openai_client

    ai_model_type = OpenAIGenerativeAIModelType()
    ai_model_type.get_client = get_client_stub

    openai_client.beta.threads.runs.create_and_poll.return_value = RunStub(
        status="failed"
    )

    with pytest.raises(GenerativeAIPromptError):
        ai_model_type.prompt_with_files("gpt-3.5", "test prompt", file_ids=[])


def test_openai_max_file_size(settings):
    ai_model_type = OpenAIGenerativeAIModelType()

    settings.BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB = 1000
    assert ai_model_type.get_max_file_size() == 512

    settings.BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB = 100
    assert ai_model_type.get_max_file_size() == 100
