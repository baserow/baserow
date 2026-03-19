from baserow.core.generative_ai.generative_ai_model_types import (
    OpenAIGenerativeAIModelType,
)


def test_openai_type_is_file_compatible():
    ai_model_type = OpenAIGenerativeAIModelType()

    assert ai_model_type.is_file_compatible("filename.txt") is True
    assert ai_model_type.is_file_compatible("filename.pdf") is True
    assert ai_model_type.is_file_compatible("filename.csv") is True
    assert ai_model_type.is_file_compatible("filename.png") is False
    assert ai_model_type.is_file_compatible("filename") is False


def test_openai_max_file_size(settings):
    ai_model_type = OpenAIGenerativeAIModelType()

    settings.BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB = 1000
    assert ai_model_type.get_max_file_size() == 512

    settings.BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB = 100
    assert ai_model_type.get_max_file_size() == 100
