"""
Tests for the Assistant class focusing on behaviors rather than implementation details.

These tests verify that the Assistant:
- Correctly loads and formats chat history for context
- Persists messages to the database during streaming
- Handles sources from tool outputs correctly
- Generates and persists chat titles appropriately
- Adapts its signature based on chat state
"""
from unittest.mock import MagicMock, patch

import pytest
from dspy.primitives.prediction import Prediction
from dspy.streaming import StreamResponse

from baserow_enterprise.assistant.assistant import Assistant, AssistantCallbacks
from baserow_enterprise.assistant.models import AssistantChat, AssistantChatMessage
from baserow_enterprise.assistant.types import (
    AiMessageChunk,
    AiThinkingMessage,
    ChatTitleMessage,
    UIContext,
    WorkspaceUIContext,
)


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
        tool_instance.name = "search_docs"
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

    @pytest.mark.asyncio
    async def test_list_chat_messages_returns_in_chronological_order(
        self, enterprise_data_fixture
    ):
        """Test that list_chat_messages returns messages oldest to newest"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Create messages in order
        msg1 = await AssistantChatMessage.objects.acreate(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="First question"
        )
        msg2 = await AssistantChatMessage.objects.acreate(
            chat=chat, role=AssistantChatMessage.Role.AI, content="First answer"
        )
        msg3 = await AssistantChatMessage.objects.acreate(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Second question"
        )

        assistant = Assistant(chat)
        messages = assistant.list_chat_messages()

        # Should be in chronological order (oldest first)
        assert len(messages) == 3
        assert messages[0].content == "First question"
        assert messages[1].content == "First answer"
        assert messages[2].content == "Second question"

    @pytest.mark.asyncio
    async def test_aload_chat_history_formats_as_question_answer_pairs(
        self, enterprise_data_fixture
    ):
        """Test that chat history is loaded as question/answer pairs for DSPy"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Create conversation history
        await AssistantChatMessage.objects.acreate(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="What is Baserow?"
        )
        await AssistantChatMessage.objects.acreate(
            chat=chat,
            role=AssistantChatMessage.Role.AI,
            content="Baserow is a no-code database platform.",
        )
        await AssistantChatMessage.objects.acreate(
            chat=chat,
            role=AssistantChatMessage.Role.HUMAN,
            content="How do I create a table?",
        )
        await AssistantChatMessage.objects.acreate(
            chat=chat,
            role=AssistantChatMessage.Role.AI,
            content="You can create a table by clicking the + button.",
        )

        assistant = Assistant(chat)
        await assistant.aload_chat_history()

        # History should contain question/answer pairs
        assert assistant.history is not None
        assert len(assistant.history.messages) == 2

        # First pair
        assert assistant.history.messages[0]["question"] == "What is Baserow?"
        assert (
            assistant.history.messages[0]["answer"]
            == "Baserow is a no-code database platform."
        )

        # Second pair
        assert assistant.history.messages[1]["question"] == "How do I create a table?"
        assert (
            assistant.history.messages[1]["answer"]
            == "You can create a table by clicking the + button."
        )

    @pytest.mark.asyncio
    async def test_aload_chat_history_respects_limit(self, enterprise_data_fixture):
        """Test that history loading respects the limit parameter"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Create 10 message pairs (20 messages)
        for i in range(10):
            await AssistantChatMessage.objects.acreate(
                chat=chat,
                role=AssistantChatMessage.Role.HUMAN,
                content=f"Question {i}",
            )
            await AssistantChatMessage.objects.acreate(
                chat=chat, role=AssistantChatMessage.Role.AI, content=f"Answer {i}"
            )

        assistant = Assistant(chat)
        await assistant.aload_chat_history(limit=6)  # Last 6 messages = 3 pairs

        # Should only load the most recent 3 pairs
        assert len(assistant.history.messages) <= 3

    @pytest.mark.asyncio
    async def test_aload_chat_history_handles_incomplete_pairs(
        self, enterprise_data_fixture
    ):
        """
        Test that incomplete message pairs (e.g., orphaned human messages) are skipped
        """

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Create complete pair
        await AssistantChatMessage.objects.acreate(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Question 1"
        )
        await AssistantChatMessage.objects.acreate(
            chat=chat, role=AssistantChatMessage.Role.AI, content="Answer 1"
        )

        # Create orphaned human message (no AI response yet)
        await AssistantChatMessage.objects.acreate(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Question 2"
        )

        assistant = Assistant(chat)
        await assistant.aload_chat_history()

        # Should only include the complete pair
        assert len(assistant.history.messages) == 1
        assert assistant.history.messages[0]["question"] == "Question 1"


@pytest.mark.django_db
class TestAssistantSignature:
    """Test that the Assistant adapts its signature based on chat state"""

    def test_signature_includes_title_field_for_new_chats(
        self, enterprise_data_fixture
    ):
        """Test that new chats (without title) include chat_title in signature"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title=""  # Empty title = new chat
        )

        assistant = Assistant(chat)
        signature = assistant._get_chat_signature()

        # Should have chat_title field for new chats
        assert "chat_title" in signature.fields
        assert "answer" in signature.fields
        assert "question" in signature.fields

    def test_signature_excludes_title_field_for_existing_chats(
        self, enterprise_data_fixture
    ):
        """
        Test that existing chats (with title) don't include chat_title in signature
        """

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Existing Chat"
        )

        assistant = Assistant(chat)
        signature = assistant._get_chat_signature()

        # Should NOT have chat_title field for existing chats
        assert "chat_title" not in signature.fields
        assert "answer" in signature.fields
        assert "question" in signature.fields


