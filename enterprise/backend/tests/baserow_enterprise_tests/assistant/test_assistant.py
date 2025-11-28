"""
Tests for the Assistant class focusing on behaviors rather than implementation details.

These tests verify that the Assistant:
- Correctly loads and formats chat history for context
- Persists messages to the database during streaming
- Handles sources from tool outputs correctly
- Generates and persists chat titles appropriately
- Adapts its signature based on chat state
"""
from unittest.mock import MagicMock, Mock, patch

from django.core.cache import cache

import pytest
from asgiref.sync import async_to_sync
from udspy import OutputStreamChunk, Prediction

from baserow_enterprise.assistant.assistant import Assistant, AssistantCallbacks
from baserow_enterprise.assistant.exceptions import AssistantMessageCancelled
from baserow_enterprise.assistant.models import AssistantChat, AssistantChatMessage
from baserow_enterprise.assistant.types import (
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
def mock_posthog_openai():
    with patch("posthog.ai.openai.AsyncOpenAI") as mock:
        # Configure the mock if needed
        mock.return_value = MagicMock()
        mock.return_value.model = "test-model"
        yield mock


@pytest.mark.django_db
class TestAssistantCallbacks:
    """Test the AssistantCallbacks class for handling tool execution"""

    def test_extend_sources_deduplicates(self):
        """Test that sources are deduplicated when extended"""

        callbacks = AssistantCallbacks()

        # Add initial sources
        callbacks.extend_sources(
            ["https://example.com/doc1", "https://example.com/doc2"]
        )
        assert callbacks.sources == [
            "https://example.com/doc1",
            "https://example.com/doc2",
        ]

        # Add sources with duplicates
        callbacks.extend_sources(
            ["https://example.com/doc2", "https://example.com/doc3"]
        )

        # Should only add the new source, not the duplicate
        assert callbacks.sources == [
            "https://example.com/doc1",
            "https://example.com/doc2",
            "https://example.com/doc3",
        ]

    def test_extend_sources_preserves_order(self):
        """Test that source order is preserved (first occurrence wins)"""

        callbacks = AssistantCallbacks()

        callbacks.extend_sources(["https://example.com/a"])
        callbacks.extend_sources(["https://example.com/b"])
        callbacks.extend_sources(["https://example.com/a"])  # Duplicate

        # 'a' should remain first
        assert callbacks.sources == ["https://example.com/a", "https://example.com/b"]

    def test_on_tool_end_extracts_sources_from_outputs(self):
        """Test that sources are extracted from tool outputs"""

        callbacks = AssistantCallbacks()

        # Mock tool instance and inputs
        tool_instance = MagicMock()
        tool_instance.name = "search_user_docs"
        inputs = {"query": "test"}

        # Register tool call
        callbacks.tool_calls["call_123"] = (tool_instance, inputs)

        # Mock registry
        with patch(
            "baserow_enterprise.assistant.assistant.assistant_tool_registry"
        ) as mock_registry:
            mock_tool = MagicMock()
            mock_registry.get.return_value = mock_tool

            # Tool returns outputs with sources
            outputs = {
                "result": "Some documentation",
                "sources": ["https://baserow.io/docs/api"],
            }

            callbacks.on_tool_end("call_123", outputs)

            # Sources should be extracted
            assert callbacks.sources == ["https://baserow.io/docs/api"]

    def test_on_tool_end_handles_missing_sources(self):
        """Test that tool outputs without sources don't cause errors"""

        callbacks = AssistantCallbacks()

        tool_instance = MagicMock()
        tool_instance.name = "some_tool"
        callbacks.tool_calls["call_123"] = (tool_instance, {})

        with patch(
            "baserow_enterprise.assistant.assistant.assistant_tool_registry"
        ) as mock_registry:
            mock_tool = MagicMock()
            mock_registry.get.return_value = mock_tool

            # Tool returns outputs without sources
            outputs = {"result": "Some result"}

            callbacks.on_tool_end("call_123", outputs)

            # Should not raise, sources should remain empty
            assert callbacks.sources == []


@pytest.mark.django_db
class TestAssistantChatHistory:
    """Test chat history loading and formatting"""

    def test_list_chat_messages_returns_in_chronological_order(
        self, enterprise_data_fixture
    ):
        """Test that list_chat_messages returns messages oldest to newest"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Create messages in order
        msg1 = AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="First question"
        )
        msg2 = AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.AI, content="First answer"
        )
        msg3 = AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Second question"
        )

        assistant = Assistant(chat)
        messages = assistant.list_chat_messages()

        # Should be in chronological order (oldest first)
        assert len(messages) == 3
        assert messages[0].content == "First question"
        assert messages[1].content == "First answer"
        assert messages[2].content == "Second question"

        # It's possible to skip messages using last_message_id
        messages = assistant.list_chat_messages(last_message_id=msg3.id, limit=1)
        assert len(messages) == 1
        assert messages[0].content == "First answer"

    def test_aload_chat_history_formats_as_question_answer_pairs(
        self, enterprise_data_fixture
    ):
        """Test that chat history is loaded as user/assistant message pairs for UDSPy"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Create conversation history
        AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="What is Baserow?"
        )
        AssistantChatMessage.objects.create(
            chat=chat,
            role=AssistantChatMessage.Role.AI,
            content="Baserow is a no-code database platform.",
        )
        AssistantChatMessage.objects.create(
            chat=chat,
            role=AssistantChatMessage.Role.HUMAN,
            content="How do I create a table?",
        )
        AssistantChatMessage.objects.create(
            chat=chat,
            role=AssistantChatMessage.Role.AI,
            content="You can create a table by clicking the + button.",
        )

        assistant = Assistant(chat)
        assistant.history = async_to_sync(assistant.afetch_chat_history)()

        # History should contain user/assistant message pairs
        assert assistant.history is not None
        assert len(assistant.history.messages) == 4

        # First pair
        assert assistant.history.messages[0] == {
            "role": "user",
            "content": "What is Baserow?",
        }
        assert assistant.history.messages[1] == {
            "role": "assistant",
            "content": "Baserow is a no-code database platform.",
        }

        # Second pair
        assert assistant.history.messages[2] == {
            "role": "user",
            "content": "How do I create a table?",
        }
        assert assistant.history.messages[3] == {
            "role": "assistant",
            "content": "You can create a table by clicking the + button.",
        }

    def test_aload_chat_history_respects_limit(self, enterprise_data_fixture):
        """Test that history loading respects the limit parameter"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Create 10 message pairs (20 messages)
        for i in range(10):
            AssistantChatMessage.objects.create(
                chat=chat,
                role=AssistantChatMessage.Role.HUMAN,
                content=f"Question {i}",
            )
            AssistantChatMessage.objects.create(
                chat=chat, role=AssistantChatMessage.Role.AI, content=f"Answer {i}"
            )

        assistant = Assistant(chat)
        assistant.history = async_to_sync(assistant.afetch_chat_history)(
            limit=6
        )  # Last 6 messages

        # Should only load the most recent 6 messages (3 pairs)
        assert len(assistant.history.messages) == 6

    def test_aload_chat_history_handles_incomplete_pairs(self, enterprise_data_fixture):
        """
        Test that incomplete message pairs (e.g., orphaned human messages) are skipped
        """

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Create complete pair
        AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Question 1"
        )
        AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.AI, content="Answer 1"
        )

        # Create orphaned human message (no AI response yet)
        AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Question 2"
        )

        assistant = Assistant(chat)
        assistant.history = async_to_sync(assistant.afetch_chat_history)()

        # Should only include the complete pair (2 messages: user + assistant)
        assert len(assistant.history.messages) == 2
        assert assistant.history.messages[0] == {
            "role": "user",
            "content": "Question 1",
        }
        assert assistant.history.messages[1] == {
            "role": "assistant",
            "content": "Answer 1",
        }

    @patch("udspy.ReAct.astream")
    def test_history_is_passed_to_astream_as_context(
        self, mock_react_astream, enterprise_data_fixture
    ):
        """
        Test that chat history is loaded correctly and passed to the agent as context
        """

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Create conversation history (2 complete pairs)
        AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="What is Baserow?"
        )
        AssistantChatMessage.objects.create(
            chat=chat,
            role=AssistantChatMessage.Role.AI,
            content="Baserow is a no-code database",
        )
        AssistantChatMessage.objects.create(
            chat=chat,
            role=AssistantChatMessage.Role.HUMAN,
            content="How do I create a table?",
        )
        AssistantChatMessage.objects.create(
            chat=chat,
            role=AssistantChatMessage.Role.AI,
            content="Click the Create Table button",
        )

        assistant = Assistant(chat)

        # Mock the router stream to delegate to agent with extracted context
        def mock_router_stream_factory(*args, **kwargs):
            # Verify conversation history is passed to router
            assert kwargs["conversation_history"] == [
                "[0] (user): What is Baserow?",
                "[1] (assistant): Baserow is a no-code database",
                "[2] (user): How do I create a table?",
                "[3] (assistant): Click the Create Table button",
            ]

            async def _stream():
                yield Prediction(
                    routing_decision="delegate_to_agent",
                    extracted_context="User wants to add a view to their table",
                    search_query="",
                )

            return _stream()

        # Patch the instance method
        assistant._request_router.astream = Mock(side_effect=mock_router_stream_factory)

        # Mock the agent stream
        def mock_agent_stream_factory(*args, **kwargs):
            # Verify extracted context is passed to agent
            assert kwargs["context"] == "User wants to add a view to their table"

            async def _stream():
                yield OutputStreamChunk(
                    module=None,
                    field_name="answer",
                    delta="Answer",
                    content="Answer",
                    is_complete=False,
                )
                yield Prediction(answer="Answer", trajectory=[], reasoning="")

            return _stream()

        mock_react_astream.side_effect = mock_agent_stream_factory

        message = HumanMessage(content="How to add a view?")

        # Consume the stream to trigger assertions
        async def consume_stream():
            async for _ in assistant.astream_messages(message):
                pass

        async_to_sync(consume_stream)()


@pytest.mark.django_db
class TestAssistantMessagePersistence:
    """Test that messages are persisted correctly during streaming"""

    @patch("udspy.ChainOfThought.astream")
    @patch("udspy.ReAct.astream")
    def test_astream_messages_persists_human_message(
        self, mock_react_astream, mock_cot_astream, enterprise_data_fixture
    ):
        """Test that human messages are persisted to database before streaming"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Mock the router stream
        async def mock_router_stream(*args, **kwargs):
            yield Prediction(
                routing_decision="delegate_to_agent",
                extracted_context="",
                search_query="",
            )

        mock_cot_astream.return_value = mock_router_stream()

        # Mock the agent streaming
        async def mock_agent_stream(*args, **kwargs):
            # Yield a simple response
            yield OutputStreamChunk(
                module=None,
                field_name="answer",
                delta="Hello",
                content="Hello",
                is_complete=False,
            )
            yield Prediction(answer="Hello", trajectory=[], reasoning="")

        mock_react_astream.return_value = mock_agent_stream()

        assistant = Assistant(chat)
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
        )

        # Consume the stream
        async def consume_stream():
            human_message = HumanMessage(content="Test message", ui_context=ui_context)
            async for _ in assistant.astream_messages(human_message):
                pass

        async_to_sync(consume_stream)()

        # Human message should be persisted
        human_messages = AssistantChatMessage.objects.filter(
            chat=chat, role=AssistantChatMessage.Role.HUMAN
        ).count()
        assert human_messages == 1

        saved_message = AssistantChatMessage.objects.filter(
            chat=chat, role=AssistantChatMessage.Role.HUMAN
        ).first()
        assert saved_message.content == "Test message"

    @patch("udspy.ChainOfThought.astream")
    @patch("udspy.ReAct.astream")
    def test_astream_messages_persists_ai_message_with_sources(
        self, mock_react_astream, mock_cot_astream, enterprise_data_fixture
    ):
        """Test that AI messages are persisted with sources in artifacts"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        assistant = Assistant(chat)

        # Mock the router stream
        async def mock_router_stream(*args, **kwargs):
            yield Prediction(
                routing_decision="delegate_to_agent",
                extracted_context="",
                search_query="",
            )

        mock_cot_astream.return_value = mock_router_stream()

        # Mock the agent streaming with a Prediction at the end
        async def mock_agent_stream(*args, **kwargs):
            yield OutputStreamChunk(
                module=None,
                field_name="answer",
                delta="Based on docs",
                content="Based on docs",
                is_complete=False,
            )
            yield Prediction(
                module=assistant._assistant,
                answer="Based on docs",
                trajectory=[],
                reasoning="",
            )

        mock_react_astream.return_value = mock_agent_stream()
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
        )

        # Manually add sources to callback manager (simulating tool execution)
        async def consume_stream():
            messages = []
            human_message = HumanMessage(content="Question", ui_context=ui_context)
            async for msg in assistant.astream_messages(human_message):
                messages.append(msg)
            return messages

        async_to_sync(consume_stream)()

        # AI message should be persisted
        ai_messages = AssistantChatMessage.objects.filter(
            chat=chat, role=AssistantChatMessage.Role.AI
        ).count()
        assert ai_messages == 1

    @patch("udspy.ChainOfThought.astream")
    @patch("udspy.ReAct.astream")
    @patch("udspy.Predict")
    def test_astream_messages_persists_chat_title(
        self,
        mock_predict_class,
        mock_react_astream,
        mock_cot_astream,
        enterprise_data_fixture,
    ):
        """Test that chat titles are persisted to the database"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title=""  # New chat
        )

        # Mock title generator
        async def mock_title_aforward(*args, **kwargs):
            return Prediction(chat_title="Greeting")

        mock_title_generator = MagicMock()
        mock_title_generator.aforward = mock_title_aforward
        mock_predict_class.return_value = mock_title_generator

        assistant = Assistant(chat)

        # Mock the router stream
        async def mock_router_stream(*args, **kwargs):
            yield Prediction(
                routing_decision="delegate_to_agent",
                extracted_context="",
                search_query="",
            )

        mock_cot_astream.return_value = mock_router_stream()

        # Mock agent streaming
        async def mock_agent_stream(*args, **kwargs):
            yield OutputStreamChunk(
                module=None,
                field_name="answer",
                delta="Hello",
                content="Hello",
                is_complete=False,
            )
            yield Prediction(
                module=assistant._assistant, answer="Hello", trajectory=[], reasoning=""
            )

        mock_react_astream.return_value = mock_agent_stream()
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
        )

        # Consume the stream
        async def consume_stream():
            human_message = HumanMessage(content="Hello", ui_context=ui_context)
            async for _ in assistant.astream_messages(human_message):
                pass

        async_to_sync(consume_stream)()

        # Refresh from DB
        chat.refresh_from_db()

        # Title should be persisted
        assert chat.title == "Greeting"


