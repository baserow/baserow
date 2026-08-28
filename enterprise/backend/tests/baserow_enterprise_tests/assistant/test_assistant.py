import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test.utils import override_settings

import pytest
from asgiref.sync import async_to_sync
from pydantic_ai.messages import PartStartEvent
from pydantic_ai.messages import TextPart as PaiTextPart

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_FEATURE_MODE_DISABLED,
    AI_PROVIDER_FEATURE_MODE_MODEL,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel
from baserow_enterprise.assistant.agents import dynamic_license_tier
from baserow_enterprise.assistant.assistant import (
    Assistant,
    _get_workspace_license_type,
    compact_message_history,
)
from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.exceptions import (
    AssistantConfiguredModelNotAvailableError,
    AssistantModelDisabledError,
    AssistantModelNotSupportedError,
)
from baserow_enterprise.assistant.model_profiles import (
    _clear_process_local_model_readiness_cache,
    check_lm_ready_or_raise,
    get_assistant_model,
    get_model_string,
    resolve_assistant_model,
)
from baserow_enterprise.assistant.models import AssistantChat, AssistantChatMessage
from baserow_enterprise.assistant.prompts import AGENT_SYSTEM_PROMPT
from baserow_enterprise.assistant.types import (
    AiMessage,
    AiMessageChunk,
    AiStartedMessage,
    AiThinkingMessage,
    ApplicationUIContext,
    ChatTitleMessage,
    HumanMessage,
    TableUIContext,
    UIContext,
    UserUIContext,
    ViewUIContext,
    WorkspaceUIContext,
)


@pytest.fixture(autouse=True)
def mock_posthog():
    with patch("baserow_enterprise.assistant.telemetry.get_posthog_client") as mock:
        mock.return_value = MagicMock()
        yield mock


@pytest.fixture(autouse=True)
def _set_test_model(settings):
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = "groq/test-model"


@pytest.fixture
def scoped_assistant_model(mocker):
    """Provide Assistant with a model whose async lifecycle can be asserted."""

    model = MagicMock()
    model.__aenter__.return_value = model
    model.__aexit__.return_value = None
    mocker.patch(
        "baserow_enterprise.assistant.model_profiles."
        "ResolvedAssistantModelProfile.create_model",
        return_value=model,
    )
    return model


def assert_model_scope_closed(model):
    model.__aenter__.assert_awaited_once_with()
    model.__aexit__.assert_awaited_once()


@pytest.mark.django_db
def test_assistant_propagates_request_model_profile_to_tool_helpers(
    enterprise_data_fixture,
    scoped_assistant_model,
):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    chat = AssistantChat.objects.create(user=user, workspace=workspace)
    model_profile = resolve_assistant_model(
        workspace=workspace,
        model="groq:request-model",
    )

    assistant = Assistant(chat, model_profile=model_profile)

    assert assistant._tool_helpers.model_profile is model_profile


@pytest.mark.asyncio
async def test_astream_messages_closes_inner_stream_before_model_scope():
    lifecycle_events = []

    @asynccontextmanager
    async def model_scope():
        lifecycle_events.append("model-enter")
        try:
            yield
        finally:
            lifecycle_events.append("model-exit")

    async def inner_stream(_message):
        lifecycle_events.append("stream-enter")
        try:
            yield AiStartedMessage(message_id="1")
        finally:
            lifecycle_events.append("stream-exit")

    assistant = Assistant.__new__(Assistant)
    assistant._model = model_scope()
    assistant._astream_messages_in_model_context = inner_stream
    stream = assistant.astream_messages(HumanMessage(content="Hello"))

    await anext(stream)
    await stream.aclose()

    assert lifecycle_events == [
        "model-enter",
        "stream-enter",
        "stream-exit",
        "model-exit",
    ]


# ---------------------------------------------------------------------------
# Mock helpers for pydantic-ai's run_stream_events async generator
# ---------------------------------------------------------------------------


async def _mock_run_stream_events(
    answer: str, messages_json: bytes = b"[]"
) -> AsyncIterator[Any]:
    """
    Async generator that mimics the events pulled from ``main_agent.run_stream_events()``,
    yielding PartStartEvent, then AgentRunResultEvent.
    """
    from pydantic_ai.run import AgentRunResultEvent

    # Emit a text part start with the full answer
    yield PartStartEvent(index=0, part=PaiTextPart(content=answer))

    # Emit the final result event
    mock_result = MagicMock()
    mock_result.output = answer
    mock_result.all_messages_json.return_value = messages_json
    yield AgentRunResultEvent(result=mock_result)


