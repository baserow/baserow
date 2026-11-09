from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgiref.sync import async_to_sync
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.usage import RequestUsage

from baserow.core.generative_ai.usage import (
    AI_USAGE_FEATURE_ASSISTANT,
    AI_USAGE_KEY_SCOPE_ENVIRONMENT,
    AI_USAGE_KEY_SCOPE_EXPLICIT,
    AI_USAGE_KEY_SCOPE_INSTANCE,
    AI_USAGE_KEY_SCOPE_WORKSPACE,
    AIUsageLimitExceeded,
    UsageReportingModel,
    ai_request_completed,
    ai_request_starting,
)
from baserow_enterprise.assistant import model_profiles
from baserow_enterprise.assistant.model_profiles import ResolvedAssistantModelProfile
from baserow_enterprise.assistant.retrying_model import RetryingModel


def profile(source, database_model=None):
    return ResolvedAssistantModelProfile(
        model_string="openai:gpt-luna",
        source=source,
        workspace=None,
        database_model=database_model,
    )


def database_model(workspace_id):
    return SimpleNamespace(
        model_identifier="gpt-luna",
        provider_config=SimpleNamespace(
            provider_type="openai", workspace_id=workspace_id
        ),
    )


class Recorder:
    def __init__(self, refuse=False):
        self.refuse = refuse
        self.started = []
        self.completed = []

    def on_starting(self, sender, scope, **kwargs):
        self.started.append(scope)
        if self.refuse:
            raise AIUsageLimitExceeded("No credits left.")

    def on_completed(self, sender, scope, usage, **kwargs):
        self.completed.append((scope, usage))

    def __enter__(self):
        ai_request_starting.connect(self.on_starting)
        ai_request_completed.connect(self.on_completed)
        return self

    def __exit__(self, *args):
        ai_request_starting.disconnect(self.on_starting)
        ai_request_completed.disconnect(self.on_completed)


def test_the_usage_scope_tells_whose_credentials_kuma_uses():
    instance = profile("database", database_model(None)).usage_scope
    assert (instance.provider_type, instance.model, instance.key_scope) == (
        "openai",
        "gpt-luna",
        AI_USAGE_KEY_SCOPE_INSTANCE,
    )
    assert instance.feature == AI_USAGE_FEATURE_ASSISTANT

    workspace = profile("database", database_model(1)).usage_scope
    assert workspace.key_scope == AI_USAGE_KEY_SCOPE_WORKSPACE

    legacy = profile("legacy").usage_scope
    assert (legacy.provider_type, legacy.model, legacy.key_scope) == (
        "openai",
        "gpt-luna",
        AI_USAGE_KEY_SCOPE_ENVIRONMENT,
    )

    assert profile("explicit").usage_scope.key_scope == AI_USAGE_KEY_SCOPE_EXPLICIT


def test_kuma_models_report_their_usage_around_the_retries():
    model = profile("legacy").create_model()

    assert isinstance(model, UsageReportingModel)
    assert isinstance(model.wrapped, RetryingModel)
    assert model.usage_scope.key_scope == AI_USAGE_KEY_SCOPE_ENVIRONMENT
    assert model.usage_scope.feature == AI_USAGE_FEATURE_ASSISTANT

    assert isinstance(profile("legacy").create_model(report_usage=False), RetryingModel)


def test_the_readiness_probe_is_not_reported_nor_refused():
    probed = []
    model_profiles._clear_process_local_model_readiness_cache()
    try:
        with (
            patch.object(
                model_profiles,
                "test_model_text_and_tool_calling",
                side_effect=lambda model, **kwargs: probed.append(model),
            ),
            Recorder(refuse=True) as recorder,
        ):
            model_profiles.check_lm_ready_or_raise(model_profile=profile("legacy"))
    finally:
        model_profiles._clear_process_local_model_readiness_cache()

    (model,) = probed
    assert not isinstance(model, UsageReportingModel)
    assert recorder.started == []


def retrying(inner):
    model = RetryingModel(inner, base_delay=0)
    model._resolved = inner
    return model


@pytest.mark.django_db
def test_a_stream_falling_back_to_a_request_is_reported_once():
    inner = MagicMock()

    @asynccontextmanager
    async def failing_request_stream(*args, **kwargs):
        raise Exception("Failed to parse tool call arguments as JSON")
        yield  # pragma: no cover

    inner.request_stream = failing_request_stream
    inner.request = AsyncMock(
        return_value=ModelResponse(
            parts=[TextPart(content="fallback")],
            usage=RequestUsage(input_tokens=10, output_tokens=5),
        )
    )
    model = UsageReportingModel(retrying(inner), profile("legacy").usage_scope)

    async def run():
        async with model.request_stream(
            [], None, ModelRequestParameters(function_tools=[], output_tools=[])
        ) as stream:
            return [event async for event in stream]

    with Recorder() as recorder:
        assert async_to_sync(run)()

    assert inner.request.await_count == 1
    assert len(recorder.started) == 1
    ((_, usage),) = recorder.completed
    assert (usage.input_tokens, usage.output_tokens) == (10, 5)
