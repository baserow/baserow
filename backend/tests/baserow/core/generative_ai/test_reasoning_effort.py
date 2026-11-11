import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic_ai.messages import ModelRequest
from pydantic_ai.models import ModelRequestParameters

from baserow.core.generative_ai.registries import generative_ai_model_type_registry


class RequestSent(Exception):
    pass


def send_request(
    provider_type: str,
    model_name: str,
    effort: str | None,
    defaults: dict | None = None,
) -> dict:
    """
    Build the model and its settings the way Agent replies do, then capture the
    arguments the provider's SDK receives.

    :param provider_type: The generative AI model type.
    :param model_name: The model's name.
    :param effort: The chosen reasoning effort.
    :param defaults: Optional task defaults to adapt before sending the request.
    :return: The keyword arguments of the SDK call.
    """

    model_type = generative_ai_model_type_registry.get(provider_type)
    model = model_type.get_ai_model(
        model_name,
        None,
        {"api_key": "test-key", "organization": None, "base_url": None},
    )
    model_settings = {
        **(defaults or {}),
        **model_type.prepare_model_settings(model_name),
    }
    thinking = model_type.get_thinking_level(model_name, model, effort)
    if thinking is not None:
        model_settings["thinking"] = thinking
    if defaults is not None:
        model_settings = model_type.sanitize_default_model_settings(
            model, model_settings
        )
    model_settings = model_type.sanitize_model_settings(model_name, model_settings)

    sent = {}

    async def create(**kwargs):
        sent.update(kwargs)
        raise RequestSent()

    if provider_type == "openai":
        model.client.responses.create = create
    elif provider_type == "anthropic":
        model.client.beta.messages.create = create
    else:
        model.client.chat.completions.create = create
    with pytest.raises(RequestSent):
        asyncio.run(
            model.request(
                [ModelRequest.user_text_prompt("Hi")],
                model_settings,
                model.customize_request_parameters(ModelRequestParameters()),
            )
        )
    return sent


def sent_openai_effort(sent: dict) -> str | None:
    reasoning = sent.get("reasoning")
    return reasoning.get("effort") if isinstance(reasoning, dict) else None


def sent_groq_effort(sent: dict) -> str | None:
    extra_body = sent.get("extra_body")
    return extra_body.get("reasoning_effort") if isinstance(extra_body, dict) else None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_name,effort,sent_effort",
    [
        ("gpt-5.1", None, None),
        ("gpt-5.1", "off", "none"),
        ("gpt-5.1", "low", "low"),
        ("gpt-5.1", "high", "high"),
        # o3 can't stop reasoning, so Off sends its lowest effort.
        ("o3", "off", "low"),
        ("o3", "medium", "medium"),
        # GPT-5 Pro only accepts high.
        ("gpt-5-pro", "off", "high"),
        ("gpt-5-pro", "low", "high"),
        ("gpt-5-pro", "medium", "high"),
        # GPT-5.2 Pro starts at medium.
        ("gpt-5.2-pro", "off", "medium"),
        ("gpt-5.2-pro", "low", "medium"),
        ("gpt-5.2-pro", "high", "high"),
        # Models that can't reason never receive an effort.
        ("gpt-4.1", "high", None),
        # A value this version doesn't know keeps the model's default.
        ("gpt-5.1", "xhigh", None),
    ],
)
def test_openai_requests_carry_an_accepted_reasoning_effort(
    model_name, effort, sent_effort
):
    sent = send_request("openai", model_name, effort)

    assert sent_openai_effort(sent) == sent_effort


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_name,effort,sent_effort",
    [
        ("openai/gpt-oss-120b", "off", "low"),
        ("openai/gpt-oss-120b", "high", "high"),
        # Qwen 3 can only turn reasoning off, so other efforts keep its default.
        ("qwen/qwen3-32b", "off", "none"),
        ("qwen/qwen3-32b", "high", None),
    ],
)
def test_groq_requests_carry_an_accepted_reasoning_effort(
    model_name, effort, sent_effort
):
    sent = send_request("groq", model_name, effort)

    assert sent_groq_effort(sent) == sent_effort


