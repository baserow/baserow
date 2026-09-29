import base64
import json
from dataclasses import dataclass, field
from unittest.mock import patch

import httpx2
import pytest
from pydantic import BaseModel
from pydantic_ai import Agent

from baserow.core.generative_ai.generative_ai_model_types import (
    ZaiGenerativeAIModelType,
)
from baserow.core.generative_ai.lifecycle import run_agent_sync_with_model
from baserow_premium.fields.ai_file import AIFile

PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
ZAI_SETTINGS = {"api_key": "zai-key", "models": ["glm-5.2"]}

AMBIENT_PROVIDER_ENVIRONMENT = {
    "ZAI_API_KEY": "environment-zai-key",
    "OPENAI_API_KEY": "environment-openai-key",
    "OPENAI_BASE_URL": "https://openai.example.com/v1",
    "OPENAI_ORG_ID": "environment-openai-organization",
    "OPENAI_PROJECT_ID": "environment-openai-project",
}


class CityAnswer(BaseModel):
    city: str


@pytest.fixture
def ambient_provider_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in AMBIENT_PROVIDER_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)


@dataclass
class FakeZaiApi:
    responses: list[dict] = field(default_factory=list)
    requests: list[httpx2.Request] = field(default_factory=list)

    def last_body(self) -> dict:
        return json.loads(self.requests[-1].content)


@pytest.fixture
def zai_api(monkeypatch: pytest.MonkeyPatch) -> FakeZaiApi:
    api = FakeZaiApi()

    async def send(
        transport: httpx2.AsyncHTTPTransport, request: httpx2.Request
    ) -> httpx2.Response:
        api.requests.append(request)
        return httpx2.Response(200, json=api.responses.pop(0))

    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", send)
    return api


def _make_ai_file(name: str, mime_type: str, content_bytes: bytes) -> AIFile:
    ai_file = AIFile(
        name=name, original_name=name, size=len(content_bytes), mime_type=mime_type
    )
    ai_file.read_content = lambda: content_bytes  # type: ignore[assignment]
    return ai_file


def _chat_completion(message: dict, finish_reason: str = "stop") -> dict:
    return {
        "id": "chatcmpl-zai",
        "object": "chat.completion",
        "created": 1,
        "model": "glm-5.2",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", **message},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@pytest.mark.django_db
def test_zai_ignores_environment_credentials(
    ambient_provider_environment: None,
) -> None:
    model_type = ZaiGenerativeAIModelType()

    assert model_type.get_api_key() is None
    assert model_type.get_enabled_models() == []

    client = model_type.get_ai_model(
        "glm-5.2", settings_override=ZAI_SETTINGS
    ).provider.client

    assert client.api_key == "zai-key"
    assert str(client.base_url) == "https://api.z.ai/api/paas/v4/"
    assert client.organization is None
    assert client.project is None


def test_zai_blank_api_key_raises_before_any_client_exists(
    ambient_provider_environment: None,
) -> None:
    with (
        patch("baserow.core.generative_ai.zai.ZaiChatProvider") as provider_class,
        pytest.raises(ValueError, match="A Z.ai API key is required."),
    ):
        ZaiGenerativeAIModelType().get_ai_model(
            "glm-5.2", settings_override={"api_key": "", "models": ["glm-5.2"]}
        )
    provider_class.assert_not_called()


def test_zai_prompt_sends_chat_completion_with_png_to_zai(
    ambient_provider_environment: None, zai_api: FakeZaiApi
) -> None:
    zai_api.responses.append(_chat_completion({"content": "A tiny image."}))
    model_type = ZaiGenerativeAIModelType()
    png = _make_ai_file("pixel.png", "image/png", PNG_BYTES)
    prepared = model_type.prepare_files(
        [png, _make_ai_file("report.pdf", "application/pdf", b"%PDF-1.4")],
        settings_override=ZAI_SETTINGS,
    )

    output = model_type.prompt(
        "glm-5.2",
        "Describe the image.",
        temperature=1.5,
        settings_override=ZAI_SETTINGS,
        content=[ai_file.content for ai_file in prepared],
        model_settings_override={"max_tokens": 64},
    )

    assert prepared == [png]
    assert output == "A tiny image."
    [request] = zai_api.requests
    assert request.method == "POST"
    assert str(request.url) == "https://api.z.ai/api/paas/v4/chat/completions"
    assert request.headers["Authorization"] == "Bearer zai-key"
    assert "OpenAI-Organization" not in request.headers
    assert "OpenAI-Project" not in request.headers
    body = zai_api.last_body()
    assert body["model"] == "glm-5.2"
    assert body["temperature"] == 1
    assert body["max_tokens"] == 64
    assert "max_completion_tokens" not in body
    assert body["thinking"] == {"clear_thinking": True}
    [message] = body["messages"]
    assert message["role"] == "user"
    text_part, image_part = message["content"]
    assert text_part["type"] == "text"
    assert text_part["text"].startswith("Describe the image.")
    assert image_part["type"] == "image_url"
    assert image_part["image_url"]["url"] == (
        f"data:image/png;base64,{base64.b64encode(PNG_BYTES).decode()}"
    )


def test_zai_prompt_without_max_tokens_sends_no_token_cap(
    zai_api: FakeZaiApi,
) -> None:
    zai_api.responses.append(_chat_completion({"content": "OK"}))

    ZaiGenerativeAIModelType().prompt(
        "glm-5.2", "Say OK.", settings_override=ZAI_SETTINGS
    )

    body = zai_api.last_body()
    assert "max_tokens" not in body
    assert "max_completion_tokens" not in body


def test_zai_output_tool_agent_sends_auto_tool_choice_without_strict(
    zai_api: FakeZaiApi,
) -> None:
    zai_api.responses.append(
        _chat_completion(
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "final_result",
                            "arguments": json.dumps({"city": "Rome"}),
                        },
                    }
                ],
            },
            finish_reason="tool_calls",
        )
    )
    model = ZaiGenerativeAIModelType().get_ai_model(
        "glm-5.2", settings_override=ZAI_SETTINGS
    )

    result = run_agent_sync_with_model(
        Agent(output_type=CityAnswer), "Capital of Italy?", model=model
    )

    assert result.output == CityAnswer(city="Rome")
    assert len(zai_api.requests) == 1
    body = zai_api.last_body()
    assert body["tool_choice"] == "auto"
    assert [tool["function"]["name"] for tool in body["tools"]] == ["final_result"]
    assert all("strict" not in tool["function"] for tool in body["tools"])


@pytest.mark.asyncio
async def test_zai_model_owns_and_closes_its_http_client() -> None:
    model = ZaiGenerativeAIModelType().get_ai_model(
        "glm-5.2", settings_override={"api_key": "zai-key"}
    )
    provider = model.provider
    client = provider.client

    assert provider._own_http_client is client._client
    async with model:
        assert not client.is_closed()
    assert client.is_closed()
