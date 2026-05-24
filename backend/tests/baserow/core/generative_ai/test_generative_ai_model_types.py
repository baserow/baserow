from unittest.mock import patch

from pydantic_ai import BinaryContent, TextContent, UploadedFile

from baserow.core.generative_ai.generative_ai_model_types import (
    AnthropicGenerativeAIModelType,
    MistralGenerativeAIModelType,
    OllamaGenerativeAIModelType,
    OpenAIGenerativeAIModelType,
    OpenRouterGenerativeAIModelType,
)
from baserow_premium.fields.ai_file import AIFile


def _make_ai_file(
    name: str, size: int, mime_type: str = "text/plain", content_bytes: bytes = b""
) -> AIFile:
    ai_file = AIFile(
        name=name,
        original_name=name,
        size=size,
        mime_type=mime_type,
    )
    ai_file.read_content = lambda: content_bytes  # type: ignore[assignment]
    return ai_file


def test_openai_supports_files():
    ai_model_type = OpenAIGenerativeAIModelType()
    assert ai_model_type.supports_files is True


def test_openai_embeddable_and_uploadable_extensions():
    handler = OpenAIGenerativeAIModelType().file_handler

    # Documents → uploadable
    assert ".txt" in handler._UPLOADABLE_EXTENSIONS
    assert ".pdf" in handler._UPLOADABLE_EXTENSIONS
    assert ".csv" in handler._UPLOADABLE_EXTENSIONS

    # Images → embeddable
    assert ".png" in handler._EMBEDDABLE_EXTENSIONS
    assert ".jpg" in handler._EMBEDDABLE_EXTENSIONS

    # Unsupported
    assert ".mp4" not in (
        handler._EMBEDDABLE_EXTENSIONS | handler._UPLOADABLE_EXTENSIONS
    )


def test_openai_max_upload_size(settings):
    ai_model_type = OpenAIGenerativeAIModelType()
    handler = ai_model_type.file_handler

    settings.BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB = 1000
    assert handler._get_max_upload_bytes() == 512 * 1024 * 1024

    settings.BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB = 100
    assert handler._get_max_upload_bytes() == 100 * 1024 * 1024


def test_prepare_files_small_text_file_is_inlined():
    """A small .txt file should be inlined as TextContent, not uploaded."""

    ai_model_type = OpenAIGenerativeAIModelType()
    data = b"talk about hamburger"
    ai_file = _make_ai_file("a.txt", size=len(data), content_bytes=data)

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 1
    assert isinstance(result[0].content, TextContent)
    assert "talk about hamburger" in result[0].content.content
    assert "a.txt" in result[0].content.content
    assert result[0].provider_file_id is None


def test_prepare_files_small_binary_uploadable_is_uploaded():
    """A small non-UTF-8 inlineable+uploadable file falls through to upload."""

    ai_model_type = OpenAIGenerativeAIModelType()
    data = b"\x80\x81\x82"
    ai_file = _make_ai_file(
        "data.csv", size=len(data), mime_type="text/csv", content_bytes=data
    )

    def fake_upload(f, workspace=None, settings_override=None):
        f.provider_file_id = "file-bin"
        f.content = UploadedFile(
            file_id="file-bin",
            provider_name="openai",
            media_type=f.mime_type,
            identifier=f.original_name,
        )

    with patch.object(ai_model_type.file_handler, "_upload", side_effect=fake_upload):
        result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 1
    assert isinstance(result[0].content, UploadedFile)
    assert result[0].provider_file_id == "file-bin"


def test_prepare_files_large_uploadable_is_uploaded():
    """A .txt file over the inline threshold should be uploaded via the Files API."""

    ai_model_type = OpenAIGenerativeAIModelType()
    size = ai_model_type.file_handler._INLINE_UPLOAD_THRESHOLD_BYTES + 1
    data = b"x" * size
    ai_file = _make_ai_file("big.txt", size=size, content_bytes=data)

    def fake_upload(f, workspace=None, settings_override=None):
        f.provider_file_id = "file-123"
        f.content = UploadedFile(
            file_id="file-123",
            provider_name="openai",
            media_type=f.mime_type,
            identifier=f.original_name,
        )

    with patch.object(ai_model_type.file_handler, "_upload", side_effect=fake_upload):
        result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 1
    assert isinstance(result[0].content, UploadedFile)
    assert result[0].provider_file_id == "file-123"