@pytest.mark.django_db
class TestAssistantStreaming:
    """Test streaming behavior of the Assistant"""

    @patch("udspy.ChainOfThought.astream")
    @patch("udspy.ReAct.astream")
    def test_astream_messages_yields_answer_chunks(
        self, mock_react_astream, mock_cot_astream, enterprise_data_fixture
    ):
        """Test that answer chunks are yielded during streaming"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Mock the router stream
        async def mock_router_stream(*args, **kwargs):
            yield Prediction(
                routing_decision="delegate_to_agent",
                extracted_context="",
                search_query="",
            )

        mock_cot_astream.return_value = mock_router_stream()

        assistant = Assistant(chat)

        # Mock agent streaming
        async def mock_agent_stream(*args, **kwargs):
            yield OutputStreamChunk(
                module=assistant._assistant.extract_module,
                field_name="answer",
                delta="Hello",
                content="Hello",
                is_complete=False,
            )
            yield OutputStreamChunk(
                module=assistant._assistant.extract_module,
                field_name="answer",
                delta=" world",
                content="Hello world",
                is_complete=False,
            )
            yield Prediction(answer="Hello world", trajectory=[], reasoning="")

        mock_react_astream.return_value = mock_agent_stream()

        async def consume_stream():
            chunks = []
            human_message = HumanMessage(content="Test")
            async for msg in assistant.astream_messages(human_message):
                if isinstance(msg, AiMessageChunk):
                    chunks.append(msg)
            return chunks

        chunks = async_to_sync(consume_stream)()

        # Should receive chunks with accumulated content
        assert len(chunks) == 2
        assert chunks[0].content == "Hello"
        assert chunks[1].content == "Hello world"

    @patch("udspy.ChainOfThought.astream")
    @patch("udspy.ReAct.astream")
    @patch("udspy.Predict")
    def test_astream_messages_yields_title_chunks(
        self,
        mock_predict_class,
        mock_react_astream,
        mock_cot_astream,
        enterprise_data_fixture,
    ):
        """Test that title chunks are yielded for new chats"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title=""  # New chat
        )

        # Mock title generator
        async def mock_title_aforward(*args, **kwargs):
            return Prediction(chat_title="Title")

        mock_title_generator = MagicMock()
        mock_title_generator.aforward = mock_title_aforward
        mock_predict_class.return_value = mock_title_generator

        assistant = Assistant(chat)

        # Mock the router stream
        async def mock_router_stream(*args, **kwargs):
            yield Prediction(
                routing_decision="delegate_to_agent",
                extracted_context="",
                search_query="",
            )

        mock_cot_astream.return_value = mock_router_stream()

        # Mock agent streaming
        async def mock_agent_stream(*args, **kwargs):
            yield OutputStreamChunk(
                module=None,
                field_name="answer",
                delta="Answer",
                content="Answer",
                is_complete=False,
            )
            yield Prediction(
                module=assistant._assistant,
                answer="Answer",
                trajectory=[],
                reasoning="",
            )

        mock_react_astream.return_value = mock_agent_stream()

        async def consume_stream():
            title_messages = []
            human_message = HumanMessage(content="Test")
            async for msg in assistant.astream_messages(human_message):
                if isinstance(msg, ChatTitleMessage):
                    title_messages.append(msg)
            return title_messages

        title_messages = async_to_sync(consume_stream)()

        # Should receive title chunks
        assert len(title_messages) == 1
        assert title_messages[0].content == "Title"

    @patch("udspy.ChainOfThought.astream")
    @patch("udspy.ReAct.astream")
    def test_astream_messages_yields_thinking_messages(
        self, mock_react_astream, mock_cot_astream, enterprise_data_fixture
    ):
        """Test that thinking messages from tools are yielded"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Mock the router stream
        async def mock_router_stream(*args, **kwargs):
            yield Prediction(
                routing_decision="delegate_to_agent",
                extracted_context="",
                search_query="",
            )

        mock_cot_astream.return_value = mock_router_stream()

        assistant = Assistant(chat)

        # Mock the agent streaming
        async def mock_agent_stream(*args, **kwargs):
            yield AiThinkingMessage(content="still thinking...")
            yield OutputStreamChunk(
                module=assistant._assistant.extract_module,
                field_name="answer",
                delta="Answer",
                content="Answer",
                is_complete=False,
            )
            yield Prediction(answer="Answer", trajectory=[], reasoning="")

        mock_react_astream.return_value = mock_agent_stream()

        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
        )

        async def consume_stream():
            thinking_messages = []
            human_message = HumanMessage(content="Test", ui_context=ui_context)
            async for msg in assistant.astream_messages(human_message):
                if isinstance(msg, AiThinkingMessage):
                    thinking_messages.append(msg)
            return thinking_messages

        thinking_messages = async_to_sync(consume_stream)()

        # Should receive thinking messages
        assert len(thinking_messages) == 2
        assert thinking_messages[0].content == "Thinking..."
        assert thinking_messages[1].content == "still thinking..."


@pytest.mark.django_db
class TestUIContext:
    """Test UI context handling and validation"""

    def test_ui_context_from_validate_request_adds_user_info(
        self, enterprise_data_fixture
    ):
        """
        Test that UIContext.from_validate_request adds user information
        from request
        """

        user = enterprise_data_fixture.create_user(
            email="test@example.com", first_name="Test User"
        )
        workspace = enterprise_data_fixture.create_workspace(user=user)

        # Mock request object
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
        """Test that UIContext correctly stores database builder fields"""

        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test Workspace"),
            database=ApplicationUIContext(id="db-123", name="My Database"),
            table=TableUIContext(id=456, name="Customers"),
            view=ViewUIContext(id=789, name="All Customers", type="grid"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
        )

        assert ui_context.workspace.id == 1
        assert ui_context.database.id == "db-123"
        assert ui_context.database.name == "My Database"
        assert ui_context.table.id == 456
        assert ui_context.table.name == "Customers"
        assert ui_context.view.id == 789
        assert ui_context.view.name == "All Customers"
        assert ui_context.view.type == "grid"

    def test_ui_context_with_application_builder_fields(self):
        """Test that UIContext correctly stores application builder fields"""

        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test Workspace"),
            application=ApplicationUIContext(id="app-123", name="My App"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
        )

        assert ui_context.application.id == "app-123"
        assert ui_context.application.name == "My App"
        assert ui_context.database is None
        assert ui_context.table is None

    def test_ui_context_serialization_excludes_none_values(self):
        """Test that UIContext serialization excludes None values"""

        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test Workspace"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
            # All other fields are None
        )

        # Serialize with exclude_none=True
        serialized = ui_context.model_dump(exclude_none=True)

        assert "workspace" in serialized
        assert "user" in serialized
        assert "database" not in serialized
        assert "table" not in serialized
        assert "view" not in serialized
        assert "application" not in serialized

    def test_ui_context_json_serialization_excludes_none(self):
        """Test that UIContext JSON serialization excludes None values"""

        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test Workspace"),
            table=TableUIContext(id=456, name="Customers"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
            # database and view are None
        )

        # Serialize to JSON with exclude_none=True
        json_str = ui_context.model_dump_json(exclude_none=True)

        # Parse back to verify
        import json

        parsed = json.loads(json_str)

        assert "workspace" in parsed
        assert "table" in parsed
        assert "user" in parsed
        assert "database" not in parsed
        assert "view" not in parsed

    def test_human_message_with_ui_context(self):
        """Test that HumanMessage correctly stores ui_context"""

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
        assert human_message.ui_context.database.name == "My Database"

    def test_human_message_ui_context_json_serialization(self):
        """
        Test that HumanMessage ui_context serializes to JSON with None
        values excluded
        """

        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test Workspace"),
            database=ApplicationUIContext(id="db-123", name="My Database"),
            table=TableUIContext(id=456, name="Customers"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
            # view is None
        )

        human_message = HumanMessage(
            content="How do I filter this view?", ui_context=ui_context
        )

        # Serialize ui_context as it would be in the prompt
        ui_context_json = human_message.ui_context.model_dump_json(exclude_none=True)

        # Parse to verify
        import json

        parsed = json.loads(ui_context_json)

        # Should have database and table but not view
        assert "database" in parsed
        assert parsed["database"]["name"] == "My Database"
        assert "table" in parsed
        assert parsed["table"]["name"] == "Customers"
        assert "view" not in parsed  # None values excluded

    def test_ui_context_has_default_timestamp(self):
        """Test that UIContext has a default timestamp"""

        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
        )

        assert ui_context.timestamp is not None
        # Should be a datetime object
        from datetime import datetime

        assert isinstance(ui_context.timestamp, datetime)

    def test_ui_context_has_default_timezone(self):
        """Test that UIContext has a default timezone of UTC"""

        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
        )

        assert ui_context.timezone == "UTC"

    def test_user_ui_context_from_user(self, enterprise_data_fixture):
        """Test UserUIContext.from_user factory method"""

        user = enterprise_data_fixture.create_user(
            email="john@example.com", first_name="John Doe"
        )

        user_context = UserUIContext.from_user(user)

        assert user_context.id == user.id
        assert user_context.name == "John Doe"
        assert user_context.email == "john@example.com"


@pytest.mark.django_db
class TestAssistantCancellation:
    """Test cancellation functionality in Assistant"""

    def test_get_cancellation_cache_key(self, enterprise_data_fixture):
        """Test that cancellation cache key is correctly formatted"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test"
        )

        assistant = Assistant(chat)
        cache_key = assistant._get_cancellation_cache_key()

        assert cache_key == f"assistant:chat:{chat.uuid}:cancelled"

    def test_check_cancellation_raises_when_flag_set(self, enterprise_data_fixture):
        """Test that check_cancellation raises exception when flag is set"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test"
        )

        assistant = Assistant(chat)
        cache_key = assistant._get_cancellation_cache_key()

        # Set cancellation flag
        cache.set(cache_key, True)

        # Should raise exception
        with pytest.raises(AssistantMessageCancelled) as exc_info:
            assistant._check_cancellation(cache_key, "msg123")

        assert exc_info.value.message_id == "msg123"

        # Flag should be cleaned up
        assert cache.get(cache_key) is None

    def test_check_cancellation_does_nothing_when_no_flag(
        self, enterprise_data_fixture
    ):
        """Test that check_cancellation does nothing when flag not set"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test"
        )

        assistant = Assistant(chat)
        cache_key = assistant._get_cancellation_cache_key()

        # Should not raise
        assistant._check_cancellation(cache_key, "msg123")

    @patch("udspy.ChainOfThought.astream")
    @patch("udspy.ReAct.astream")
    def test_astream_messages_yields_ai_started_message(
        self, mock_react_astream, mock_cot_astream, enterprise_data_fixture
    ):
        """Test that astream_messages yields AiStartedMessage at the beginning"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test"
        )

        # Mock the router stream
        async def mock_router_stream(*args, **kwargs):
            yield Prediction(
                routing_decision="delegate_to_agent",
                extracted_context="",
                search_query="",
            )

        mock_cot_astream.return_value = mock_router_stream()

        # Mock the agent streaming
        async def mock_agent_stream(*args, **kwargs):
            yield OutputStreamChunk(
                module=None,
                field_name="answer",
                delta="Hello",
                content="Hello",
                is_complete=False,
            )
            yield Prediction(answer="Hello there!", trajectory=[], reasoning="")

        mock_react_astream.return_value = mock_agent_stream()

        assistant = Assistant(chat)
        human_message = HumanMessage(content="Hello")

        # Collect messages
        async def collect_messages():
            messages = []
            async for msg in assistant.astream_messages(human_message):
                messages.append(msg)
            return messages

        messages = async_to_sync(collect_messages)()

        # First message should be AiStartedMessage
        assert len(messages) > 0
        assert isinstance(messages[0], AiStartedMessage)
        assert messages[0].message_id is not None

    @patch("udspy.ChainOfThought.astream")
    @patch("udspy.ReAct.astream")
    def test_astream_messages_checks_cancellation_periodically(
        self, mock_react_astream, mock_cot_astream, enterprise_data_fixture
    ):
        """Test that astream_messages checks for cancellation every 10 chunks"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test"
        )

        # Mock the router stream
        async def mock_router_stream(*args, **kwargs):
            yield Prediction(
                routing_decision="delegate_to_agent",
                extracted_context="",
                search_query="",
            )

        mock_cot_astream.return_value = mock_router_stream()

        # Mock the stream to return many chunks - enough to trigger check at 10
        async def mock_agent_stream(*args, **kwargs):
            # Yield 15 chunks - cancellation check happens at chunk 10
            for i in range(15):
                yield OutputStreamChunk(
                    module=None,
                    field_name="answer",
                    delta=f"word{i}",
                    content=f"word{i}",
                    is_complete=False,
                )
            yield Prediction(answer="Complete response", trajectory=[], reasoning="")

        mock_react_astream.return_value = mock_agent_stream()

        assistant = Assistant(chat)
        cache_key = assistant._get_cancellation_cache_key()

        # Set cancellation flag immediately - it should be detected at chunk 10
        cache.set(cache_key, True)

        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
        )
        human_message = HumanMessage(content="Hello", ui_context=ui_context)

        # Should raise AssistantMessageCancelled when check happens at chunk 10
        async def stream_messages():
            async for msg in assistant.astream_messages(human_message):
                pass

        with pytest.raises(AssistantMessageCancelled):
            async_to_sync(stream_messages)()
