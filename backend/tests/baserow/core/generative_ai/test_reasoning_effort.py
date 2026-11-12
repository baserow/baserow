import asyncio
import json

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
) -> dict:
    """
    Build the model and its settings the way Agent replies do, then capture the
    arguments the provider's SDK receives.

    :param provider_type: The generative AI model type.
    :param model_name: The model's name.
    :param effort: The chosen reasoning effort.
    :return: The keyword arguments of the SDK call.
    """

    model_type = generative_ai_model_type_registry.get(provider_type)
    model = model_type.get_ai_model(
        model_name,
        None,
        {"api_key": "test-key", "organization": None, "base_url": None},
    )
    model_settings = model_type.prepare_model_settings(model_name)
    thinking = model_type.get_thinking_level(model_name, model, effort)
    if thinking is not None:
        model_settings["thinking"] = thinking
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