@asynccontextmanager
async def _mock_run_stream_events_cm(
    events: AsyncIterator[Any],
) -> AsyncIterator[AsyncIterator[Any]]:
    """run_stream_events() is a context manager yielding an iterator, so the double must be too."""

    yield events


def make_mock_run_stream_events_side_effect(
    answer: str, messages_json: bytes = b"[]"
) -> Callable[..., AbstractAsyncContextManager[AsyncIterator[Any]]]:
    """Return a side_effect callable returning the context manager run_stream_events() now yields."""

    def side_effect(
        *args: Any, **kwargs: Any
    ) -> AbstractAsyncContextManager[AsyncIterator[Any]]:
        return _mock_run_stream_events_cm(
            _mock_run_stream_events(answer, messages_json)
        )

    return side_effect


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAssistantDeps:
    """Test the AssistantDeps class for source tracking."""

    def test_extend_sources_deduplicates(self):
        deps = AssistantDeps(
            user=MagicMock(),
            workspace=MagicMock(),
            tool_helpers=MagicMock(),
        )

        deps.extend_sources(["https://example.com/doc1", "https://example.com/doc2"])
        assert deps.sources == [
            "https://example.com/doc1",
            "https://example.com/doc2",
        ]

        deps.extend_sources(["https://example.com/doc2", "https://example.com/doc3"])

        assert deps.sources == [
            "https://example.com/doc1",
            "https://example.com/doc2",
            "https://example.com/doc3",
        ]

    def test_extend_sources_preserves_order(self):
        deps = AssistantDeps(
            user=MagicMock(),
            workspace=MagicMock(),
            tool_helpers=MagicMock(),
        )

        deps.extend_sources(["https://example.com/a"])
        deps.extend_sources(["https://example.com/b"])
        deps.extend_sources(["https://example.com/a"])

        assert deps.sources == ["https://example.com/a", "https://example.com/b"]


@pytest.mark.django_db
class TestAssistantChatHistory:
    """Test chat history loading and formatting."""

    def test_list_chat_messages_returns_in_chronological_order(
        self, enterprise_data_fixture
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="First question"
        )
        AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.AI, content="First answer"
        )
        msg3 = AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Second question"
        )

        assistant = Assistant(chat)
        messages = assistant.list_chat_messages()

        assert len(messages) == 3
        assert messages[0].content == "First question"
        assert messages[1].content == "First answer"
        assert messages[2].content == "Second question"

        messages = assistant.list_chat_messages(last_message_id=msg3.id, limit=1)
        assert len(messages) == 1
        assert messages[0].content == "First answer"

    def test_load_message_history_returns_none_for_empty(self, enterprise_data_fixture):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        assistant = Assistant(chat)
        history = async_to_sync(assistant._load_message_history)()
        assert history is None

    def test_load_message_history_deserializes_and_compacts(
        self, enterprise_data_fixture
    ):
        from pydantic_ai.messages import (
            ModelMessagesTypeAdapter,
            ModelRequest,
            ModelResponse,
            TextPart,
            ToolCallPart,
            ToolReturnPart,
            UserPromptPart,
        )

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        messages = [
            ModelRequest(parts=[UserPromptPart(content="create a database")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="create_tables",
                        args={"thought": "creating", "tables": ["recipes"]},
                        tool_call_id="tc1",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="create_tables",
                        content="Created",
                        tool_call_id="tc1",
                    )
                ]
            ),
            ModelResponse(parts=[TextPart(content="Done!")]),
        ]
        chat.message_history = ModelMessagesTypeAdapter.dump_json(messages)
        chat.save(update_fields=["message_history"])

        assistant = Assistant(chat)
        history = async_to_sync(assistant._load_message_history)()

        assert history is not None
        assert len(history) == 2
        assert isinstance(history[0], ModelRequest)
        assert isinstance(history[1], ModelResponse)

    def test_load_message_history_handles_corrupt_data(self, enterprise_data_fixture):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        chat.message_history = b"not valid json"
        chat.save(update_fields=["message_history"])

        assistant = Assistant(chat)
        history = async_to_sync(assistant._load_message_history)()
        assert history is None


