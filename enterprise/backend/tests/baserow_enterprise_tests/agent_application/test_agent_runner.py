from unittest.mock import patch

import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from baserow.api.generative_ai.serializers import GenerativeAIModelsSerializer
from baserow.core.generative_ai.registries import (
    GenerativeAIModelType,
    generative_ai_model_type_registry,
)
from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_application.ai_models import resolve_agent_model
from baserow_enterprise.agent_application.exceptions import AgentModelNotConfigured
from baserow_enterprise.agent_application.handler import (
    AgentApplicationHandler,
    AgentChatHandler,
)
from baserow_enterprise.agent_application.models import AgentChat, AgentChatMessage
from baserow_enterprise.agent_application.tasks import run_agent_chat

TEST_ANSWER = "The task is complete."


def _model_function(messages, info):
    return ModelResponse(parts=[TextPart(TEST_ANSWER)])


async def _stream_function(messages, info):
    yield TEST_ANSWER


class AgentRunnerTestModelType(GenerativeAIModelType):
    type = "agent_runner_test"

    def is_enabled(self, workspace=None):
        return True

    def get_enabled_models(self, workspace=None, settings_override=None):
        return ["test-model"]

    def get_ai_model(self, model_name, workspace=None, settings_override=None):
        return FunctionModel(_model_function, stream_function=_stream_function)

    def prompt(self, *args, **kwargs):
        return TEST_ANSWER

    def get_settings_serializer(self):
        return GenerativeAIModelsSerializer


def register_runner_test_model_type():
    try:
        generative_ai_model_type_registry.register(AgentRunnerTestModelType())
    except generative_ai_model_type_registry.already_registered_exception_class:
        pass


@pytest.fixture
def agent_chat_setup(data_fixture):
    register_runner_test_model_type()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent,
        instructions="Do the thing.",
        ai_generative_ai_type="agent_runner_test",
        ai_generative_ai_model="test-model",
    )
    return user, workspace, application, agent


@pytest.mark.django_db
def test_resolve_agent_model_requires_configuration(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="A")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)

    with pytest.raises(AgentModelNotConfigured):
        resolve_agent_model(agent)

    AgentApplicationHandler().update_agent(
        agent,
        ai_generative_ai_type="agent_runner_test",
        ai_generative_ai_model="unknown-model",
    )
    register_runner_test_model_type()

    with pytest.raises(AgentModelNotConfigured):
        resolve_agent_model(agent)


@pytest.mark.django_db(transaction=True)
def test_run_agent_chat_persists_response_and_usage(agent_chat_setup):
    user, workspace, application, agent = agent_chat_setup

    chat = AgentChat.objects.create(agent=agent, user=user)
    prompt = AgentChatHandler().create_message(
        chat, AgentChatMessage.Role.HUMAN, "Please do the thing."
    )

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ) as broadcast_mock:
        run_agent_chat(chat.id, prompt.id)

    chat.refresh_from_db()
    assert chat.status == AgentChat.Status.IDLE
    assert chat.started_on is not None
    assert chat.completed_on is not None
    assert chat.error == ""
    assert chat.message_history

    ai_message = chat.messages.filter(role=AgentChatMessage.Role.AI).get()
    assert ai_message.content == TEST_ANSWER
    assert ai_message.input_tokens is not None
    assert ai_message.output_tokens is not None
    assert chat.total_input_tokens == ai_message.input_tokens
    assert chat.total_output_tokens == ai_message.output_tokens

    # A manual chat gets a generated title.
    assert chat.title

    event_types = [call.delay.call_args_list for call in [broadcast_mock]][0]
    payload_types = [args[0][1]["type"] for args in event_types]
    assert "agent_chat_updated" in payload_types
    chat_events = [
        args[0][1]["event"]["type"]
        for args in event_types
        if args[0][1]["type"] == "agent_chat_event"
    ]
    assert "ai/started" in chat_events
    assert "ai/message" in chat_events