@pytest.mark.django_db
class TestAssistantMessagePersistence:
    """Test that messages are persisted correctly during streaming"""

    @pytest.mark.asyncio
    @patch("baserow_enterprise.assistant.assistant.dspy.streamify")
    @patch("baserow_enterprise.assistant.assistant.dspy.LM")
    async def test_astream_messages_persists_human_message(
        self, mock_lm, mock_streamify, enterprise_data_fixture
    ):
        """Test that human messages are persisted to database before streaming"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Mock the streaming
        async def mock_stream(*args, **kwargs):
            # Yield a simple response
            yield StreamResponse(
                signature_field_name="answer",
                chunk="Hello",
                predict_name="ReAct",
                is_last_chunk=False,
            )
            yield Prediction(answer="Hello")

        mock_streamify.return_value = MagicMock(return_value=mock_stream())

        assistant = Assistant(chat)
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name)
        )

        # Consume the stream
        async for _ in assistant.astream_messages("Test message", ui_context):
            pass

        # Human message should be persisted
        human_messages = await AssistantChatMessage.objects.filter(
            chat=chat, role=AssistantChatMessage.Role.HUMAN
        ).acount()
        assert human_messages == 1

        saved_message = await AssistantChatMessage.objects.filter(
            chat=chat, role=AssistantChatMessage.Role.HUMAN
        ).afirst()
        assert saved_message.content == "Test message"

    @pytest.mark.asyncio
    @patch("baserow_enterprise.assistant.assistant.dspy.streamify")
    @patch("baserow_enterprise.assistant.assistant.dspy.LM")
    async def test_astream_messages_persists_ai_message_with_sources(
        self, mock_lm, mock_streamify, enterprise_data_fixture
    ):
        """Test that AI messages are persisted with sources in artifacts"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Mock the streaming with a Prediction at the end
        async def mock_stream(*args, **kwargs):
            yield StreamResponse(
                signature_field_name="answer",
                chunk="Based on docs",
                predict_name="ReAct",
                is_last_chunk=False,
            )
            yield Prediction(answer="Based on docs")

        mock_streamify.return_value = MagicMock(return_value=mock_stream())

        assistant = Assistant(chat)
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name)
        )

        # Manually add sources to callback manager (simulating tool execution)
        messages = []
        async for msg in assistant.astream_messages("Question", ui_context):
            messages.append(msg)

        # AI message should be persisted
        ai_messages = await AssistantChatMessage.objects.filter(
            chat=chat, role=AssistantChatMessage.Role.AI
        ).acount()
        assert ai_messages == 1

    @pytest.mark.asyncio
    @patch("baserow_enterprise.assistant.assistant.dspy.streamify")
    @patch("baserow_enterprise.assistant.assistant.dspy.LM")
    async def test_astream_messages_persists_chat_title(
        self, mock_lm, mock_streamify, enterprise_data_fixture
    ):
        """Test that chat titles are persisted to the database"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title=""  # New chat
        )

        # Mock streaming with title generation
        async def mock_stream(*args, **kwargs):
            yield StreamResponse(
                signature_field_name="answer",
                chunk="Hello",
                predict_name="ReAct",
                is_last_chunk=False,
            )
            yield StreamResponse(
                signature_field_name="chat_title",
                chunk="Greeting",
                predict_name="ReAct",
                is_last_chunk=False,
            )
            yield Prediction(answer="Hello", chat_title="Greeting")

        mock_streamify.return_value = MagicMock(return_value=mock_stream())

        assistant = Assistant(chat)
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name)
        )

        # Consume the stream
        async for _ in assistant.astream_messages("Hello", ui_context):
            pass

        # Refresh from DB
        await chat.arefresh_from_db()

        # Title should be persisted
        assert chat.title == "Greeting"


@pytest.mark.django_db
class TestAssistantStreaming:
    """Test streaming behavior of the Assistant"""

    @pytest.mark.asyncio
    @patch("baserow_enterprise.assistant.assistant.dspy.streamify")
    @patch("baserow_enterprise.assistant.assistant.dspy.LM")
    async def test_astream_messages_yields_answer_chunks(
        self, mock_lm, mock_streamify, enterprise_data_fixture
    ):
        """Test that answer chunks are yielded during streaming"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Mock streaming
        async def mock_stream(*args, **kwargs):
            yield StreamResponse(
                signature_field_name="answer",
                chunk="Hello",
                predict_name="ReAct",
                is_last_chunk=False,
            )
            yield StreamResponse(
                signature_field_name="answer",
                chunk=" world",
                predict_name="ReAct",
                is_last_chunk=False,
            )
            yield Prediction(answer="Hello world")

        mock_streamify.return_value = MagicMock(return_value=mock_stream())

        assistant = Assistant(chat)
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name)
        )

        chunks = []
        async for msg in assistant.astream_messages("Test", ui_context):
            if isinstance(msg, AiMessageChunk):
                chunks.append(msg)

        # Should receive chunks with accumulated content
        assert len(chunks) == 2
        assert chunks[0].content == "Hello"
        assert chunks[1].content == "Hello world"

    @pytest.mark.asyncio
    @patch("baserow_enterprise.assistant.assistant.dspy.streamify")
    @patch("baserow_enterprise.assistant.assistant.dspy.LM")
    async def test_astream_messages_yields_title_chunks(
        self, mock_lm, mock_streamify, enterprise_data_fixture
    ):
        """Test that title chunks are yielded for new chats"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title=""  # New chat
        )

        # Mock streaming
        async def mock_stream(*args, **kwargs):
            yield StreamResponse(
                signature_field_name="answer",
                chunk="Answer",
                predict_name="ReAct",
                is_last_chunk=False,
            )
            yield StreamResponse(
                signature_field_name="chat_title",
                chunk="Title",
                predict_name="ReAct",
                is_last_chunk=False,
            )
            yield Prediction(answer="Answer", chat_title="Title")

        mock_streamify.return_value = MagicMock(return_value=mock_stream())

        assistant = Assistant(chat)
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name)
        )

        title_messages = []
        async for msg in assistant.astream_messages("Test", ui_context):
            if isinstance(msg, ChatTitleMessage):
                title_messages.append(msg)

        # Should receive title chunks
        assert len(title_messages) == 1
        assert title_messages[0].content == "Title"

    @pytest.mark.asyncio
    @patch("baserow_enterprise.assistant.assistant.dspy.streamify")
    @patch("baserow_enterprise.assistant.assistant.dspy.LM")
    async def test_astream_messages_yields_thinking_messages(
        self, mock_lm, mock_streamify, enterprise_data_fixture
    ):
        """Test that thinking messages from tools are yielded"""

        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        # Mock streaming
        async def mock_stream(*args, **kwargs):
            yield AiThinkingMessage(code="thinking")
            yield StreamResponse(
                signature_field_name="answer",
                chunk="Answer",
                predict_name="ReAct",
                is_last_chunk=False,
            )
            yield Prediction(answer="Answer")

        mock_streamify.return_value = MagicMock(return_value=mock_stream())

        assistant = Assistant(chat)
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name)
        )

        thinking_messages = []
        async for msg in assistant.astream_messages("Test", ui_context):
            if isinstance(msg, AiThinkingMessage):
                thinking_messages.append(msg)

        # Should receive thinking messages
        assert len(thinking_messages) == 1
        assert thinking_messages[0].code == "thinking"