class TestCompactMessageHistory:
    """Test the message history compaction logic."""

    def test_compacts_tool_calls_in_older_turns(self):
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            ToolCallPart,
            ToolReturnPart,
            UserPromptPart,
        )

        messages = [
            ModelRequest(parts=[UserPromptPart(content="create a database")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="create_tables",
                        args={"thought": "creating"},
                        tool_call_id="tc1",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="create_tables",
                        content="Created",
                        tool_call_id="tc1",
                    )
                ]
            ),
            ModelResponse(parts=[TextPart(content="Done!")]),
            ModelRequest(parts=[UserPromptPart(content="add a field")]),
            ModelResponse(parts=[TextPart(content="Added!")]),
        ]

        compacted = compact_message_history(messages)
        assert len(compacted) == 4

    def test_trims_to_max_messages(self):
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            UserPromptPart,
        )

        messages = []
        for i in range(20):
            messages.append(
                ModelRequest(parts=[UserPromptPart(content=f"Question {i}")])
            )
            messages.append(ModelResponse(parts=[TextPart(content=f"Answer {i}")]))

        compacted = compact_message_history(messages, max_messages=6)
        assert len(compacted) == 6

    def test_preserves_simple_conversations(self):
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            UserPromptPart,
        )

        messages = [
            ModelRequest(parts=[UserPromptPart(content="hello")]),
            ModelResponse(parts=[TextPart(content="hi")]),
        ]

        compacted = compact_message_history(messages)
        assert len(compacted) == 2


@pytest.mark.django_db
class TestAssistantLicenseTier:
    @patch("baserow_enterprise.assistant.assistant._get_workspace_license_type")
    def test_assistant_initializes_license_tier(
        self, mock__get_workspace_license_type, enterprise_data_fixture
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )
        license_type = MagicMock(type="premium", features=["premium"])
        mock__get_workspace_license_type.return_value = license_type

        assistant = Assistant(chat)

        mock__get_workspace_license_type.assert_called_once_with(user, workspace)
        assert assistant._deps.license_tier is license_type

    def test_dynamic_license_tier_injects_type_and_features(self):
        ctx = MagicMock()
        ctx.deps.license_tier = MagicMock(type="advanced", features=["sso", "rbac"])

        assert dynamic_license_tier(ctx) == (
            "\n<license_tier>advanced</license_tier>\n<features>rbac,sso</features>"
        )

    def test_dynamic_license_tier_normalizes_internal_enterprise_type(self):
        ctx = MagicMock()
        ctx.deps.license_tier = MagicMock(
            type="enterprise_without_support", features=["sso", "rbac"]
        )

        assert dynamic_license_tier(ctx) == (
            "\n<license_tier>enterprise</license_tier>\n<features>rbac,sso</features>"
        )

    def test_dynamic_license_tier_renders_free_for_unknown_type(self):
        ctx = MagicMock()
        ctx.deps.license_tier = MagicMock(type="unknown", features=["sso", "rbac"])

        assert dynamic_license_tier(ctx) == (
            "\n<license_tier>free</license_tier>\n<features>rbac,sso</features>"
        )

    def test_dynamic_license_tier_renders_free_when_no_license(self):
        ctx = MagicMock()
        ctx.deps.license_tier = None

        assert dynamic_license_tier(ctx) == "\n<license_tier>free</license_tier>"

    def test_agent_system_prompt_includes_grounding_guardrail(self):
        assert "Use `search_user_docs` first" in AGENT_SYSTEM_PROMPT
        assert "Never invent plan names" in AGENT_SYSTEM_PROMPT


@pytest.mark.django_db
class TestGetWorkspaceLicenseType:
    _PATCH_PATH = (
        "baserow_enterprise.assistant.assistant.ActiveLicensesDataType.get_user_data"
    )

    def _call(self, data, workspace_id=1):
        with patch(self._PATCH_PATH, return_value=data):
            return _get_workspace_license_type(MagicMock(), MagicMock(id=workspace_id))

    def test_returns_none_without_active_licenses(self):
        assert self._call({"instance_wide": {}, "per_workspace": {}}) is None

    def test_returns_instance_wide_license(self):
        result = self._call({"instance_wide": {"premium": True}, "per_workspace": {}})
        assert result is not None
        assert result.type == "premium"

    def test_returns_per_workspace_license(self):
        result = self._call(
            {"instance_wide": {}, "per_workspace": {42: {"advanced": True}}},
            workspace_id=42,
        )
        assert result is not None
        assert result.type == "advanced"

    def test_ignores_licenses_from_other_workspaces(self):
        assert (
            self._call(
                {"instance_wide": {}, "per_workspace": {99: {"advanced": True}}},
                workspace_id=42,
            )
            is None
        )

    def test_picks_highest_order_from_combined_set(self):
        result = self._call(
            {
                "instance_wide": {"premium": True},
                "per_workspace": {1: {"advanced": True}},
            }
        )
        assert result is not None
        # PremiumLicenseType.order=10, AdvancedLicenseType.order=75
        assert result.type == "advanced"

    def test_skips_license_names_not_in_registry(self):
        result = self._call(
            {
                "instance_wide": {"bogus_tier": True, "premium": True},
                "per_workspace": {},
            }
        )
        assert result is not None
        assert result.type == "premium"

    def test_returns_none_when_only_unknown_names(self):
        assert (
            self._call({"instance_wide": {"bogus_tier": True}, "per_workspace": {}})
            is None
        )


