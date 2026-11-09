from unittest.mock import patch

import pytest
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    ModelRequest,
    ToolCallPart,
)
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from baserow.core.chat_runs.models import ChatRunStatus
from baserow.core.chat_runs.tasks import execute_chat_run
from baserow.core.generative_ai.usage import (
    AI_USAGE_FEATURE_ASSISTANT,
    AI_USAGE_KEY_SCOPE_INSTANCE,
    AIUsageLimitExceeded,
    AIUsageScope,
    UsageReportingModel,
    ai_request_completed,
    ai_request_starting,
)
from baserow.core.registries import Plugin, plugin_registry
from baserow_enterprise.assistant.models import AssistantChat
from baserow_enterprise.assistant.runs import ERROR_USAGE_LIMIT_EXCEEDED
from baserow_enterprise.assistant.types import ASSISTANT_MESSAGE_USAGE_REFERENCE
from baserow_enterprise_tests.assistant.runs.utils import ai_message


class Recorder:
    """Records the reported requests, refusing them from `refuse_from` on."""

    def __init__(self, refuse_from=None):
        self.refuse_from = refuse_from
        self.started = []
        self.completed = []

    def on_starting(self, sender, scope, **kwargs):
        self.started.append(scope)
        if self.refuse_from is not None and len(self.started) >= self.refuse_from:
            raise AIUsageLimitExceeded("No AI credits left.")

    def on_completed(self, sender, scope, usage, **kwargs):
        self.completed.append((scope, usage))

    def __enter__(self):
        ai_request_starting.connect(self.on_starting)
        ai_request_completed.connect(self.on_completed)
        return self

    def __exit__(self, *args):
        ai_request_starting.disconnect(self.on_starting)
        ai_request_completed.disconnect(self.on_completed)


@pytest.fixture
def reporting_kuma_model(mocker):
    """Makes Kuma's runs use a scripted model that reports its usage."""

    mocker.patch("baserow_enterprise.assistant.chat_run_type.check_lm_ready_or_raise")

    def _model(stream):
        model = UsageReportingModel(
            FunctionModel(stream_function=stream),
            AIUsageScope(
                "openai",
                "gpt-test",
                AI_USAGE_KEY_SCOPE_INSTANCE,
                feature=AI_USAGE_FEATURE_ASSISTANT,
            ),
        )
        mocker.patch(
            "baserow_enterprise.assistant.model_profiles."
            "ResolvedAssistantModelProfile.create_model",
            return_value=model,
        )

    return _model


@pytest.mark.django_db(transaction=True)
def test_a_run_reports_its_usage_with_the_question_and_shows_its_cost(
    assistant_run, reporting_kuma_model, fast_journal, output_events
):
    async def stream(messages, info):
        yield "Hello"

    reporting_kuma_model(stream)
    run = assistant_run(content="Question")

    class CostPlugin(Plugin):
        type = "cost"

        def get_ai_usage_plugin_data(self, reference_type, reference_ids):
            assert reference_type == ASSISTANT_MESSAGE_USAGE_REFERENCE
            return {reference_ids[0]: {"credits": 2}}

    with (
        patch.dict(plugin_registry.registry, {"cost": CostPlugin()}),
        Recorder() as recorder,
    ):
        execute_chat_run(str(run.id))

    run.refresh_from_db()
    assert run.status == ChatRunStatus.COMPLETED
    ((scope, usage),) = recorder.completed
    assert (scope.feature, scope.reference_type, scope.reference_id) == (
        AI_USAGE_FEATURE_ASSISTANT,
        ASSISTANT_MESSAGE_USAGE_REFERENCE,
        str(run.context["human_message_id"]),
    )
    assert usage.input_tokens > 0
    # The finished answer shows its cost without a reload.
    assert run.outcome["plugin_data"] == {"cost": {"credits": 2}}
    assert output_events[-1]["data"]["message"]["plugin_data"] == {
        "cost": {"credits": 2}
    }


@pytest.mark.django_db(transaction=True)
def test_a_refused_run_fails_with_the_usage_limit(
    assistant_run, reporting_kuma_model, fast_journal
):
    async def stream(messages, info):
        yield "Hello"  # pragma: no cover

    reporting_kuma_model(stream)
    run = assistant_run(content="Question")

    with Recorder(refuse_from=1) as recorder:
        execute_chat_run(str(run.id))

    run.refresh_from_db()
    assert (run.status, run.error_code) == (
        ChatRunStatus.FAILED,
        ERROR_USAGE_LIMIT_EXCEEDED,
    )
    assert ai_message(run).artifacts["run"] == {
        "status": "failed",
        "error_code": ERROR_USAGE_LIMIT_EXCEEDED,
    }
    assert recorder.completed == []


@pytest.mark.django_db(transaction=True)
def test_a_run_refused_halfway_keeps_the_turn(
    assistant_run, reporting_kuma_model, fast_journal
):
    async def stream(messages, info):
        if len([m for m in messages if isinstance(m, ModelRequest)]) == 1:
            yield {
                0: DeltaToolCall(
                    name="list_builders",
                    json_args='{"builder_types": null, "thought": "look"}',
                    tool_call_id="call-1",
                )
            }
        else:
            yield "Done"  # pragma: no cover

    reporting_kuma_model(stream)
    run = assistant_run(content="Question")

    with Recorder(refuse_from=2) as recorder:
        execute_chat_run(str(run.id))

    run.refresh_from_db()
    assert run.error_code == ERROR_USAGE_LIMIT_EXCEEDED
    # The tool may have changed data, so the turn and its history are kept.
    chat = AssistantChat.objects.get(id=run.chat_id)
    history = ModelMessagesTypeAdapter.validate_json(bytes(chat.message_history))
    assert any(
        isinstance(part, ToolCallPart) and part.tool_name == "list_builders"
        for message in history
        for part in message.parts
    )
    assert len(recorder.completed) == 1
