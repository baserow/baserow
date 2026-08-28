from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai import BinaryContent, TextContent, UploadedFile

from baserow.core.generative_ai.generative_ai_model_types import (
    AnthropicGenerativeAIModelType,
    GoogleGenerativeAIModelType,
    GroqGenerativeAIModelType,
    MistralGenerativeAIModelType,
    OllamaGenerativeAIModelType,
    OpenAIGenerativeAIModelType,
    OpenRouterGenerativeAIModelType,
)
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
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


def test_google_and_groq_model_types_are_registered():
    assert isinstance(
        generative_ai_model_type_registry.get("google"),
        GoogleGenerativeAIModelType,
    )
    assert isinstance(
        generative_ai_model_type_registry.get("groq"), GroqGenerativeAIModelType
    )


def test_openai_supports_files():
    ai_model_type = OpenAIGenerativeAIModelType()
    assert ai_model_type.supports_files is True


def test_openai_file_clients_are_closed_after_upload_and_delete():
    handler = OpenAIGenerativeAIModelType().file_handler
    client = MagicMock()
    client.__enter__.return_value = client
    client.files.create.return_value.id = "file-openai"
    ai_file = _make_ai_file("a.pdf", 3, "application/pdf", b"pdf")

    with patch.object(handler, "_get_upload_client", return_value=client):
        handler._upload(ai_file)
        handler.delete_file(ai_file)

    assert client.__enter__.call_count == 2
    assert client.__exit__.call_count == 2
    client.files.delete.assert_called_once_with("file-openai")


@pytest.mark.asyncio
async def test_openai_model_owns_and_closes_its_http_client():
    model = OpenAIGenerativeAIModelType().get_ai_model(
        "gpt-5-mini",
        settings_override={
            "api_key": "openai-key",
            "base_url": None,
            "organization": "openai-organization",
        },
    )
    provider = model.provider
    client = provider.client

    assert client.organization == "openai-organization"
    assert provider._own_http_client is client._client
    async with model:
        assert not client.is_closed()
    assert client.is_closed()


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


def test_anthropic_file_clients_are_closed_after_upload_and_delete():
    handler = AnthropicGenerativeAIModelType().file_handler
    client = MagicMock()
    client.__enter__.return_value = client
    client.beta.files.upload.return_value.id = "file-anthropic"
    ai_file = _make_ai_file("a.pdf", 3, "application/pdf", b"pdf")

    with patch.object(handler, "_get_sync_client", return_value=client):
        handler._upload(ai_file)
        handler.delete_file(ai_file)

    assert client.__enter__.call_count == 2
    assert client.__exit__.call_count == 2
    client.beta.files.delete.assert_called_once_with("file-anthropic")


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


# --- Google (embed-only) ---


def test_google_supports_files():
    assert GoogleGenerativeAIModelType().supports_files is True


def test_google_prepare_files_image_and_pdf_are_embedded():
    ai_model_type = GoogleGenerativeAIModelType()
    image = _make_ai_file(
        "photo.png",
        size=8,
        mime_type="image/png",
        content_bytes=b"image123",
    )
    pdf = _make_ai_file(
        "document.pdf",
        size=8,
        mime_type="application/pdf",
        content_bytes=b"pdf-data",
    )

    result = ai_model_type.prepare_files([image, pdf])

    assert result == [image, pdf]
    assert isinstance(image.content, BinaryContent)
    assert isinstance(pdf.content, BinaryContent)


def test_google_prepare_files_respects_conservative_inline_request_budget():
    ai_model_type = GoogleGenerativeAIModelType()
    limit = ai_model_type.file_handler._MAX_EMBED_PAYLOAD_BYTES
    at_limit = _make_ai_file(
        "at-limit.png",
        size=limit,
        mime_type="image/png",
        content_bytes=b"image",
    )
    over_limit = _make_ai_file(
        "over-limit.png",
        size=limit + 1,
        mime_type="image/png",
        content_bytes=b"image",
    )

    result = ai_model_type.prepare_files([at_limit, over_limit])

    assert result == [at_limit]
    assert isinstance(at_limit.content, BinaryContent)
    assert over_limit.content is None


def test_google_prepare_files_applies_budget_across_multiple_files():
    ai_model_type = GoogleGenerativeAIModelType()
    limit = ai_model_type.file_handler._MAX_EMBED_PAYLOAD_BYTES
    first = _make_ai_file(
        "first.pdf",
        size=limit // 2,
        mime_type="application/pdf",
        content_bytes=b"pdf",
    )
    second = _make_ai_file(
        "second.png",
        size=limit // 2,
        mime_type="image/png",
        content_bytes=b"image",
    )
    no_room = _make_ai_file(
        "third.png",
        size=1,
        mime_type="image/png",
        content_bytes=b"image",
    )

    result = ai_model_type.prepare_files([first, second, no_room])

    assert result == [first, second]
    assert no_room.content is None