@pytest.mark.django_db
class TestAssistantMessagePersistence:
    """Test that messages are persisted correctly during streaming."""

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_persists_human_message(
        self,
        mock_run_stream_events,
        enterprise_data_fixture,
        scoped_assistant_model,
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        mock_run_stream_events.side_effect = make_mock_run_stream_events_side_effect(
            "Hello"
        )

        assistant = Assistant(chat)
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
        )

        async def consume_stream():
            human_message = HumanMessage(content="Test message", ui_context=ui_context)
            async for _ in assistant.astream_messages(human_message):
                pass

        async_to_sync(consume_stream)()

        human_messages = AssistantChatMessage.objects.filter(
            chat=chat, role=AssistantChatMessage.Role.HUMAN
        ).count()
        assert human_messages == 1

        saved_message = AssistantChatMessage.objects.filter(
            chat=chat, role=AssistantChatMessage.Role.HUMAN
        ).first()
        assert saved_message.content == "Test message"
        assert_model_scope_closed(scoped_assistant_model)

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_persists_ai_message(
        self,
        mock_run_stream_events,
        enterprise_data_fixture,
        scoped_assistant_model,
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        mock_run_stream_events.side_effect = make_mock_run_stream_events_side_effect(
            "Based on docs"
        )

        assistant = Assistant(chat)
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
        )

        async def consume_stream():
            human_message = HumanMessage(content="Question", ui_context=ui_context)
            async for _ in assistant.astream_messages(human_message):
                pass

        async_to_sync(consume_stream)()

        ai_messages = AssistantChatMessage.objects.filter(
            chat=chat, role=AssistantChatMessage.Role.AI
        ).count()
        assert ai_messages == 1
        assert_model_scope_closed(scoped_assistant_model)

    @patch("baserow_enterprise.assistant.agents.title_agent.run")
    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_persists_chat_title(
        self,
        mock_run_stream_events,
        mock_title_run,
        enterprise_data_fixture,
        scoped_assistant_model,
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(user=user, workspace=workspace, title="")

        mock_run_stream_events.side_effect = make_mock_run_stream_events_side_effect(
            "Hello"
        )

        mock_title_result = MagicMock()
        mock_title_result.output = "Greeting"
        mock_title_run.return_value = mock_title_result

        assistant = Assistant(chat)
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
        )

        async def consume_stream():
            human_message = HumanMessage(content="Hello", ui_context=ui_context)
            async for _ in assistant.astream_messages(human_message):
                pass

        async_to_sync(consume_stream)()

        chat.refresh_from_db()
        assert chat.title == "Greeting"
        assert_model_scope_closed(scoped_assistant_model)


