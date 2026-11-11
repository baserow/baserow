import asyncio
import json

import httpx
import httpx2
import pytest
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelRequest
from pydantic_ai.models import ModelRequestParameters

from baserow.contrib.agent.replies import create_reply_model
from baserow.contrib.agent.types import AgentReplyRequest
from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel


@pytest.fixture
def configured_reply_model(data_fixture):
    def create(provider_type, model_identifier, reasoning_effort=None):
        agent = data_fixture.create_agent_application(
            provider_type=provider_type,
            model_identifier=model_identifier,
            reasoning_effort=reasoning_effort,
        )
        provider = AIProviderConfig.objects.create(
            workspace=agent.workspace,
            provider_type=provider_type,
            api_key="test-key",
        )
        AIProviderModel.objects.create(
            provider_config=provider, model_identifier=model_identifier
        )
        return create_reply_model(
            AgentReplyRequest(
                reply_id=1,
                workspace=agent.workspace,
                provider_type=agent.provider_type,
                model_identifier=agent.model_identifier,
                reasoning_effort=agent.reasoning_effort,
                instructions="",
                prompt="Hi",
            )
        )

    return create


@pytest.mark.django_db
@pytest.mark.parametrize("effort", [None, "high"], ids=["default", "high"])
@pytest.mark.parametrize("exhausted", [False, True], ids=["answer", "token-limit"])
def test_groq_agent_stream_uses_shared_budget_and_supported_reasoning(
    configured_reply_model, monkeypatch, effort, exhausted
):
    model_name = "openai/gpt-oss-120b"
    sent = []

    async def send(transport, request):
        sent.append(json.loads(request.content))
        assert request.headers["authorization"] == "Bearer test-key"
        deltas = [
            ({"role": "assistant", "reasoning": "Considering the request."}, None),
            ({}, "length") if exhausted else ({"content": "Ready."}, "stop"),
        ]
        chunks = [
            {
                "id": "reply",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": model_name,
                "choices": [
                    {"index": 0, "delta": delta, "finish_reason": finish_reason}
                ],
            }
            for delta, finish_reason in deltas
        ]
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
            + "data: [DONE]\n\n",
        )

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    model, model_settings = configured_reply_model("groq", model_name, effort)

    async def answer():
        async with model:
            async with Agent(model, model_settings=model_settings).run_stream(
                "Hi"
            ) as result:
                return await result.get_output()

    if exhausted:
        with pytest.raises(
            UnexpectedModelBehavior,
            match=r"Model token limit \(16384\) exceeded before any response",
        ):
            asyncio.run(answer())
    else:
        assert asyncio.run(answer()) == "Ready."

    # A larger task budget cannot prevent every exhaustion. It must still fail
    # without retrying a run that might already have made changes through tools.
    assert len(sent) == 1
    assert sent[0]["max_tokens"] == 16384
    assert sent[0]["temperature"] == 0.3
    assert sent[0].get("reasoning_effort") == effort
    assert "reasoning_format" not in sent[0]
    assert model_settings["timeout"] == 30
    assert model_settings["parallel_tool_calls"] is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_name,temperature",
    [
        ("gemini-3.1-pro-preview", None),
        ("gemini-flash-latest", None),
        ("gemini-2.5-flash", 0.3),
    ],
)
def test_google_agent_sanitizes_shared_sampling_defaults(
    configured_reply_model, monkeypatch, model_name, temperature
):
    sent = []

    async def send(transport, request):
        sent.append(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "Ready."}]},
                        "finishReason": "STOP",
                    }
                ],
                "modelVersion": model_name,
            },
        )

    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", send)
    model, model_settings = configured_reply_model("google", model_name)

    async def request():
        async with model:
            return await model.request(
                [ModelRequest.user_text_prompt("Hi")],
                model_settings,
                ModelRequestParameters(),
            )

    response = asyncio.run(request())

    assert response.parts[0].content == "Ready."
    assert len(sent) == 1
    config = sent[0]["generationConfig"]
    assert config["maxOutputTokens"] == 16384
    assert config.get("temperature") == temperature
    if temperature is None:
        assert "temperature" not in config


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_name,effort,thinking_type",
    [
        ("claude-sonnet-4-5", None, None),
        ("claude-sonnet-4-5", "high", "enabled"),
        ("claude-sonnet-4-6", None, None),
        ("claude-sonnet-4-6", "high", "adaptive"),
        ("claude-sonnet-5", None, None),
    ],
)
def test_anthropic_agent_retains_provider_options_and_compatible_thinking_budget(
    configured_reply_model, model_name, effort, thinking_type
):
    model, model_settings = configured_reply_model("anthropic", model_name, effort)
    sent = {}

    class RequestSent(Exception):
        pass

    async def create(**kwargs):
        sent.update(kwargs)
        raise RequestSent()

    model.client.beta.messages.create = create

    async def request():
        async with model:
            await model.request(
                [ModelRequest.user_text_prompt("Hi")],
                model_settings,
                ModelRequestParameters(),
            )

    with pytest.raises(RequestSent):
        asyncio.run(request())

    assert "files-api-2025-04-14" in sent["betas"]
    assert sent["timeout"] == 30
    if thinking_type:
        assert sent["thinking"]["type"] == thinking_type
    else:
        assert not isinstance(sent["thinking"], dict)
    if thinking_type == "enabled":
        assert sent["max_tokens"] > sent["thinking"]["budget_tokens"]
    else:
        assert sent["max_tokens"] == 16384
    if thinking_type or model_name == "claude-sonnet-5":
        assert "temperature" not in (sent.get("extra_body") or {})
    else:
        assert sent["extra_body"]["temperature"] == 0.3