def test_prepare_files_small_uploadable_respects_embed_limits():
    """When embed payload would exceed the limit, small files fall back to upload."""

    ai_model_type = OpenAIGenerativeAIModelType()
    handler = ai_model_type.file_handler
    data = b"small"
    ai_file = _make_ai_file("a.txt", size=len(data), content_bytes=data)

    def fake_upload(f, workspace=None, settings_override=None):
        f.provider_file_id = "file-456"
        f.content = UploadedFile(
            file_id="file-456",
            provider_name="openai",
            media_type=f.mime_type,
            identifier=f.original_name,
        )

    original = handler._MAX_EMBED_PAYLOAD_BYTES
    handler._MAX_EMBED_PAYLOAD_BYTES = 0
    try:
        with patch.object(handler, "_upload", side_effect=fake_upload):
            result = ai_model_type.prepare_files([ai_file])
    finally:
        handler._MAX_EMBED_PAYLOAD_BYTES = original

    assert len(result) == 1
    assert isinstance(result[0].content, UploadedFile)
    assert result[0].provider_file_id == "file-456"


def test_prepare_files_image_still_embedded():
    """Images should still go through the embeddable path as before."""

    ai_model_type = OpenAIGenerativeAIModelType()
    data = b"\x89PNG\r\n\x1a\n"
    ai_file = _make_ai_file(
        "photo.png", size=len(data), mime_type="image/png", content_bytes=data
    )

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 1
    assert isinstance(result[0].content, BinaryContent)
    assert result[0].provider_file_id is None


def test_prepare_files_unsupported_extension_is_skipped():
    """Files with unsupported extensions are excluded from the result."""

    ai_model_type = OpenAIGenerativeAIModelType()
    data = b"some data"
    ai_file = _make_ai_file(
        "video.mp4", size=len(data), mime_type="video/mp4", content_bytes=data
    )

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 0
    assert ai_file.content is None


def test_prepare_files_oversized_uploadable_is_skipped(settings):
    """Uploadable files exceeding the size limit are excluded."""

    ai_model_type = OpenAIGenerativeAIModelType()
    settings.BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB = 1
    limit = ai_model_type.file_handler._get_max_upload_bytes()
    data = b"x" * (limit + 1)
    ai_file = _make_ai_file("huge.txt", size=len(data), content_bytes=data)

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 0
    assert ai_file.content is None


def test_anthropic_supports_files():
    assert AnthropicGenerativeAIModelType().supports_files is True


def test_anthropic_prepare_files_image_is_embedded():
    ai_model_type = AnthropicGenerativeAIModelType()
    data = b"\x89PNG\r\n\x1a\n"
    ai_file = _make_ai_file(
        "photo.png", size=len(data), mime_type="image/png", content_bytes=data
    )

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 1
    assert isinstance(result[0].content, BinaryContent)


def test_anthropic_prepare_files_pdf_is_uploaded():
    """PDFs are always uploaded via the Files API for Anthropic."""

    ai_model_type = AnthropicGenerativeAIModelType()
    data = b"%PDF-1.4 fake"
    ai_file = _make_ai_file(
        "doc.pdf", size=len(data), mime_type="application/pdf", content_bytes=data
    )

    def fake_upload(f, workspace=None, settings_override=None):
        f.content = "uploaded"

    with patch.object(ai_model_type.file_handler, "_upload", side_effect=fake_upload):
        result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 1


def test_anthropic_prepare_files_small_text_is_inlined():
    ai_model_type = AnthropicGenerativeAIModelType()
    data = b"hello world"
    ai_file = _make_ai_file("notes.txt", size=len(data), content_bytes=data)

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 1
    assert isinstance(result[0].content, TextContent)
    assert "hello world" in result[0].content.content