@pytest.mark.django_db
class TestAssistantStreaming:
    """Test streaming behavior of the Assistant."""

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_yields_answer_chunks(
        self,
        mock_run_stream_events,
        enterprise_data_fixture,
        scoped_assistant_model,
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        mock_run_stream_events.side_effect = make_mock_run_stream_events_side_effect(
            "Hello world"
        )

        assistant = Assistant(chat)

        async def consume_stream():
            messages = []
            human_message = HumanMessage(content="Test")
            async for msg in assistant.astream_messages(human_message):
                messages.append(msg)
            return messages

        messages = async_to_sync(consume_stream)()

        # Filter for final AiMessage
        ai_messages = [m for m in messages if isinstance(m, AiMessage)]
        assert len(ai_messages) == 1
        assert ai_messages[0].content == "Hello world"
        assert ai_messages[0].id is not None

        # Should also have AiMessageChunk(s)
        chunks = [
            m
            for m in messages
            if isinstance(m, AiMessageChunk) and not isinstance(m, AiMessage)
        ]
        assert len(chunks) >= 1
        assert_model_scope_closed(scoped_assistant_model)

    @patch("baserow_enterprise.assistant.agents.title_agent.run")
    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_yields_title_for_new_chat(
        self,
        mock_run_stream_events,
        mock_title_run,
        enterprise_data_fixture,
        scoped_assistant_model,
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(user=user, workspace=workspace, title="")

        mock_run_stream_events.side_effect = make_mock_run_stream_events_side_effect(
            "Answer"
        )

        mock_title_result = MagicMock()
        mock_title_result.output = "Title"
        mock_title_run.return_value = mock_title_result

        assistant = Assistant(chat)

        async def consume_stream():
            msgs = []
            human_message = HumanMessage(content="Test")
            async for msg in assistant.astream_messages(human_message):
                msgs.append(msg)
            return msgs

        messages = async_to_sync(consume_stream)()

        title_messages = [m for m in messages if isinstance(m, ChatTitleMessage)]
        assert len(title_messages) == 1
        assert title_messages[0].content == "Title"
        assert_model_scope_closed(scoped_assistant_model)

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_yields_thinking_messages(
        self,
        mock_run_stream_events,
        enterprise_data_fixture,
        scoped_assistant_model,
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        assistant = Assistant(chat)

        async def mock_stream_with_thinking(*args, **kwargs):
            from pydantic_ai.run import AgentRunResultEvent

            # Emit thinking message via the event bus during streaming
            assistant._event_bus.emit(AiThinkingMessage(content="still thinking..."))

            # Yield text part then result
            yield PartStartEvent(index=0, part=PaiTextPart(content="Answer"))

            mock_result = MagicMock()
            mock_result.output = "Answer"
            mock_result.all_messages_json.return_value = b"[]"
            yield AgentRunResultEvent(result=mock_result)

        mock_run_stream_events.side_effect = (
            lambda *args, **kwargs: _mock_run_stream_events_cm(
                mock_stream_with_thinking(*args, **kwargs)
            )
        )

        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
        )

        async def consume_stream():
            thinking = []
            human_message = HumanMessage(content="Test", ui_context=ui_context)
            async for msg in assistant.astream_messages(human_message):
                if isinstance(msg, AiThinkingMessage):
                    thinking.append(msg)
            return thinking

        thinking_messages = async_to_sync(consume_stream)()

        assert len(thinking_messages) == 1
        assert thinking_messages[0].content == "still thinking..."
        assert_model_scope_closed(scoped_assistant_model)

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_yields_ai_started_message(
        self,
        mock_run_stream_events,
        enterprise_data_fixture,
        scoped_assistant_model,
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test"
        )

        mock_run_stream_events.side_effect = make_mock_run_stream_events_side_effect(
            "Hello"
        )

        assistant = Assistant(chat)
        human_message = HumanMessage(content="Hello")

        async def collect_messages():
            messages = []
            async for msg in assistant.astream_messages(human_message):
                messages.append(msg)
            return messages

        messages = async_to_sync(collect_messages)()

        assert len(messages) > 0
        assert isinstance(messages[0], AiStartedMessage)
        assert messages[0].message_id is not None
        assert_model_scope_closed(scoped_assistant_model)


@pytest.mark.django_db
def test_stream_agent_run_drives_the_real_pydantic_ai_stream(enterprise_data_fixture):
    """
    Exercises main_agent.run_stream_events for real, unmocked.

    The other streaming tests patch run_stream_events with an async generator,
    which cannot detect a change in how that call must be invoked. This one
    fails if the call shape is wrong.
    """

    from pydantic_ai.models.test import TestModel

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )
    assistant = Assistant(chat)
    queue = asyncio.Queue()

    async def run():
        return await assistant._stream_agent_run("say hello", None, queue)

    # call_tools=[]: TestModel's default 'all' would invoke every real tool with synthetic args.
    with patch.object(
        assistant, "_model", TestModel(custom_output_text="hello", call_tools=[])
    ):
        result = async_to_sync(run)()

    assert result is not None, "the real stream produced no AgentRunResultEvent"
    answer, run_result = result
    assert answer == "hello"
    assert run_result.all_messages_json()


@pytest.mark.django_db
def test_stream_agent_run_cancellation_propagates_through_async_with(
    enterprise_data_fixture,
):
    """
    Cancels the task driving ``_stream_agent_run`` mid-stream.

    ``_RunStreamEventsContext.__aexit__`` is only ever invoked by an ``async
    with`` block, so observing it fire on cancellation proves the
    cancellation unwound through that block.
    """

    from types import TracebackType

    from pydantic_ai.agent.abstract import _RunStreamEventsContext
    from pydantic_ai.messages import ModelMessage
    from pydantic_ai.models.function import AgentInfo, FunctionModel

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )
    assistant = Assistant(chat)
    queue = asyncio.Queue()

    reached_block = asyncio.Event()

    async def stream_function(messages: list[ModelMessage], agent_info: AgentInfo):
        yield "partial answer"
        reached_block.set()
        await asyncio.Event().wait()  # never set: only cancellation ends this

    aexit_exc_types: list[type[BaseException] | None] = []
    real_aexit = _RunStreamEventsContext.__aexit__

    async def spy_aexit(
        self: _RunStreamEventsContext,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        aexit_exc_types.append(exc_type)
        return await real_aexit(self, exc_type, exc, tb)

    async def run_and_cancel() -> None:
        with (
            patch.object(
                assistant, "_model", FunctionModel(stream_function=stream_function)
            ),
            patch.object(_RunStreamEventsContext, "__aexit__", spy_aexit),
        ):
            task = asyncio.ensure_future(
                assistant._stream_agent_run("say hello", None, queue)
            )
            await reached_block.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    async_to_sync(run_and_cancel)()

    assert asyncio.CancelledError in aexit_exc_types, (
        "_RunStreamEventsContext.__aexit__ never ran with CancelledError — "
        "cancellation did not unwind through the async with block"
    )


@pytest.mark.django_db
class TestUIContext:
    """Test UI context handling and validation."""

    def test_ui_context_from_validate_request_adds_user_info(
        self, enterprise_data_fixture
    ):
        user = enterprise_data_fixture.create_user(
            email="test@example.com", first_name="Test User"
        )
        workspace = enterprise_data_fixture.create_workspace(user=user)

        class MockRequest:
            pass

        request = MockRequest()
        request.user = user

        ui_context_data = {"workspace": {"id": workspace.id, "name": workspace.name}}
        ui_context = UIContext.from_validate_request(request, ui_context_data)

        assert ui_context.workspace.id == workspace.id
        assert ui_context.workspace.name == workspace.name
        assert ui_context.user.id == user.id
        assert ui_context.user.email == "test@example.com"
        assert ui_context.user.name == "Test User"

    def test_ui_context_with_database_builder_fields(self):
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test Workspace"),
            database=ApplicationUIContext(id="db-123", name="My Database"),
            table=TableUIContext(id=456, name="Customers"),
            view=ViewUIContext(id=789, name="All Customers", type="grid"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
        )

        assert ui_context.workspace.id == 1
        assert ui_context.database.id == "db-123"
        assert ui_context.table.id == 456
        assert ui_context.view.id == 789

    def test_ui_context_serialization_excludes_none_values(self):
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test Workspace"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
        )

        serialized = ui_context.model_dump(exclude_none=True)
        assert "workspace" in serialized
        assert "user" in serialized
        assert "database" not in serialized
        assert "table" not in serialized

    def test_ui_context_has_default_timestamp(self):
        from datetime import datetime

        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
        )

        assert ui_context.timestamp is not None
        assert isinstance(ui_context.timestamp, datetime)

    def test_ui_context_has_default_timezone(self):
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
        )

        assert ui_context.timezone == "UTC"

    def test_user_ui_context_from_user(self, enterprise_data_fixture):
        user = enterprise_data_fixture.create_user(
            email="john@example.com", first_name="John Doe"
        )

        user_context = UserUIContext.from_user(user)

        assert user_context.id == user.id
        assert user_context.name == "John Doe"
        assert user_context.email == "john@example.com"

    def test_human_message_with_ui_context(self):
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test Workspace"),
            database=ApplicationUIContext(id="db-123", name="My Database"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
        )

        human_message = HumanMessage(
            content="How do I create a field?", ui_context=ui_context
        )

        assert human_message.content == "How do I create a field?"
        assert human_message.ui_context.workspace.id == 1
        assert human_message.ui_context.database.id == "db-123"


