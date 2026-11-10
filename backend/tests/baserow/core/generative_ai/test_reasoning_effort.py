import asyncio

import pytest
from pydantic_ai.messages import ModelRequest
from pydantic_ai.models import ModelRequestParameters

from baserow.core.generative_ai.registries import generative_ai_model_type_registry


class RequestSent(Exception):
    pass


def send_request(provider_type: str, model_name: str, effort: str | None) -> dict:
    """
    Build the model and its settings the way Agent replies do, then capture the
    arguments the provider's SDK receives.

    :param provider_type: The generative AI model type.
    :param model_name: The model's name.
    :param effort: The chosen reasoning effort.
    :return: The keyword arguments of the SDK call.
    """

    model_type = generative_ai_model_type_registry.get(provider_type)
    model = model_type.get_ai_model(model_name, None, {"api_key": "test-key"})
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
