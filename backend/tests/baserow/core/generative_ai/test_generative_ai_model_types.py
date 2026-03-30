from baserow.core.generative_ai.generative_ai_model_types import (
    OpenAIGenerativeAIModelType,
)


def test_openai_supports_files():
    ai_model_type = OpenAIGenerativeAIModelType()
    assert ai_model_type.supports_files is True


def test_openai_embeddable_and_uploadable_extensions():
    ai_model_type = OpenAIGenerativeAIModelType()

    # Documents → uploadable
    assert ".txt" in ai_model_type._UPLOADABLE_EXTENSIONS
    assert ".pdf" in ai_model_type._UPLOADABLE_EXTENSIONS
    assert ".csv" in ai_model_type._UPLOADABLE_EXTENSIONS

    # Images → embeddable
    assert ".png" in ai_model_type._EMBEDDABLE_EXTENSIONS
    assert ".jpg" in ai_model_type._EMBEDDABLE_EXTENSIONS

    # Unsupported
    assert ".mp4" not in (
        ai_model_type._EMBEDDABLE_EXTENSIONS | ai_model_type._UPLOADABLE_EXTENSIONS
    )


def test_openai_max_upload_size(settings):
    ai_model_type = OpenAIGenerativeAIModelType()

    settings.BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB = 1000
    assert ai_model_type._get_max_upload_bytes() == 512 * 1024 * 1024

    settings.BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB = 100
    assert ai_model_type._get_max_upload_bytes() == 100 * 1024 * 1024