@pytest.mark.django_db(transaction=True)
def test_run_agent_chat_marks_error_when_model_missing(agent_chat_setup, data_fixture):
    user, workspace, application, agent = agent_chat_setup
    AgentApplicationHandler().update_agent(agent, ai_generative_ai_type=None)

    chat = AgentChat.objects.create(agent=agent, user=user)
    prompt = AgentChatHandler().create_message(
        chat, AgentChatMessage.Role.HUMAN, "Hello"
    )

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ) as broadcast_mock:
        run_agent_chat(chat.id, prompt.id)

    chat.refresh_from_db()
    assert chat.status == AgentChat.Status.ERROR
    assert chat.error

    chat_events = [
        args[0][1]["event"]["type"]
        for args in broadcast_mock.delay.call_args_list
        if args[0][1]["type"] == "agent_chat_event"
    ]
    assert "ai/error" in chat_events


@pytest.mark.django_db
def test_cancel_chat_run_sets_flag_and_status(agent_chat_setup):
    from django.core.cache import cache

    from baserow_enterprise.agent_application.runner import (
        get_agent_chat_cancellation_key,
    )

    user, workspace, application, agent = agent_chat_setup
    chat = AgentChat.objects.create(
        agent=agent, user=user, status=AgentChat.Status.IN_PROGRESS
    )

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        AgentChatHandler().cancel_chat_run(chat)

    chat.refresh_from_db()
    assert chat.status == AgentChat.Status.CANCELING
    assert cache.get(get_agent_chat_cancellation_key(chat.uuid))


@pytest.mark.django_db
def test_start_chat_run_rejects_running_chat(agent_chat_setup):
    user, workspace, application, agent = agent_chat_setup
    chat = AgentChat.objects.create(
        agent=agent, user=user, status=AgentChat.Status.IN_PROGRESS
    )
    prompt = AgentChatHandler().create_message(
        chat, AgentChatMessage.Role.HUMAN, "Hello"
    )

    from baserow_enterprise.agent_application.exceptions import AgentChatAlreadyRunning

    with pytest.raises(AgentChatAlreadyRunning):
        AgentChatHandler().start_chat_run(chat, prompt)


def test_split_think_content():
    from baserow_enterprise.agent_application.runner import _split_think_content

    # Plain text is all answer, no thinking.
    assert _split_think_content("Just an answer.") == ("", "Just an answer.")

    # Closed think blocks are thinking; the rest is answer.
    thinking, answer = _split_think_content(
        "<think>step one</think>The answer.<think>step two</think>"
    )
    assert thinking == "step one\nstep two"
    assert answer == "The answer."

    # A trailing unclosed block (still streaming) counts as thinking.
    thinking, answer = _split_think_content("Partial answer<think>still thin")
    assert thinking == "still thin"
    assert answer == "Partial answer"


def test_get_typed_content_delta():
    from pydantic_ai.messages import (
        PartDeltaEvent,
        PartStartEvent,
        TextPart,
        TextPartDelta,
        ThinkingPart,
        ThinkingPartDelta,
    )

    from baserow_enterprise.agent_application.runner import _get_typed_content_delta

    assert _get_typed_content_delta(PartStartEvent(index=0, part=TextPart("Hi"))) == (
        "Hi",
        False,
    )
    assert _get_typed_content_delta(
        PartStartEvent(index=0, part=ThinkingPart("Hmm"))
    ) == ("Hmm", True)
    assert _get_typed_content_delta(
        PartDeltaEvent(index=0, delta=TextPartDelta(" there"))
    ) == (" there", False)
    assert _get_typed_content_delta(
        PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta=" maybe"))
    ) == (" maybe", True)