@pytest.mark.parametrize(
    "model_name,effort,sent_effort",
    [
        ("openai/gpt-oss-120b", None, None),
        ("openai/gpt-oss-120b", "off", "low"),
        ("openai/gpt-oss-120b", "low", "low"),
        ("openai/gpt-oss-120b", "medium", "medium"),
        ("openai/gpt-oss-120b", "high", "high"),
        ("openai/gpt-oss-20b", None, None),
        ("openai/gpt-oss-20b", "off", "low"),
        ("openai/gpt-oss-20b", "low", "low"),
        ("openai/gpt-oss-20b", "medium", "medium"),
        ("openai/gpt-oss-20b", "high", "high"),
        ("qwen/qwen3-32b", "off", "none"),
        ("qwen/qwen3-32b", "high", None),
    ],
)
def test_groq_http_requests_preserve_supported_reasoning_and_output_budget(
    monkeypatch, model_name, effort, sent_effort
):
    sent = {}

    async def send(transport, request):
        sent.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "reply",
                "object": "chat.completion",
                "created": 1,
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Ready."},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    model_type = generative_ai_model_type_registry.get("groq")
    model = model_type.get_ai_model(model_name, None, {"api_key": "test-key"})
    model_settings = {"max_tokens": 16384}
    thinking = model_type.get_thinking_level(model_name, model, effort)
    if thinking is not None:
        model_settings["thinking"] = thinking
    model_settings = model_type.sanitize_model_settings(model_name, model_settings)

    async def request():
        async with model:
            return await model.request(
                [ModelRequest.user_text_prompt("Hi")],
                model_settings,
                model.customize_request_parameters(ModelRequestParameters()),
            )

    response = asyncio.run(request())

    assert response.parts[0].content == "Ready."
    assert sent["max_tokens"] == 16384
    assert sent.get("reasoning_effort") == sent_effort
    assert "reasoning_format" not in sent, sent


@pytest.mark.parametrize("provider_effort,expected", [("high", "high"), (None, "low")])
def test_groq_gpt_oss_sanitizing_preserves_explicit_effort_and_input(
    provider_effort, expected
):
    model_type = generative_ai_model_type_registry.get("groq")
    settings = {
        "thinking": "low",
        "groq_reasoning_effort": provider_effort,
        "groq_reasoning_format": "parsed",
        "max_tokens": 16384,
    }

    sanitized = model_type.sanitize_model_settings("openai/gpt-oss-120b", settings)

    assert sanitized == {"groq_reasoning_effort": expected, "max_tokens": 16384}
    assert settings == {
        "thinking": "low",
        "groq_reasoning_effort": provider_effort,
        "groq_reasoning_format": "parsed",
        "max_tokens": 16384,
    }


@pytest.mark.parametrize("model_name", ["qwen/qwen3-32b", "future-model"])
def test_other_groq_models_keep_their_thinking_settings(model_name):
    model_type = generative_ai_model_type_registry.get("groq")
    settings = {"thinking": False, "groq_reasoning_format": "parsed"}

    assert model_type.sanitize_model_settings(model_name, settings) == settings


@pytest.mark.parametrize(
    "model_name,effort,expected_max_tokens",
    [
        ("gpt-4-turbo", None, None),
        ("gpt-4.1", None, None),
        ("gpt-5.1", None, 16384),
        ("gpt-5.1", "high", 16384),
        ("o3", "medium", 16384),
    ],
)
def test_openai_task_defaults_preserve_legacy_limits(
    model_name, effort, expected_max_tokens
):
    from openai import Omit

    settings = {"max_tokens": 16384, "temperature": 0.3}
    sent = send_request("openai", model_name, effort, settings)

    if expected_max_tokens is None:
        assert isinstance(sent["max_output_tokens"], Omit)
        assert sent["temperature"] == 0.3
    else:
        assert sent["max_output_tokens"] == expected_max_tokens
    assert settings == {"max_tokens": 16384, "temperature": 0.3}


@pytest.mark.parametrize(
    "model_name,effort,max_tokens,thinking_type",
    [
        ("claude-3-7-sonnet-latest", None, 4096, None),
        ("claude-3-7-sonnet-latest", "high", 20480, "enabled"),
        ("claude-sonnet-4-6", None, 16384, None),
        ("claude-sonnet-4-6", "high", 16384, "adaptive"),
    ],
)
def test_anthropic_task_defaults_respect_reasoning_and_legacy_limits(
    model_name, effort, max_tokens, thinking_type
):
    sent = send_request(
        "anthropic",
        model_name,
        effort,
        {"max_tokens": 16384, "temperature": 0.3, "top_p": 0.8, "top_k": 10},
    )

    assert sent["max_tokens"] == max_tokens
    if thinking_type:
        assert sent["thinking"]["type"] == thinking_type
        if thinking_type == "enabled":
            assert sent["thinking"]["budget_tokens"] < sent["max_tokens"]
        assert not {"temperature", "top_p", "top_k"}.intersection(
            sent.get("extra_body") or {}
        )
    else:
        assert not isinstance(sent["thinking"], dict)
        assert sent["extra_body"]["temperature"] == 0.3


