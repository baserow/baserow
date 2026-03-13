from unittest.mock import MagicMock, patch

from django.test.utils import override_settings

import pytest
from asgiref.sync import async_to_sync
from pydantic_ai.messages import PartStartEvent
from pydantic_ai.messages import TextPart as PaiTextPart

from baserow_enterprise.assistant.assistant import (
    Assistant,
    compact_message_history,
    get_model_string,
)
from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.models import AssistantChat, AssistantChatMessage
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

TEST_MODEL = "groq:test-model"


@pytest.fixture(autouse=True)
def mock_posthog():
    with patch("baserow_enterprise.assistant.telemetry.get_posthog_client") as mock:
        mock.return_value = MagicMock()
        yield mock


@pytest.fixture(autouse=True)
def _set_test_model(settings):
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = "groq/test-model"


# ---------------------------------------------------------------------------
# Mock helpers for pydantic-ai's run_stream_events async generator
# ---------------------------------------------------------------------------


async def _mock_run_stream_events(answer: str, messages_json: bytes = b"[]"):
    """
    Async generator that mimics ``main_agent.run_stream_events()``
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


def make_mock_run_stream_events_side_effect(answer: str, messages_json: bytes = b"[]"):
    """Return a side_effect callable that returns the mock async generator."""

    def side_effect(*args, **kwargs):
        return _mock_run_stream_events(answer, messages_json)

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
class TestAssistantMessagePersistence:
    """Test that messages are persisted correctly during streaming."""

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_persists_human_message(
        self, mock_run_stream_events, enterprise_data_fixture
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

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_persists_ai_message(
        self, mock_run_stream_events, enterprise_data_fixture
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

    @patch("baserow_enterprise.assistant.agents.title_agent.run")
    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_persists_chat_title(
        self,
        mock_run_stream_events,
        mock_title_run,
        enterprise_data_fixture,
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


@pytest.mark.django_db
class TestAssistantStreaming:
    """Test streaming behavior of the Assistant."""

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_yields_answer_chunks(
        self, mock_run_stream_events, enterprise_data_fixture
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

    @patch("baserow_enterprise.assistant.agents.title_agent.run")
    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_yields_title_for_new_chat(
        self, mock_run_stream_events, mock_title_run, enterprise_data_fixture
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

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_yields_thinking_messages(
        self, mock_run_stream_events, enterprise_data_fixture
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

        mock_run_stream_events.side_effect = mock_stream_with_thinking

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

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_yields_ai_started_message(
        self, mock_run_stream_events, enterprise_data_fixture
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

    def test_explicit_model_overrides_setting(self):
        assert get_model_string("groq/custom-model") == "groq:custom-model"