@pytest.mark.django_db(transaction=True)
def test_unsupported_native_web_search_retries_without_native_tools(
    agent_chat_setup,
):
    import asyncio

    from pydantic_ai import WebSearchTool
    from pydantic_ai.exceptions import ModelHTTPError

    from baserow_enterprise.agent_application.runner import AgentRunner

    user, workspace, application, agent = agent_chat_setup
    chat = AgentChat.objects.create(agent=agent, user=user)
    runner = AgentRunner(chat)
    runner._native_tools = [WebSearchTool()]

    calls = []

    async def fake_consume(user_prompt, message_history, queue, deferred=None):
        calls.append(True)
        if len(calls) == 1:
            raise ModelHTTPError(
                status_code=400,
                model_name="gpt-4.1-nano",
                body={
                    "message": (
                        "Tool 'web_search_preview' is not supported with gpt-4.1-nano."
                    )
                },
            )
        return "answer", None

    runner._consume_agent_events = fake_consume
    answer, result = asyncio.run(runner._stream_agent_run("hi", None, None))

    assert answer == "answer"
    assert len(calls) == 2
    assert any("does not support" in note for note in runner.deps.system_notes)


@pytest.mark.django_db(transaction=True)
def test_unrelated_model_error_is_not_retried(agent_chat_setup):
    import asyncio

    from pydantic_ai import WebSearchTool
    from pydantic_ai.exceptions import ModelHTTPError

    from baserow_enterprise.agent_application.runner import AgentRunner

    user, workspace, application, agent = agent_chat_setup
    chat = AgentChat.objects.create(agent=agent, user=user)
    runner = AgentRunner(chat)
    runner._native_tools = [WebSearchTool()]

    async def fake_consume(user_prompt, message_history, queue, deferred=None):
        raise ModelHTTPError(
            status_code=400,
            model_name="gpt-4.1-nano",
            body={"message": "Invalid request."},
        )

    runner._consume_agent_events = fake_consume
    with pytest.raises(ModelHTTPError):
        asyncio.run(runner._stream_agent_run("hi", None, None))


@pytest.mark.django_db(transaction=True)
def test_retry_chat_run_reruns_last_prompt(agent_chat_setup, api_client, data_fixture):
    user, workspace, application, agent = agent_chat_setup
    token = data_fixture.generate_token(user)

    chat = AgentChat.objects.create(
        agent=agent, user=user, status=AgentChat.Status.ERROR, error="boom"
    )
    AgentChatMessage.objects.create(
        chat=chat, role=AgentChatMessage.Role.HUMAN, content="Do the thing."
    )

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        response = api_client.post(
            f"/api/agent_application/chats/{chat.uuid}/retry/",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == 202, response.json()
    chat.refresh_from_db()
    # The eager celery task completed the retried run.
    assert chat.status == AgentChat.Status.IDLE
    assert chat.error == ""
    assert (
        chat.messages.filter(role=AgentChatMessage.Role.AI).last().content
        == TEST_ANSWER
    )


@pytest.mark.django_db(transaction=True)
def test_retry_chat_run_requires_error_state(
    agent_chat_setup, api_client, data_fixture
):
    user, workspace, application, agent = agent_chat_setup
    token = data_fixture.generate_token(user)

    chat = AgentChat.objects.create(agent=agent, user=user)
    response = api_client.post(
        f"/api/agent_application/chats/{chat.uuid}/retry/",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_AGENT_CHAT_NOT_RETRYABLE"


@pytest.mark.django_db(transaction=True)
def test_oversized_tool_args_do_not_crash_the_run(agent_chat_setup):
    """
    Tool call args beyond the payload limit are truncated to a string; the
    display event must carry that instead of failing validation and killing
    the run.
    """

    from baserow_enterprise.agent_application.chat_types import ToolCallMessage
    from baserow_enterprise.agent_application.runner import _jsonable

    big_args = {"rows": [{"Company Name": "x" * 100} for _ in range(200)]}
    serialized = _jsonable(big_args)
    assert isinstance(serialized, str)
    assert serialized.endswith("… (truncated)")

    message = ToolCallMessage(id="call_1", tool_name="create_rows", args=serialized)
    assert message.args == serialized
