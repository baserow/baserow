from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from botocore.stub import Stubber
from pydantic_ai import BinaryContent, TextContent, UploadedFile

from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.generative_ai.bedrock import create_bedrock_runtime_client
from baserow.core.generative_ai.generative_ai_model_types import (
    AnthropicGenerativeAIModelType,
    BedrockGenerativeAIModelType,
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
@pytest.mark.parametrize(
    ("model_type", "provider_type", "model_identifier"),
    [
        (GoogleGenerativeAIModelType(), "google", "gemini-2.5-flash"),
        (GroqGenerativeAIModelType(), "groq", "openai/gpt-oss-120b"),
        (
            BedrockGenerativeAIModelType(),
            "bedrock",
            "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
        ),
    ],
)
def test_database_only_providers_ignore_legacy_workspace_settings(
    data_fixture, model_type, provider_type, model_identifier
):
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


# --- Bedrock ---

BEDROCK_MODEL = "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
BEDROCK_CONVERSE_RESPONSE = {
    "output": {"message": {"role": "assistant", "content": [{"text": "Hello"}]}},
    "stopReason": "end_turn",
    "usage": {"inputTokens": 3, "outputTokens": 1, "totalTokens": 4},
    "metrics": {"latencyMs": 10},
}


def _bedrock_settings(**overrides: Any) -> dict[str, Any]:
    return {
        "api_key": "stored-api-key",
        "region": "eu-central-1",
        "access_key_id": None,
        "models": [BEDROCK_MODEL],
        **overrides,
    }


def _capture_bedrock_request(model: Any) -> dict[str, str]:
    captured = {}

    def capture(request, **kwargs):
        authorization = request.headers["Authorization"]
        if isinstance(authorization, bytes):
            authorization = authorization.decode()
        captured["authorization"] = authorization
        captured["url"] = request.url
        raise RuntimeError("request captured")

    model.client.meta.events.register("before-send.bedrock-runtime.Converse", capture)
    with pytest.raises(RuntimeError, match="request captured"):
        model.client.converse(
            modelId=BEDROCK_MODEL,
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
        )
    return captured


@pytest.fixture
def aws_environment_credentials(monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "environment-token")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAENVIRONMENTKEY01")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "environment-secret")
    # Baserow's S3/MinIO endpoint env vars must never redirect Bedrock traffic.
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://minio.internal:9000")
    monkeypatch.setenv("AWS_ENDPOINT_URL_BEDROCK_RUNTIME", "http://minio.internal:9000")


def test_bedrock_model_type_is_registered():
    assert isinstance(
        generative_ai_model_type_registry.get("bedrock"), BedrockGenerativeAIModelType
    )


def test_bedrock_sends_the_stored_api_key_as_bearer_token(aws_environment_credentials):
    model = BedrockGenerativeAIModelType().get_ai_model(
        BEDROCK_MODEL, settings_override=_bedrock_settings()
    )

    request = _capture_bedrock_request(model)

    assert request["authorization"] == "Bearer stored-api-key"
    assert request["url"].startswith(
        "https://bedrock-runtime.eu-central-1.amazonaws.com/"
    )


def test_bedrock_signs_with_the_stored_access_key(aws_environment_credentials):
    model = BedrockGenerativeAIModelType().get_ai_model(
        BEDROCK_MODEL,
        settings_override=_bedrock_settings(
            api_key="stored-secret-access-key", access_key_id="AKIASTOREDACCESSKEY1"
        ),
    )

    request = _capture_bedrock_request(model)

    assert request["authorization"].startswith(
        "AWS4-HMAC-SHA256 Credential=AKIASTOREDACCESSKEY1/"
    )
    assert request["url"].startswith(
        "https://bedrock-runtime.eu-central-1.amazonaws.com/"
    )


@pytest.mark.parametrize(
    "overrides", [{"api_key": ""}, {"region": ""}, {"api_key": None}]
)
def test_bedrock_never_falls_back_to_environment_credentials(
    aws_environment_credentials, overrides
):
    with pytest.raises(ValueError, match="Amazon Bedrock"):
        BedrockGenerativeAIModelType().get_ai_model(
            BEDROCK_MODEL, settings_override=_bedrock_settings(**overrides)
        )


@pytest.mark.parametrize("region", ["", None])
def test_bedrock_factory_rejects_a_blank_region_even_with_a_default_region(
    monkeypatch, region
):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    with pytest.raises(ValueError, match="Amazon Bedrock"):
        create_bedrock_runtime_client(region, "stored-api-key")


def test_bedrock_client_bounds_timeouts_and_retries():
    model = BedrockGenerativeAIModelType().get_ai_model(
        BEDROCK_MODEL, settings_override=_bedrock_settings()
    )
    config = model.client.meta.config

    assert config.connect_timeout == 10
    assert config.read_timeout == 300
    # total_max_attempts (unlike max_attempts) round-trips unchanged: 3 total attempts.
    assert config.retries == {"mode": "standard", "total_max_attempts": 3}


def test_bedrock_prompt_returns_the_converse_text():
    client = create_bedrock_runtime_client("eu-central-1", "stored-api-key")
    stubber = Stubber(client)
    stubber.add_response("converse", BEDROCK_CONVERSE_RESPONSE)

    with (
        stubber,
        patch(
            "baserow.core.generative_ai.bedrock.create_bedrock_runtime_client",
            return_value=client,
        ),
    ):
        result = BedrockGenerativeAIModelType().prompt(
            BEDROCK_MODEL, "Say hello", settings_override=_bedrock_settings()
        )

    assert result == "Hello"
    stubber.assert_no_pending_responses()


def test_bedrock_caps_temperature_at_one():
    assert BedrockGenerativeAIModelType().prepare_model_settings(
        BEDROCK_MODEL, 1.7
    ) == {"temperature": 1}


def test_bedrock_known_models_exclude_retired_models():
    models = BedrockGenerativeAIModelType().get_known_models()

    assert "eu.anthropic.claude-sonnet-4-5-20250929-v1:0" in models
    assert "us.amazon.nova-pro-v1:0" in models
    for retired in (
        "anthropic.claude-v2",
        "us.anthropic.claude-3-haiku-20240307-v1:0",
        "eu.anthropic.claude-sonnet-4-20250514-v1:0",
        "amazon.titan-text-express-v1",
        "us.amazon.nova-premier-v1:0",
        "cohere.command-r-plus-v1:0",
    ):
        assert retired not in models


def test_bedrock_is_enabled_only_with_secret_region_and_models():
    model_type = BedrockGenerativeAIModelType()

    assert model_type.is_enabled(settings_override=_bedrock_settings()) is True
    assert (
        model_type.is_enabled(settings_override=_bedrock_settings(region="")) is False
    )
    assert (
        model_type.is_enabled(settings_override=_bedrock_settings(models=[])) is False
    )
    assert (
        model_type.is_enabled(settings_override=_bedrock_settings(api_key="")) is False
    )


def test_bedrock_integration_override_needs_secret_and_region():
    model_type = BedrockGenerativeAIModelType()

    assert (
        model_type.get_atomic_settings_override(
            {"api_key": "secret", "models": [BEDROCK_MODEL]}
        )
        is None
    )
    assert model_type.get_atomic_settings_override(
        {"api_key": "secret", "region": "eu-central-1", "models": [BEDROCK_MODEL]}
    ) == {
        "api_key": "secret",
        "models": [BEDROCK_MODEL],
        "region": "eu-central-1",
        "access_key_id": None,
    }


@pytest.mark.django_db
def test_bedrock_instance_provider_resolves_and_signs_without_settings_override(
    data_fixture,
):
    workspace = data_fixture.create_workspace()
    AIProviderHandler.create_provider(
        "bedrock",
        api_key="stored-secret-access-key",
        extra_settings={
            "region": "eu-central-1",
            "access_key_id": "AKIASTOREDACCESSKEY1",
        },
        models_data=[{"model_identifier": BEDROCK_MODEL}],
    )

    model_type = BedrockGenerativeAIModelType()

    assert model_type.get_region() == "eu-central-1"
    assert model_type.get_access_key_id() == "AKIASTOREDACCESSKEY1"
    assert model_type.get_region(workspace) == "eu-central-1"
    assert model_type.get_access_key_id(workspace) == "AKIASTOREDACCESSKEY1"

    model = model_type.get_ai_model(BEDROCK_MODEL, workspace)
    request = _capture_bedrock_request(model)

    assert request["authorization"].startswith(
        "AWS4-HMAC-SHA256 Credential=AKIASTOREDACCESSKEY1/"
    )


def test_bedrock_supports_files():
    assert BedrockGenerativeAIModelType().supports_files is True


def test_bedrock_prepare_files_uses_native_blocks_and_inlines_small_text():
    files = [
        _make_ai_file("photo.png", 1000, "image/png", b"png"),
        _make_ai_file("report.pdf", 1000, "application/pdf", b"pdf"),
        _make_ai_file(
            "notes.docx",
            1000,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            b"docx",
        ),
        _make_ai_file("large.csv", 20 * 1024, "text/csv", b"a,b\n1,2\n"),
        _make_ai_file("small.txt", 10, "text/plain", b"hello"),
        _make_ai_file(
            "slides.pptx",
            1000,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            b"pptx",
        ),
    ]

    prepared = BedrockGenerativeAIModelType().prepare_files(files)

    contents = {ai_file.name: ai_file.content for ai_file in prepared}
    assert set(contents) == {
        "photo.png",
        "report.pdf",
        "notes.docx",
        "large.csv",
        "small.txt",
    }
    for name in ("photo.png", "report.pdf", "notes.docx", "large.csv"):
        assert isinstance(contents[name], BinaryContent)
    assert isinstance(contents["small.txt"], TextContent)


def test_bedrock_prepare_files_never_embeds_html_as_a_document():
    # Uploads store HTML as application/octet-stream, which Converse can't map.
    files = [
        _make_ai_file("large.html", 20 * 1024, "application/octet-stream", b"<p>x</p>"),
        _make_ai_file("small.html", 10, "application/octet-stream", b"<p>hi</p>"),
    ]

    prepared = BedrockGenerativeAIModelType().prepare_files(files)

    assert [ai_file.name for ai_file in prepared] == ["small.html"]
    assert isinstance(prepared[0].content, TextContent)


def test_bedrock_prepare_files_respects_per_kind_limits():
    images = [
        _make_ai_file(f"{index}.png", 10, "image/png", b"png") for index in range(11)
    ] + [_make_ai_file(f"{index}.jpg", 10, "image/jpeg", b"jpg") for index in range(10)]
    documents = [
        _make_ai_file(f"{index}.pdf", 10, "application/pdf", b"pdf")
        for index in range(6)
    ]
    oversized = [
        _make_ai_file("huge.jpg", 3_750_001, "image/jpeg", b"jpg"),
        _make_ai_file("huge.pdf", 4_500_001, "application/pdf", b"pdf"),
    ]

    prepared = BedrockGenerativeAIModelType().prepare_files(
        oversized + images + documents
    )

    names = [ai_file.name for ai_file in prepared]
    image_names = [name for name in names if name.endswith((".png", ".jpg"))]
    assert len(image_names) == 20
    assert sum(name.endswith(".pdf") for name in names) == 5
    assert "huge.jpg" not in names and "huge.pdf" not in names


def test_bedrock_prepare_files_respects_total_payload_budget():
    documents = [
        _make_ai_file(f"{index}.pdf", 4_000_000, "application/pdf", b"pdf")
        for index in range(4)
    ]

    prepared = BedrockGenerativeAIModelType().prepare_files(documents)

    assert [ai_file.name for ai_file in prepared] == ["0.pdf", "1.pdf", "2.pdf"]


def test_bedrock_prompt_sends_prepared_files_as_valid_converse_blocks():
    model_type = BedrockGenerativeAIModelType()
    prepared = model_type.prepare_files(
        [
            _make_ai_file("photo.png", 3, "image/png", b"png"),
            _make_ai_file("report.pdf", 3, "application/pdf", b"pdf"),
        ]
    )
    client = create_bedrock_runtime_client("eu-central-1", "stored-api-key")
    stubber = Stubber(client)
    stubber.add_response("converse", BEDROCK_CONVERSE_RESPONSE)

    with (
        stubber,
        patch(
            "baserow.core.generative_ai.bedrock.create_bedrock_runtime_client",
            return_value=client,
        ),
    ):
        result = model_type.prompt(
            BEDROCK_MODEL,
            "Describe the files",
            settings_override=_bedrock_settings(),
            content=[ai_file.content for ai_file in prepared],
        )

    assert result == "Hello"
    stubber.assert_no_pending_responses()