def test_google_constructs_native_model_with_safe_timeout():
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    ai_model_type = GoogleGenerativeAIModelType()
    model = ai_model_type.get_ai_model(
        "gemini-2.5-flash",
        settings_override={
            "api_key": "google-key",
            "models": ["gemini-2.5-flash"],
        },
    )
    second_model = ai_model_type.get_ai_model(
        "gemini-2.5-flash",
        settings_override={
            "api_key": "google-key",
            "models": ["gemini-2.5-flash"],
        },
    )

    assert isinstance(model, GoogleModel)
    assert isinstance(model._provider, GoogleProvider)
    assert model.model_name == "gemini-2.5-flash"
    assert model._provider.client._api_client.api_key == "google-key"
    assert model._provider.client._api_client._http_options.timeout >= 10_000
    assert (
        model._provider._own_http_client
        is model._provider.client._api_client._async_httpx_client
    )
    assert (
        model._provider.client._api_client._async_httpx_client
        is not second_model._provider.client._api_client._async_httpx_client
    )


@pytest.mark.parametrize(
    "model_identifier",
    ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-flash-latest"],
)
def test_google_current_models_use_provider_default_sampling(model_identifier):
    settings = GoogleGenerativeAIModelType().sanitize_model_settings(
        model_identifier,
        {"temperature": 0.1, "top_p": 0.9, "top_k": 40, "timeout": 20},
    )

    assert settings == {"timeout": 20}


def test_google_older_models_keep_supported_sampling_settings():
    settings = GoogleGenerativeAIModelType().prepare_model_settings(
        "gemini-2.5-flash", temperature=0.1
    )

    assert settings["temperature"] == 0.1


# --- Groq ---


def test_groq_does_not_advertise_provider_level_file_support():
    assert GroqGenerativeAIModelType().supports_files is False


def test_groq_constructs_native_model_with_configured_credentials():
    from pydantic_ai.models.groq import GroqModel
    from pydantic_ai.providers.groq import GroqProvider

    ai_model_type = GroqGenerativeAIModelType()
    model = ai_model_type.get_ai_model(
        "openai/gpt-oss-120b",
        settings_override={
            "api_key": "groq-key",
            "models": ["openai/gpt-oss-120b"],
        },
    )

    assert isinstance(model, GroqModel)
    assert isinstance(model._provider, GroqProvider)
    assert model.model_name == "openai/gpt-oss-120b"
    assert model._provider.client.api_key == "groq-key"
    assert model.profile.get("supports_tools") is not False


def test_google_and_groq_do_not_fall_back_to_legacy_kuma_credentials(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "legacy-google-key")
    monkeypatch.setenv("GROQ_API_KEY", "legacy-groq-key")

    for model_type, model_identifier in (
        (GoogleGenerativeAIModelType(), "gemini-2.5-flash"),
        (GroqGenerativeAIModelType(), "openai/gpt-oss-120b"),
    ):
        with pytest.raises(ValueError, match="API key is required"):
            model_type.get_ai_model(
                model_identifier,
                settings_override={"api_key": "", "models": [model_identifier]},
            )


@pytest.mark.django_db
@pytest.mark.parametrize("feature_flags", [[], ["ai-providers"]])
@pytest.mark.parametrize(
    ("model_type", "provider_type", "model_identifier"),
    [
        (GoogleGenerativeAIModelType(), "google", "gemini-2.5-flash"),
        (GroqGenerativeAIModelType(), "groq", "openai/gpt-oss-120b"),
    ],
)
def test_database_only_providers_ignore_legacy_workspace_settings(
    data_fixture, settings, feature_flags, model_type, provider_type, model_identifier
):
    settings.FEATURE_FLAGS = feature_flags
    workspace = data_fixture.create_workspace(
        generative_ai_models_settings={
            provider_type: {
                "api_key": "legacy-secret",
                "models": [model_identifier],
            }
        }
    )

    assert model_type.get_api_key(workspace) is None
    assert model_type.get_enabled_models(workspace) == []


@pytest.mark.asyncio
async def test_openrouter_model_owns_and_closes_its_http_client():
    model = OpenRouterGenerativeAIModelType().get_ai_model(
        "openai/gpt-oss-120b",
        settings_override={
            "api_key": "openrouter-key",
            "organization": "openrouter-organization",
        },
    )
    provider = model.provider
    client = provider.client

    assert client.organization == "openrouter-organization"
    assert provider._own_http_client is client._client
    async with model:
        assert not client.is_closed()
    assert client.is_closed()


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
