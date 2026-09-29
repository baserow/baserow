import base64
import json
from unittest.mock import patch

import httpx2
import pytest

from baserow.core.generative_ai.generative_ai_model_types import (
    XaiGenerativeAIModelType,
)
from baserow_premium.fields.ai_file import AIFile

PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

AMBIENT_PROVIDER_ENVIRONMENT = {
    "XAI_API_KEY": "environment-xai-key",
    "OPENAI_API_KEY": "environment-openai-key",
    "OPENAI_BASE_URL": "https://openai.example.com/v1",
    "OPENAI_ORG_ID": "environment-openai-organization",
    "OPENAI_PROJECT_ID": "environment-openai-project",
}


@pytest.fixture
def ambient_provider_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in AMBIENT_PROVIDER_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)


def _make_ai_file(name: str, mime_type: str, content_bytes: bytes) -> AIFile:
    ai_file = AIFile(
        name=name, original_name=name, size=len(content_bytes), mime_type=mime_type
    )
    ai_file.read_content = lambda: content_bytes  # type: ignore[assignment]
    return ai_file


def _chat_completion(text: str) -> dict:
    return {
        "id": "chatcmpl-xai",
        "object": "chat.completion",
        "created": 1,
        "model": "grok-4.3",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@pytest.mark.django_db
def test_xai_ignores_environment_credentials(
    ambient_provider_environment: None,
) -> None:
    model_type = XaiGenerativeAIModelType()

    assert model_type.get_api_key() is None
    assert model_type.get_enabled_models() == []

    with (
        patch("baserow.core.generative_ai.xai.XaiChatProvider") as provider_class,
        pytest.raises(ValueError, match="An xAI API key is required."),
    ):
        model_type.get_ai_model(
            "grok-4.3", settings_override={"api_key": "", "models": ["grok-4.3"]}
        )
    provider_class.assert_not_called()

    client = model_type.get_ai_model(
        "grok-4.3", settings_override={"api_key": "xai-key", "models": ["grok-4.3"]}
    ).provider.client

    assert client.api_key == "xai-key"
    assert str(client.base_url) == "https://api.x.ai/v1/"
    assert client.organization is None
    assert client.project is None


def test_xai_prompt_sends_chat_completion_with_png_to_xai(
    ambient_provider_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[httpx2.Request] = []

    async def send(
        transport: httpx2.AsyncHTTPTransport, request: httpx2.Request
    ) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json=_chat_completion("A tiny image."))

    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", send)
    model_type = XaiGenerativeAIModelType()
    settings_override = {"api_key": "xai-key", "models": ["grok-4.3"]}
    prepared = model_type.prepare_files(
        [
            _make_ai_file("pixel.png", "image/png", PNG_BYTES),
            _make_ai_file("report.pdf", "application/pdf", b"%PDF-1.4"),
        ],
        settings_override=settings_override,
    )

    output = model_type.prompt(
        "grok-4.3",
        "Describe the image.",
        temperature=1.5,
        settings_override=settings_override,
        content=[ai_file.content for ai_file in prepared],
    )

    assert output == "A tiny image."
    [request] = requests
    assert request.method == "POST"
    assert str(request.url) == "https://api.x.ai/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer xai-key"
    assert "OpenAI-Organization" not in request.headers
    assert "OpenAI-Project" not in request.headers
    body = json.loads(request.content)
    assert body["model"] == "grok-4.3"
    assert body["temperature"] == 1.5
    [message] = body["messages"]
    assert message["role"] == "user"
    text_part, image_part = message["content"]
    assert text_part["type"] == "text"
    assert text_part["text"].startswith("Describe the image.")
    assert image_part["type"] == "image_url"
    assert image_part["image_url"]["url"] == (
        f"data:image/png;base64,{base64.b64encode(PNG_BYTES).decode()}"
    )


@pytest.mark.asyncio
async def test_xai_model_owns_and_closes_its_http_client() -> None:
    model = XaiGenerativeAIModelType().get_ai_model(
        "grok-4.3", settings_override={"api_key": "xai-key"}
    )
    provider = model.provider
    client = provider.client

    assert provider._own_http_client is client._client
    async with model:
        assert not client.is_closed()
    assert client.is_closed()
