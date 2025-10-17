import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import override_settings
from django.urls import reverse

import pytest
from freezegun import freeze_time

from baserow.test_utils.helpers import AnyStr
from baserow_enterprise.assistant.models import AssistantChat
from baserow_enterprise.assistant.types import (
    AiErrorMessage,
    AiMessage,
    AiMessageChunk,
    AiThinkingMessage,
    ChatTitleMessage,
    HumanMessage,
    UIContext,
    UserUIContext,
    WorkspaceUIContext,
)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_list_assistant_chats_without_valid_workspace(
    api_client, enterprise_data_fixture, enable_enterprise
):
    _, token = enterprise_data_fixture.create_user_and_token()

    rsp = api_client.get(
        reverse("assistant:list"),  # missing workspace_id
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == 400
    assert rsp.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
    assert rsp.json()["detail"]["workspace_id"][0]["code"] == "required"

    rsp = api_client.get(
        reverse("assistant:list") + f"?workspace_id=0",  # non existing workspace
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == 404
    assert rsp.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    workspace = enterprise_data_fixture.create_workspace()

    rsp = api_client.get(
        reverse("assistant:list") + f"?workspace_id={workspace.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == 400
    assert rsp.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_list_assistant_chats_without_license(
    api_client, enterprise_data_fixture
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    rsp = api_client.get(
        reverse("assistant:list") + f"?workspace_id={workspace.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == 402
    assert rsp.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_assistant_chats(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chats_count = 10
    chats = [
        AssistantChat(workspace=workspace, user=user, title=f"Chat {i}")
        for i in range(chats_count)
    ]
    with freeze_time("2024-01-14 12:00:00"):
        AssistantChat.objects.bulk_create(chats)

    rsp = api_client.get(
        reverse("assistant:list") + f"?workspace_id={workspace.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == 200
    data = rsp.json()
    assert data["count"] == chats_count
    assert len(data["results"]) == chats_count
    for i in range(chats_count):
        chat = data["results"][i]
        assert chat == {
            "uuid": AnyStr(),
            "user_id": user.id,
            "workspace_id": workspace.id,
            "title": f"Chat {i}",
            "status": AssistantChat.Status.IDLE,
            "created_on": "2024-01-14T12:00:00Z",
            "updated_on": "2024-01-14T12:00:00Z",
        }
    assert data["previous"] is None
    assert data["next"] is None

    rsp = api_client.get(
        reverse("assistant:list") + f"?workspace_id={workspace.id}&offset=2&limit=1",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200
    data = rsp.json()
    assert data["count"] == 10
    assert len(data["results"]) == 1
    assert data["results"][0] == {
        "uuid": AnyStr(),
        "user_id": user.id,
        "workspace_id": workspace.id,
        "title": "Chat 2",
        "status": AssistantChat.Status.IDLE,
        "created_on": "2024-01-14T12:00:00Z",
        "updated_on": "2024-01-14T12:00:00Z",
    }
    assert data["previous"] is not None
    assert data["next"] is not None


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_send_message_without_valid_workspace(
    api_client, enterprise_data_fixture, enable_enterprise
):
    """Test that sending a message requires a valid workspace"""

    _, token = enterprise_data_fixture.create_user_and_token()
    chat_uuid = str(uuid4())

    # Test with non-existing workspace
    rsp = api_client.post(
        reverse(
            "assistant:chat_messages",
            kwargs={"chat_uuid": chat_uuid},
        ),
        data={
            "content": "Hello AI",
            "ui_context": {"workspace": {"id": 999999, "name": "Non-existent"}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == 404
    assert rsp.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    # Test with workspace user doesn't belong to
    workspace = enterprise_data_fixture.create_workspace()
    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "Hello AI",
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == 400
    assert rsp.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_send_message_without_license(api_client, enterprise_data_fixture):
    """Test that sending messages requires an enterprise license"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    chat_uuid = str(uuid4())

    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "Hello AI",
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == 402
    assert rsp.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"


@pytest.mark.django_db()
@override_settings(DEBUG=True)
@patch("baserow_enterprise.assistant.handler.Assistant")
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_send_message_creates_chat_if_not_exists(
    mock_handler_class, mock_assistant_class, api_client, enterprise_data_fixture
):
    """Test that sending a message creates a chat if it doesn't exist"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chat_uuid = uuid4()

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock chat creation
    mock_chat = MagicMock(spec=AssistantChat)
    mock_chat.uuid = chat_uuid
    mock_chat.workspace = workspace
    mock_chat.user = user
    mock_handler.get_or_create_chat.return_value = (mock_chat, True)

    # Mock the assistant
    mock_assistant = MagicMock()
    mock_handler.get_assistant.return_value = mock_assistant

    async def mock_astream(human_message):
        # Simulate AI response messages
        yield AiMessage(content="Hello! How can I help you today?")

    mock_assistant.astream_messages = mock_astream

    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "Hello AI",
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200
    assert rsp["Content-Type"] == "text/event-stream"

    # Consume the streaming response
    chunks = rsp.stream_chunks()

    # Verify we got streaming content
    assert len(chunks) > 0
    ai_response = json.loads(chunks[0])
    assert ai_response["type"] == "ai/message"
    assert ai_response["content"] == "Hello! How can I help you today?"

    # Verify handler was called correctly
    mock_handler.get_or_create_chat.assert_called_once_with(user, workspace, chat_uuid)


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.assistant.handler.Assistant")
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_send_message_streams_response(
    mock_handler_class, mock_assistant_class, api_client, enterprise_data_fixture
):
    """Test that the endpoint streams AI responses properly"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chat_uuid = str(uuid4())

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock chat creation
    mock_chat = MagicMock(spec=AssistantChat)
    mock_chat.uuid = chat_uuid
    mock_chat.workspace = workspace
    mock_chat.user = user
    mock_handler.get_or_create_chat.return_value = (mock_chat, True)

    # Mock the assistant
    mock_assistant = MagicMock()
    mock_handler.get_assistant.return_value = mock_assistant

    # Mock assistant with async generator for streaming
    response_messages = [
        AiMessage(content="I'm thinking..."),
        AiMessage(content="Here's my response!"),
        ChatTitleMessage(content="Chat about AI assistance"),
    ]

    async def mock_astream(human_message):
        for msg in response_messages:
            yield msg

    mock_assistant.astream_messages = mock_astream

    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "Tell me about AI",
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200
    assert rsp["Content-Type"] == "text/event-stream"

    # Read the streamed content
    chunks = rsp.stream_chunks()

    # Parse the streamed messages
    messages = []
    for line in chunks:
        if line:
            messages.append(json.loads(line))

    assert len(messages) == 3

    # Check first message
    assert messages[0]["content"] == "I'm thinking..."
    assert messages[0]["type"] == "ai/message"

    # Check second message
    assert messages[1]["content"] == "Here's my response!"
    assert messages[1]["type"] == "ai/message"

    # Check title update message
    assert messages[2]["content"] == "Chat about AI assistance"
    assert messages[2]["type"] == "chat/title"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_send_message_validates_request_body(api_client, enterprise_data_fixture):
    """Test that the endpoint validates the request body properly"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chat_uuid = str(uuid4())

    # Test missing content
    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == 400
    assert "content" in str(rsp.json())

    # Test missing ui_context
    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "Hello",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == 400
    assert "ui_context" in str(rsp.json())


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_get_messages_without_valid_chat(api_client, enterprise_data_fixture):
    """Test that getting messages requires a valid chat"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    non_existent_uuid = str(uuid4())

    rsp = api_client.get(
        reverse(
            "assistant:chat_messages",
            kwargs={"chat_uuid": non_existent_uuid},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == 404
    assert rsp.json()["error"] == "ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_get_messages_without_license(api_client, enterprise_data_fixture):
    """Test that getting messages requires an enterprise license"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    # Create a chat
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )

    rsp = api_client.get(
        reverse(
            "assistant:chat_messages",
            kwargs={"chat_uuid": str(chat.uuid)},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == 402
    assert rsp.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_get_messages_from_another_users_chat(
    api_client, enterprise_data_fixture
):
    """Test that users can only get messages from their own chats"""

    user1, _ = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(members=[user1, user2])
    enterprise_data_fixture.enable_enterprise()

    # Create a chat for user1
    chat = AssistantChat.objects.create(
        user=user1, workspace=workspace, title="User1's Chat"
    )

    # Try to access it as user2
    rsp = api_client.get(
        reverse(
            "assistant:chat_messages",
            kwargs={"chat_uuid": str(chat.uuid)},
        ),
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert rsp.status_code == 404
    assert rsp.json()["error"] == "ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_get_messages_returns_chat_history(
    mock_handler_class, api_client, enterprise_data_fixture
):
    """Test that the endpoint returns the chat message history"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create a chat
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock get_chat to return the chat
    mock_handler.get_chat.return_value = chat

    # Mock message history - only HumanMessage and AiMessage are returned
    message_history = [
        HumanMessage(
            id=1,
            content="What's the weather like?",
            ui_context=UIContext(
                workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
                user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
            ),
        ),
        AiMessage(
            id=2,
            content="I don't have access to real-time weather data.",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        ),
        HumanMessage(
            id=3,
            content="Can you help me with Baserow?",
            ui_context=UIContext(
                workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
                user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
            ),
        ),
        AiMessage(
            id=4,
            content="Of course! I'd be happy to help you with Baserow.",
            timestamp=datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc),
        ),
    ]
    mock_handler.list_chat_messages.return_value = message_history

    rsp = api_client.get(
        reverse(
            "assistant:chat_messages",
            kwargs={"chat_uuid": str(chat.uuid)},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200
    data = rsp.json()

    assert "messages" in data
    assert len(data["messages"]) == 4

    # Check first message (human)
    assert data["messages"][0]["content"] == "What's the weather like?"
    assert data["messages"][0]["type"] == "human"
    assert data["messages"][0]["id"] == 1

    # Check second message (AI)
    assert (
        data["messages"][1]["content"]
        == "I don't have access to real-time weather data."
    )
    assert data["messages"][1]["type"] == "ai/message"
    assert data["messages"][1]["id"] == 2
    assert "timestamp" in data["messages"][1]

    # Check third message (human)
    assert data["messages"][2]["content"] == "Can you help me with Baserow?"
    assert data["messages"][2]["type"] == "human"
    assert data["messages"][2]["id"] == 3

    # Check fourth message (AI)
    assert (
        data["messages"][3]["content"]
        == "Of course! I'd be happy to help you with Baserow."
    )
    assert data["messages"][3]["type"] == "ai/message"
    assert data["messages"][3]["id"] == 4
    assert "timestamp" in data["messages"][3]

    # Verify handler was called correctly
    mock_handler.get_chat.assert_called_once_with(user, chat.uuid)
    mock_handler.list_chat_messages.assert_called_once_with(chat)


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_get_messages_returns_empty_list_for_new_chat(
    mock_handler_class, api_client, enterprise_data_fixture
):
    """Test that the endpoint returns an empty list for a chat with no messages"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create a chat
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Empty Chat"
    )

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock get_chat to return the chat
    mock_handler.get_chat.return_value = chat

    # Mock empty message history
    mock_handler.get_chat_messages.return_value = []

    rsp = api_client.get(
        reverse(
            "assistant:chat_messages",
            kwargs={"chat_uuid": str(chat.uuid)},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200
    data = rsp.json()

    assert "messages" in data
    assert data["messages"] == []


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_get_messages_with_different_message_types(
    mock_handler_class, api_client, enterprise_data_fixture
):
    """Test that the endpoint correctly handles different message types"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create a chat
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock get_chat to return the chat
    mock_handler.get_chat.return_value = chat

    # Mock message history - only HumanMessage and AiMessage are returned
    message_history = [
        HumanMessage(
            id=1,
            content="Hello",
            ui_context=UIContext(
                workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
                user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
            ),
        ),
        AiMessage(
            id=2,
            content="Hi there! How can I help you?",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        ),
        HumanMessage(
            id=3,
            content="Tell me about Baserow",
            ui_context=UIContext(
                workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
                user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
            ),
        ),
        AiMessage(
            id=4,
            content="Baserow is an open-source no-code database platform.",
            timestamp=datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc),
        ),
    ]
    mock_handler.list_chat_messages.return_value = message_history

    rsp = api_client.get(
        reverse(
            "assistant:chat_messages",
            kwargs={"chat_uuid": str(chat.uuid)},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200
    data = rsp.json()

    assert len(data["messages"]) == 4

    # Check first human message has id
    assert data["messages"][0]["content"] == "Hello"
    assert data["messages"][0]["type"] == "human"
    assert data["messages"][0]["id"] == 1

    # Check first AI message has id and timestamp
    assert data["messages"][1]["content"] == "Hi there! How can I help you?"
    assert data["messages"][1]["type"] == "ai/message"
    assert data["messages"][1]["id"] == 2
    assert "timestamp" in data["messages"][1]

    # Check second human message
    assert data["messages"][2]["content"] == "Tell me about Baserow"
    assert data["messages"][2]["type"] == "human"
    assert data["messages"][2]["id"] == 3

    # Check second AI message
    assert (
        data["messages"][3]["content"]
        == "Baserow is an open-source no-code database platform."
    )
    assert data["messages"][3]["type"] == "ai/message"
    assert data["messages"][3]["id"] == 4
    assert "timestamp" in data["messages"][3]


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.assistant.handler.Assistant")
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_send_message_streams_sources_from_tools(
    mock_handler_class, mock_assistant_class, api_client, enterprise_data_fixture
):
    """Test that sources from tool calls are included in streamed responses"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chat_uuid = str(uuid4())

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock chat creation
    mock_chat = MagicMock(spec=AssistantChat)
    mock_chat.uuid = chat_uuid
    mock_chat.workspace = workspace
    mock_chat.user = user
    mock_handler.get_or_create_chat.return_value = (mock_chat, True)

    # Mock the assistant
    mock_assistant = MagicMock()
    mock_handler.get_assistant.return_value = mock_assistant

    # Mock assistant with sources from tool calls
    async def mock_astream(human_message):
        # First chunk without sources
        yield AiMessageChunk(content="Let me search for that...")
        # Second chunk with sources (as if a tool was called)
        yield AiMessageChunk(
            content="Let me search for that... Based on the documentation,",
            sources=["https://baserow.io/user-docs/database"],
        )
        # Third chunk with more sources
        yield AiMessageChunk(
            content="Let me search for that... Based on the documentation, you can use fields",
            sources=[
                "https://baserow.io/user-docs/database",
                "https://baserow.io/user-docs/fields",
            ],
        )

    mock_assistant.astream_messages = mock_astream

    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "How do I create a field?",
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200
    assert rsp["Content-Type"] == "text/event-stream"

    # Read the streamed content
    chunks = rsp.stream_chunks()

    # Parse the streamed messages
    messages = [json.loads(line) for line in chunks if line]

    assert len(messages) == 3

    # First chunk has no sources
    assert messages[0]["content"] == "Let me search for that..."
    assert messages[0].get("sources") is None

    # Second chunk has one source
    assert (
        messages[1]["content"]
        == "Let me search for that... Based on the documentation,"
    )
    assert messages[1]["sources"] == ["https://baserow.io/user-docs/database"]

    # Third chunk has two sources (accumulated)
    assert messages[2]["sources"] == [
        "https://baserow.io/user-docs/database",
        "https://baserow.io/user-docs/fields",
    ]


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.assistant.handler.Assistant")
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_send_message_streams_thinking_messages_during_tool_execution(
    mock_handler_class, mock_assistant_class, api_client, enterprise_data_fixture
):
    """Test that thinking messages are streamed during tool execution"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chat_uuid = str(uuid4())

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock chat creation
    mock_chat = MagicMock(spec=AssistantChat)
    mock_chat.uuid = chat_uuid
    mock_chat.workspace = workspace
    mock_chat.user = user
    mock_handler.get_or_create_chat.return_value = (mock_chat, True)

    # Mock the assistant
    mock_assistant = MagicMock()
    mock_handler.get_assistant.return_value = mock_assistant

    # Mock assistant with thinking messages (simulating tool execution)
    async def mock_astream(human_message):
        # Initial thinking
        yield AiThinkingMessage(content="Thinking...")
        # Tool-specific thinking (e.g., searching docs)
        yield AiThinkingMessage(content="Searching documentation...")
        # Analyzing results
        yield AiThinkingMessage(content="Analyzing results...")
        # Final answer
        yield AiMessageChunk(
            content="Based on the documentation, here's how to do it...",
            sources=["https://baserow.io/user-docs"],
        )

    mock_assistant.astream_messages = mock_astream

    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "How do I use webhooks?",
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200
    assert rsp["Content-Type"] == "text/event-stream"

    # Read the streamed content
    chunks = rsp.stream_chunks()

    # Parse the streamed messages
    messages = [json.loads(line) for line in chunks if line]

    assert len(messages) == 4

    # First three messages are thinking messages
    assert messages[0]["type"] == "ai/thinking"
    assert messages[0]["content"] == "Thinking..."

    assert messages[1]["type"] == "ai/thinking"
    assert messages[1]["content"] == "Searching documentation..."

    assert messages[2]["type"] == "ai/thinking"
    assert messages[2]["content"] == "Analyzing results..."

    # Final message is the answer
    assert messages[3]["type"] == "ai/message"
    assert (
        messages[3]["content"] == "Based on the documentation, here's how to do it..."
    )
    assert messages[3]["sources"] == ["https://baserow.io/user-docs"]


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.assistant.handler.Assistant")
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_send_message_generates_chat_title_on_first_message(
    mock_handler_class, mock_assistant_class, api_client, enterprise_data_fixture
):
    """Test that a chat title is generated and streamed on the first message"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chat_uuid = str(uuid4())

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock chat creation (empty title, indicates first message)
    mock_chat = MagicMock(spec=AssistantChat)
    mock_chat.uuid = chat_uuid
    mock_chat.workspace = workspace
    mock_chat.user = user
    mock_chat.title = ""  # Empty title for new chat
    mock_handler.get_or_create_chat.return_value = (mock_chat, True)

    # Mock the assistant
    mock_assistant = MagicMock()
    mock_handler.get_assistant.return_value = mock_assistant

    # Mock assistant that generates title on first message
    async def mock_astream(human_message):
        # Stream the answer
        yield AiMessageChunk(content="Hello! How can I help you?")
        # Stream the generated title
        yield ChatTitleMessage(content="Greeting and Assistance")

    mock_assistant.astream_messages = mock_astream

    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "Hello!",
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200
    assert rsp["Content-Type"] == "text/event-stream"

    # Read the streamed content
    chunks = rsp.stream_chunks()

    # Parse the streamed messages
    messages = [json.loads(line) for line in chunks if line]

    assert len(messages) == 2

    # First message is the answer
    assert messages[0]["type"] == "ai/message"
    assert messages[0]["content"] == "Hello! How can I help you?"

    # Second message is the title
    assert messages[1]["type"] == "chat/title"
    assert messages[1]["content"] == "Greeting and Assistance"


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.assistant.handler.Assistant")
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_send_message_does_not_generate_title_on_subsequent_messages(
    mock_handler_class, mock_assistant_class, api_client, enterprise_data_fixture
):
    """Test that chat title is NOT regenerated on subsequent messages"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create existing chat with title
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Existing Chat Title"
    )

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock chat retrieval (has existing title)
    mock_chat = MagicMock(spec=AssistantChat)
    mock_chat.uuid = chat.uuid
    mock_chat.workspace = workspace
    mock_chat.user = user
    mock_chat.title = "Existing Chat Title"  # Already has title
    mock_handler.get_or_create_chat.return_value = (mock_chat, False)

    # Mock the assistant
    mock_assistant = MagicMock()
    mock_handler.get_assistant.return_value = mock_assistant

    # Mock assistant that only streams answer (no title)
    async def mock_astream(human_message):
        # Only stream the answer, no title
        yield AiMessageChunk(content="Here's the answer to your follow-up question.")

    mock_assistant.astream_messages = mock_astream

    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": str(chat.uuid)}),
        data={
            "content": "Follow-up question",
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200
    assert rsp["Content-Type"] == "text/event-stream"

    # Read the streamed content
    chunks = rsp.stream_chunks()

    # Parse the streamed messages
    messages = [json.loads(line) for line in chunks if line]

    # Should only have the answer, no title message
    assert len(messages) == 1
    assert messages[0]["type"] == "ai/message"
    assert messages[0]["content"] == "Here's the answer to your follow-up question."

    # Verify no ChatTitleMessage was sent
    for msg in messages:
        assert msg["type"] != "chat/title"


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.assistant.handler.Assistant")
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_send_message_handles_ai_error_in_streaming(
    mock_handler_class, mock_assistant_class, api_client, enterprise_data_fixture
):
    """Test that AI errors are properly streamed to the client"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chat_uuid = str(uuid4())

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock chat creation
    mock_chat = MagicMock(spec=AssistantChat)
    mock_chat.uuid = chat_uuid
    mock_chat.workspace = workspace
    mock_chat.user = user
    mock_handler.get_or_create_chat.return_value = (mock_chat, True)

    # Mock the assistant
    mock_assistant = MagicMock()
    mock_handler.get_assistant.return_value = mock_assistant

    # Mock assistant that encounters an error during streaming
    async def mock_astream(human_message):
        # Start responding
        yield AiMessageChunk(content="Let me help you with that...")
        # Simulate an error (e.g., tool failure, timeout, etc.)
        yield AiErrorMessage(
            content="I encountered an error while processing your request. Please try again.",
            code="timeout",
        )

    mock_assistant.astream_messages = mock_astream

    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "Can you help me?",
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200
    assert rsp["Content-Type"] == "text/event-stream"

    # Read the streamed content
    chunks = rsp.stream_chunks()

    # Parse the streamed messages
    messages = [json.loads(line) for line in chunks if line]

    assert len(messages) == 2

    # First message is partial answer
    assert messages[0]["type"] == "ai/message"
    assert messages[0]["content"] == "Let me help you with that..."

    # Second message is the error
    assert messages[1]["type"] == "ai/error"
    assert messages[1]["code"] == "timeout"
    assert "error while processing your request" in messages[1]["content"].lower()


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.assistant.handler.Assistant")
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_send_message_with_minimal_ui_context(
    mock_handler_class, mock_assistant_class, api_client, enterprise_data_fixture
):
    """Test sending message with minimal UI context (workspace only)"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chat_uuid = str(uuid4())

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock chat creation
    mock_chat = MagicMock(spec=AssistantChat)
    mock_chat.uuid = chat_uuid
    mock_chat.workspace = workspace
    mock_chat.user = user
    mock_handler.get_or_create_chat.return_value = (mock_chat, True)

    # Mock the assistant
    mock_assistant = MagicMock()
    mock_handler.get_assistant.return_value = mock_assistant

    # Track what HumanMessage was passed to the assistant
    received_message = None

    async def mock_astream(human_message):
        nonlocal received_message
        received_message = human_message
        yield AiMessage(content="Response")

    mock_assistant.astream_messages = mock_astream

    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "Hello",
            "ui_context": {"workspace": {"id": workspace.id, "name": workspace.name}},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200

    # Consume the stream to trigger the async function
    chunks = rsp.stream_chunks()
    list(chunks)  # Force consumption

    # Verify the HumanMessage received has correct ui_context
    assert received_message is not None
    assert received_message.content == "Hello"
    assert received_message.ui_context.workspace.id == workspace.id
    assert received_message.ui_context.workspace.name == workspace.name
    assert received_message.ui_context.database is None
    assert received_message.ui_context.table is None
    assert received_message.ui_context.view is None


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.assistant.handler.Assistant")
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_send_message_with_database_builder_context(
    mock_handler_class, mock_assistant_class, api_client, enterprise_data_fixture
):
    """
    Test sending message with database builder context
    (workspace + database + table + view)
    """

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chat_uuid = str(uuid4())

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock chat creation
    mock_chat = MagicMock(spec=AssistantChat)
    mock_chat.uuid = chat_uuid
    mock_chat.workspace = workspace
    mock_chat.user = user
    mock_handler.get_or_create_chat.return_value = (mock_chat, True)

    # Mock the assistant
    mock_assistant = MagicMock()
    mock_handler.get_assistant.return_value = mock_assistant

    # Track what HumanMessage was passed to the assistant
    received_message = None

    async def mock_astream(human_message):
        nonlocal received_message
        received_message = human_message
        yield AiMessage(content="Response with database context")

    mock_assistant.astream_messages = mock_astream

    # Send message with full database builder context
    ui_context = {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "database": {"id": "123", "name": "My Database"},
        "table": {"id": 456, "name": "Customers"},
        "view": {"id": 789, "name": "All Customers", "type": "grid"},
    }

    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "How do I filter this view?",
            "ui_context": ui_context,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200

    # Consume the stream to trigger the async function
    chunks = rsp.stream_chunks()
    list(chunks)  # Force consumption

    # Verify the HumanMessage received has correct ui_context
    assert received_message is not None
    assert received_message.content == "How do I filter this view?"
    assert received_message.ui_context.workspace.id == workspace.id
    assert received_message.ui_context.database.id == "123"
    assert received_message.ui_context.database.name == "My Database"
    assert received_message.ui_context.table.id == 456
    assert received_message.ui_context.table.name == "Customers"
    assert received_message.ui_context.view.id == 789
    assert received_message.ui_context.view.name == "All Customers"
    assert received_message.ui_context.view.type == "grid"


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.assistant.handler.Assistant")
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_send_message_with_application_builder_context(
    mock_handler_class, mock_assistant_class, api_client, enterprise_data_fixture
):
    """
    Test sending message with application builder context
    (workspace + application + page)
    """

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chat_uuid = str(uuid4())

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock chat creation
    mock_chat = MagicMock(spec=AssistantChat)
    mock_chat.uuid = chat_uuid
    mock_chat.workspace = workspace
    mock_chat.user = user
    mock_handler.get_or_create_chat.return_value = (mock_chat, True)

    # Mock the assistant
    mock_assistant = MagicMock()
    mock_handler.get_assistant.return_value = mock_assistant

    # Track what HumanMessage was passed to the assistant
    received_message = None

    async def mock_astream(human_message):
        nonlocal received_message
        received_message = human_message
        yield AiMessage(content="Response with application context")

    mock_assistant.astream_messages = mock_astream

    # Send message with application builder context
    ui_context = {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "application": {"id": "app-123", "name": "My App"},
        "page": {"id": "page-456", "name": "Dashboard"},
    }

    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "How do I add a button to this page?",
            "ui_context": ui_context,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200

    # Consume the stream to trigger the async function
    chunks = rsp.stream_chunks()
    list(chunks)  # Force consumption

    # Verify the HumanMessage received has correct ui_context
    assert received_message is not None
    assert received_message.content == "How do I add a button to this page?"
    assert received_message.ui_context.workspace.id == workspace.id
    assert received_message.ui_context.application.id == "app-123"
    assert received_message.ui_context.application.name == "My App"
    assert received_message.ui_context.page.id == "page-456"
    assert received_message.ui_context.page.name == "Dashboard"
    assert received_message.ui_context.database is None
    assert received_message.ui_context.table is None


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_send_message_ui_context_validation_missing_workspace(
    api_client, enterprise_data_fixture
):
    """Test that UI context validation requires workspace"""

    user, token = enterprise_data_fixture.create_user_and_token()
    enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chat_uuid = str(uuid4())

    # Send message without workspace in ui_context
    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "Hello",
            "ui_context": {},  # Missing workspace
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 400
    assert "workspace" in str(rsp.json()).lower()


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.assistant.handler.Assistant")
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_send_message_with_automation_context(
    mock_handler_class, mock_assistant_class, api_client, enterprise_data_fixture
):
    """Test sending message with automation builder context"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chat_uuid = str(uuid4())

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock chat creation
    mock_chat = MagicMock(spec=AssistantChat)
    mock_chat.uuid = chat_uuid
    mock_chat.workspace = workspace
    mock_chat.user = user
    mock_handler.get_or_create_chat.return_value = (mock_chat, True)

    # Mock the assistant
    mock_assistant = MagicMock()
    mock_handler.get_assistant.return_value = mock_assistant

    # Track what HumanMessage was passed to the assistant
    received_message = None

    async def mock_astream(human_message):
        nonlocal received_message
        received_message = human_message
        yield AiMessage(content="Response with automation context")

    mock_assistant.astream_messages = mock_astream

    # Send message with automation context
    ui_context = {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "automation": {"id": "auto-123", "name": "Customer Automation"},
        "workflow": {"id": "wf-456", "name": "Send Email Workflow"},
    }

    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "How do I trigger this workflow?",
            "ui_context": ui_context,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200

    # Consume the stream to trigger the async function
    chunks = rsp.stream_chunks()
    list(chunks)  # Force consumption

    # Verify the HumanMessage received has correct ui_context
    assert received_message is not None
    assert received_message.ui_context.automation.id == "auto-123"
    assert received_message.ui_context.automation.name == "Customer Automation"
    assert received_message.ui_context.workflow.id == "wf-456"
    assert received_message.ui_context.workflow.name == "Send Email Workflow"


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.assistant.handler.Assistant")
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_send_message_with_dashboard_context(
    mock_handler_class, mock_assistant_class, api_client, enterprise_data_fixture
):
    """Test sending message with dashboard context"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chat_uuid = str(uuid4())

    # Mock the handler
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler

    # Mock chat creation
    mock_chat = MagicMock(spec=AssistantChat)
    mock_chat.uuid = chat_uuid
    mock_chat.workspace = workspace
    mock_chat.user = user
    mock_handler.get_or_create_chat.return_value = (mock_chat, True)

    # Mock the assistant
    mock_assistant = MagicMock()
    mock_handler.get_assistant.return_value = mock_assistant

    # Track what HumanMessage was passed to the assistant
    received_message = None

    async def mock_astream(human_message):
        nonlocal received_message
        received_message = human_message
        yield AiMessage(content="Response with dashboard context")

    mock_assistant.astream_messages = mock_astream

    # Send message with dashboard context
    ui_context = {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "dashboard": {"id": "dash-789", "name": "Sales Dashboard"},
    }

    rsp = api_client.post(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
        data={
            "content": "How do I add widgets to this dashboard?",
            "ui_context": ui_context,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200

    # Consume the stream to trigger the async function
    chunks = rsp.stream_chunks()
    list(chunks)  # Force consumption

    # Verify the HumanMessage received has correct ui_context
    assert received_message is not None
    assert received_message.ui_context.dashboard.id == "dash-789"
    assert received_message.ui_context.dashboard.name == "Sales Dashboard"