@pytest.mark.parametrize("maximum,expected", [(8192, 8192), (None, 16384), (0, 16384)])
def test_anthropic_defaults_cap_at_a_known_output_limit_without_mutating_input(
    maximum, expected
):
    model_type = generative_ai_model_type_registry.get("anthropic")
    model = SimpleNamespace(profile={"anthropic_max_output_tokens": maximum})
    settings = {"max_tokens": 16384, "temperature": 0.3}

    sanitized = model_type.sanitize_default_model_settings(model, settings)

    assert sanitized == {"max_tokens": expected, "temperature": 0.3}
    assert settings == {"max_tokens": 16384, "temperature": 0.3}


@pytest.mark.parametrize(
    "model_name,thinking,max_tokens",
    [
        ("us.anthropic.claude-3-7-sonnet-20250219-v1:0", None, None),
        ("us.anthropic.claude-3-7-sonnet-20250219-v1:0", "medium", 16384),
        ("us.anthropic.claude-3-7-sonnet-20250219-v1:0", "high", 20480),
        ("us.anthropic.claude-sonnet-4-6", "high", 16384),
    ],
)
def test_bedrock_claude_task_defaults_leave_room_for_reasoning(
    model_name, thinking, max_tokens
):
    from pydantic_ai.providers.bedrock import BedrockProvider

    model_type = generative_ai_model_type_registry.get("bedrock")
    model = SimpleNamespace(profile=BedrockProvider.model_profile(model_name))
    settings = {
        "max_tokens": 16384,
        "temperature": 0.3,
        "top_p": 0.8,
        "top_k": 10,
        "thinking": thinking,
    }

    sanitized = model_type.sanitize_default_model_settings(model, settings)

    assert sanitized.get("max_tokens") == max_tokens
    assert sanitized["thinking"] == thinking
    if thinking:
        assert not {"temperature", "top_p", "top_k"}.intersection(sanitized)
    else:
        assert sanitized["temperature"] == 0.3
    assert settings["max_tokens"] == 16384
    assert settings["temperature"] == 0.3


@pytest.mark.parametrize(
    "model_name",
    [
        "meta.llama3-8b-instruct-v1:0",
        "meta.llama3-70b-instruct-v1:0",
        "meta.llama3-3-70b-instruct-v1:0",
    ],
)
def test_non_claude_bedrock_models_keep_provider_output_limits(model_name):
    from pydantic_ai.providers.bedrock import BedrockProvider

    model_type = generative_ai_model_type_registry.get("bedrock")
    model = SimpleNamespace(profile=BedrockProvider.model_profile(model_name))
    settings = {"max_tokens": 16384, "temperature": 0.3}

    assert model_type.sanitize_default_model_settings(model, settings) == {
        "temperature": 0.3
    }
    assert settings == {"max_tokens": 16384, "temperature": 0.3}


@pytest.mark.parametrize("maximum,expected", [(8192, 8192), (None, None), (0, None)])
def test_bedrock_claude_defaults_respect_known_output_limits(maximum, expected):
    model_type = generative_ai_model_type_registry.get("bedrock")
    model = SimpleNamespace(
        profile={
            "bedrock_thinking_variant": "anthropic",
            "anthropic_max_output_tokens": maximum,
        }
    )
    settings = {"max_tokens": 16384, "temperature": 0.3}

    sanitized = model_type.sanitize_default_model_settings(model, settings)

    assert sanitized.get("max_tokens") == expected
    assert sanitized["temperature"] == 0.3
    assert settings == {"max_tokens": 16384, "temperature": 0.3}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "provider_type,model_name,effort,applied",
    [
        ("openai", "gpt-5.1", "off", "off"),
        ("openai", "o3", "off", "low"),
        ("openai", "gpt-5-pro", "low", "high"),
        ("openai", "gpt-5.2-pro", "off", "medium"),
        ("openai", "gpt-4.1", "high", None),
        ("groq", "qwen/qwen3-32b", "off", "off"),
        ("groq", "qwen/qwen3-32b", "low", None),
        # Pydantic AI sends Ollama models no effort.
        ("ollama", "qwen3", "high", None),
    ],
)
def test_reasoning_effort_reports_what_the_model_uses(
    provider_type, model_name, effort, applied
):
    model_type = generative_ai_model_type_registry.get(provider_type)
    model = model_type.get_ai_model(
        model_name, None, {"api_key": "test-key", "host": "http://ollama.test"}
    )

    assert model_type.get_reasoning_effort(model_name, model, effort) == applied