def test_anthropic_prepare_files_unsupported_is_skipped():
    ai_model_type = AnthropicGenerativeAIModelType()
    data = b"data"
    ai_file = _make_ai_file(
        "sheet.xlsx",
        size=len(data),
        mime_type="application/vnd.ms-excel",
        content_bytes=data,
    )

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 0


def test_anthropic_prepare_files_large_text_is_skipped():
    """Text files over the inline threshold are skipped (no upload API)."""

    ai_model_type = AnthropicGenerativeAIModelType()
    size = ai_model_type.file_handler._INLINE_UPLOAD_THRESHOLD_BYTES + 1
    data = b"x" * size
    ai_file = _make_ai_file("big.txt", size=size, content_bytes=data)

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 0


def test_mistral_supports_files():
    assert MistralGenerativeAIModelType().supports_files is True


def test_mistral_prepare_files_image_is_embedded():
    ai_model_type = MistralGenerativeAIModelType()
    data = b"\xff\xd8\xff\xe0"
    ai_file = _make_ai_file(
        "photo.jpg", size=len(data), mime_type="image/jpeg", content_bytes=data
    )

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 1
    assert isinstance(result[0].content, BinaryContent)


def test_mistral_prepare_files_small_text_is_inlined():
    ai_model_type = MistralGenerativeAIModelType()
    data = b"some csv data"
    ai_file = _make_ai_file(
        "data.csv", size=len(data), mime_type="text/csv", content_bytes=data
    )

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 1
    assert isinstance(result[0].content, TextContent)


# --- Ollama (embed-only) ---


def test_ollama_supports_files():
    assert OllamaGenerativeAIModelType().supports_files is True


def test_ollama_prepare_files_image_is_embedded():
    ai_model_type = OllamaGenerativeAIModelType()
    data = b"\x89PNG\r\n\x1a\n"
    ai_file = _make_ai_file(
        "photo.png", size=len(data), mime_type="image/png", content_bytes=data
    )

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 1
    assert isinstance(result[0].content, BinaryContent)


def test_ollama_prepare_files_pdf_is_embedded():
    ai_model_type = OllamaGenerativeAIModelType()
    data = b"%PDF-1.4 fake"
    ai_file = _make_ai_file(
        "doc.pdf", size=len(data), mime_type="application/pdf", content_bytes=data
    )

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 1
    assert isinstance(result[0].content, BinaryContent)


def test_ollama_prepare_files_small_text_is_inlined():
    ai_model_type = OllamaGenerativeAIModelType()
    data = b"hello from ollama"
    ai_file = _make_ai_file("notes.txt", size=len(data), content_bytes=data)

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 1
    assert isinstance(result[0].content, TextContent)
    assert "hello from ollama" in result[0].content.content


def test_ollama_prepare_files_unsupported_is_skipped():
    ai_model_type = OllamaGenerativeAIModelType()
    data = b"data"
    ai_file = _make_ai_file(
        "sheet.xlsx",
        size=len(data),
        mime_type="application/vnd.ms-excel",
        content_bytes=data,
    )

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 0


# --- OpenRouter (embed-only) ---


def test_openrouter_supports_files():
    assert OpenRouterGenerativeAIModelType().supports_files is True


def test_openrouter_prepare_files_image_is_embedded():
    ai_model_type = OpenRouterGenerativeAIModelType()
    data = b"\xff\xd8\xff\xe0"
    ai_file = _make_ai_file(
        "photo.jpg", size=len(data), mime_type="image/jpeg", content_bytes=data
    )

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 1
    assert isinstance(result[0].content, BinaryContent)


def test_openrouter_prepare_files_small_text_is_inlined():
    ai_model_type = OpenRouterGenerativeAIModelType()
    data = b"some data"
    ai_file = _make_ai_file(
        "data.csv", size=len(data), mime_type="text/csv", content_bytes=data
    )

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 1
    assert isinstance(result[0].content, TextContent)


def test_openrouter_prepare_files_unsupported_is_skipped():
    ai_model_type = OpenRouterGenerativeAIModelType()
    data = b"data"
    ai_file = _make_ai_file(
        "video.mp4", size=len(data), mime_type="video/mp4", content_bytes=data
    )

    result = ai_model_type.prepare_files([ai_file])

    assert len(result) == 0