@pytest.mark.django_db
class TestAssistantCancellation:
    """Test cancellation functionality in Assistant."""

    def test_get_cancellation_cache_key(self, enterprise_data_fixture):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test"
        )

        from baserow_enterprise.assistant.assistant import (
            get_assistant_cancellation_key,
        )

        cache_key = get_assistant_cancellation_key(str(chat.uuid))
        assert cache_key == f"assistant:chat:{chat.uuid}:cancelled"


@pytest.mark.django_db
class TestGetModelString:
    """Test the model string conversion logic."""

    @override_settings(BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL="groq/llama-3.3-70b")
    def test_replaces_slash_with_colon(self):
        assert get_model_string() == "groq:llama-3.3-70b"

    @override_settings(BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL="openai/gpt-4")
    def test_openai_model(self):
        assert get_model_string() == "openai:gpt-4"

    @override_settings(BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL="gpt-4o")
    def test_bare_model_defaults_to_openai(self):
        assert get_model_string() == "openai:gpt-4o"

    def test_unconfigured_database_feature_keeps_legacy_fallback(
        self, data_fixture, settings
    ):
        settings.FEATURE_FLAGS = ["ai-providers"]
        settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = "groq:legacy-model"
        workspace = data_fixture.create_workspace()

        assert get_model_string(workspace=workspace) == "groq:legacy-model"

    def test_process_local_readiness_is_cached_per_process_not_globally(self):
        _clear_process_local_model_readiness_cache()
        try:
            with (
                patch(
                    "baserow_enterprise.assistant.model_profiles."
                    "ResolvedAssistantModelProfile.create_model"
                ) as create_model,
                patch(
                    "baserow_enterprise.assistant.model_profiles."
                    "test_model_text_and_tool_calling"
                ) as test_model,
                patch(
                    "baserow_enterprise.assistant.model_profiles.global_cache.get"
                ) as global_cache_get,
            ):
                check_lm_ready_or_raise()
                check_lm_ready_or_raise()

            create_model.assert_called_once_with()
            assert test_model.call_count == 1
            global_cache_get.assert_not_called()
        finally:
            _clear_process_local_model_readiness_cache()

    def test_process_local_readiness_failures_are_briefly_throttled(self):
        _clear_process_local_model_readiness_cache()
        try:
            with (
                patch(
                    "baserow_enterprise.assistant.model_profiles."
                    "ResolvedAssistantModelProfile.create_model"
                ) as create_model,
                patch(
                    "baserow_enterprise.assistant.model_profiles."
                    "test_model_text_and_tool_calling",
                    side_effect=RuntimeError("provider unavailable"),
                ) as test_model,
            ):
                for _ in range(2):
                    with pytest.raises(
                        AssistantModelNotSupportedError,
                        match="not supported or accessible",
                    ):
                        check_lm_ready_or_raise()

            create_model.assert_called_once_with()
            test_model.assert_called_once()
        finally:
            _clear_process_local_model_readiness_cache()

    def test_explicit_model_overrides_setting(self):
        assert get_model_string("groq/custom-model") == "groq:custom-model"

    def test_google_gla_prefix_is_normalised(self):
        """Sub-agents pass this string straight to pydantic-ai's infer_model,
        which only accepts its own provider names."""

        assert get_model_string("google-gla:gemini-2.0-flash") == (
            "google:gemini-2.0-flash"
        )

    def test_google_vertex_prefix_is_normalised(self):
        assert get_model_string("google-vertex:gemini-2.0-flash") == (
            "google-cloud:gemini-2.0-flash"
        )

    def test_uses_instance_model_and_workspace_override(self, data_fixture, settings):
        settings.FEATURE_FLAGS = ["ai-providers"]
        workspace = data_fixture.create_workspace()
        instance_provider = AIProviderConfig.objects.create(
            provider_type="openai", api_key="instance-key"
        )
        instance_model = AIProviderModel.objects.create(
            provider_config=instance_provider,
            model_identifier="instance-model",
            feature_types=[AI_PROVIDER_FEATURE_KUMA],
        )
        workspace_provider = AIProviderConfig.objects.create(
            workspace=workspace,
            provider_type="anthropic",
            api_key="workspace-key",
        )
        workspace_model = AIProviderModel.objects.create(
            provider_config=workspace_provider,
            model_identifier="workspace-model",
            feature_types=[AI_PROVIDER_FEATURE_KUMA],
        )
        AIProviderHandler.update_feature_setting(
            AI_PROVIDER_FEATURE_KUMA,
            AI_PROVIDER_FEATURE_MODE_MODEL,
            model=instance_model,
        )

        assert get_model_string(workspace=workspace) == "openai:instance-model"

        AIProviderHandler.update_feature_setting(
            AI_PROVIDER_FEATURE_KUMA,
            AI_PROVIDER_FEATURE_MODE_MODEL,
            workspace=workspace,
            model=workspace_model,
        )
        assert get_model_string(workspace=workspace) == "anthropic:workspace-model"

    @pytest.mark.parametrize(
        ("provider_type", "model_identifier"),
        [
            ("google", "gemini-2.5-flash"),
            ("groq", "openai/gpt-oss-120b"),
        ],
    )
    def test_database_selected_google_and_groq_models_use_database_credentials(
        self,
        data_fixture,
        settings,
        monkeypatch,
        provider_type,
        model_identifier,
    ):
        settings.FEATURE_FLAGS = ["ai-providers"]
        monkeypatch.setenv("GOOGLE_API_KEY", "legacy-kuma-key")
        monkeypatch.setenv("GROQ_API_KEY", "legacy-kuma-key")
        workspace = data_fixture.create_workspace()
        provider = AIProviderConfig.objects.create(
            provider_type=provider_type, api_key="database-key"
        )
        model = AIProviderModel.objects.create(
            provider_config=provider,
            model_identifier=model_identifier,
            feature_types=[AI_PROVIDER_FEATURE_KUMA],
        )
        AIProviderHandler.update_feature_setting(
            AI_PROVIDER_FEATURE_KUMA,
            AI_PROVIDER_FEATURE_MODE_MODEL,
            model=model,
        )

        assistant_model = get_assistant_model(workspace=workspace).wrapped

        assert get_model_string(workspace=workspace) == (
            f"{provider_type}:{model_identifier}"
        )
        assert assistant_model.system == provider_type
        if provider_type == "google":
            assert (
                assistant_model._provider.client._api_client.api_key == "database-key"
            )
        else:
            assert assistant_model._provider.client.api_key == "database-key"

    def test_workspace_can_disable_kuma(self, data_fixture, settings):
        settings.FEATURE_FLAGS = ["ai-providers"]
        workspace = data_fixture.create_workspace()
        AIProviderHandler.update_feature_setting(
            AI_PROVIDER_FEATURE_KUMA,
            AI_PROVIDER_FEATURE_MODE_DISABLED,
            workspace=workspace,
        )

        with pytest.raises(AssistantModelDisabledError, match="disabled"):
            get_model_string(workspace=workspace)

    def test_database_model_readiness_failure_has_database_specific_error(
        self, data_fixture, settings
    ):
        settings.FEATURE_FLAGS = ["ai-providers"]
        workspace = data_fixture.create_workspace()
        provider = AIProviderConfig.objects.create(
            provider_type="openai", api_key="database-key"
        )
        model = AIProviderModel.objects.create(
            provider_config=provider,
            model_identifier="instance-model",
            feature_types=[AI_PROVIDER_FEATURE_KUMA],
        )
        AIProviderHandler.update_feature_setting(
            AI_PROVIDER_FEATURE_KUMA,
            AI_PROVIDER_FEATURE_MODE_MODEL,
            model=model,
        )

        with patch(
            "baserow.core.generative_ai.capabilities.Agent.run",
            side_effect=RuntimeError("provider rejected the request"),
        ) as run:
            for _ in range(2):
                with pytest.raises(
                    AssistantConfiguredModelNotAvailableError,
                    match="openai:instance-model",
                ):
                    check_lm_ready_or_raise(workspace)

        run.assert_called_once()

    def test_database_model_readiness_is_cached_per_configuration(
        self, data_fixture, settings
    ):
        settings.FEATURE_FLAGS = ["ai-providers"]
        workspace = data_fixture.create_workspace()
        provider = AIProviderConfig.objects.create(
            provider_type="openai", api_key="database-key"
        )
        identifier = f"model-{uuid4().hex}"
        model = AIProviderModel.objects.create(
            provider_config=provider,
            model_identifier=identifier,
            feature_types=[AI_PROVIDER_FEATURE_KUMA],
        )
        AIProviderHandler.update_feature_setting(
            AI_PROVIDER_FEATURE_KUMA,
            AI_PROVIDER_FEATURE_MODE_MODEL,
            model=model,
        )

        with (
            patch(
                "baserow_enterprise.assistant.model_profiles."
                "ResolvedAssistantModelProfile.create_model"
            ) as create_model,
            patch(
                "baserow_enterprise.assistant.model_profiles."
                "test_model_text_and_tool_calling"
            ) as test_model,
        ):
            check_lm_ready_or_raise(workspace)
            check_lm_ready_or_raise(workspace)

            model = AIProviderHandler.update_model(
                model, model_identifier=f"{identifier}-updated"
            )
            check_lm_ready_or_raise(workspace)

        assert create_model.call_count == 2
        assert test_model.call_count == 2
