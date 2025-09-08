import json
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
    ChatTitleMessage,
    HumanMessage,
    UIContext,
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
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_send_message_creates_chat_if_not_exists(
    mock_handler_class, api_client, enterprise_data_fixture
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

    async def mock_astream(chat, new_message):
        # Simulate AI response messages
        yield AiMessage(content="Hello! How can I help you today?")

    mock_handler.stream_assistant_messages = mock_astream

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
    assert ai_response["id"] is not None
    assert ai_response["role"] == "ai"
    assert ai_response["type"] == "ai/message"
    assert ai_response["content"] == "Hello! How can I help you today?"

    # Verify handler was called correctly
    mock_handler.get_or_create_chat.assert_called_once_with(user, workspace, chat_uuid)


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.api.assistant.views.AssistantHandler")
def test_send_message_streams_response(
    mock_handler_class, api_client, enterprise_data_fixture
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

    # Mock assistant with async generator for streaming
    response_messages = [
        AiMessage(content="I'm thinking..."),
        AiMessage(content="Here's my response!"),
        ChatTitleMessage(content="Chat about AI assistance"),
    ]

    async def mock_astream(chat, new_message):
        for msg in response_messages:
            yield msg

    mock_handler.stream_assistant_messages = mock_astream

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
    assert messages[0]["role"] == "ai"
    assert messages[0]["type"] == "ai/message"

    # Check second message
    assert messages[1]["content"] == "Here's my response!"
    assert messages[1]["role"] == "ai"
    assert messages[1]["type"] == "ai/message"

    # Check title update message
    assert messages[2]["content"] == "Chat about AI assistance"
    assert messages[2]["role"] == "ai"
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

    # Mock message history
    message_history = [
        HumanMessage(
            content="What's the weather like?",
            ui_context=UIContext(
                workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name)
            ),
        ),
        AiMessage(
            content="I don't have access to real-time weather data.",
        ),
        HumanMessage(
            content="Can you help me with Python?",
            ui_context=UIContext(
                workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name)
            ),
        ),
        AiMessage(
            content="Of course! I'd be happy to help you with Python.",
        ),
    ]
    mock_handler.get_chat_messages.return_value = message_history

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
    assert data["messages"][0]["role"] == "human"
    assert "id" in data["messages"][0]

    # Check second message (AI)
    assert (
        data["messages"][1]["content"]
        == "I don't have access to real-time weather data."
    )
    assert data["messages"][1]["role"] == "ai"
    assert data["messages"][1]["type"] == "ai/message"

    # Check third message (human)
    assert data["messages"][2]["content"] == "Can you help me with Python?"
    assert data["messages"][2]["role"] == "human"

    # Check fourth message (AI)
    assert (
        data["messages"][3]["content"]
        == "Of course! I'd be happy to help you with Python."
    )
    assert data["messages"][3]["role"] == "ai"

    # Verify handler was called correctly
    mock_handler.get_chat.assert_called_once_with(user, chat.uuid)
    mock_handler.get_chat_messages.assert_called_once_with(chat)


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

    # Mock message history with different types
    message_history = [
        HumanMessage(
            content="Hello",
            ui_context=UIContext(
                workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name)
            ),
        ),
        AiErrorMessage(content="Something went wrong", code="unknown"),
        ChatTitleMessage(content="New Chat Title"),
    ]
    mock_handler.get_chat_messages.return_value = message_history

    rsp = api_client.get(
        reverse(
            "assistant:chat_messages",
            kwargs={"chat_uuid": str(chat.uuid)},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200
    data = rsp.json()

    assert len(data["messages"]) == 3

    # Check error message
    assert data["messages"][1]["content"] == "Something went wrong"
    assert data["messages"][1]["type"] == "ai/error"

    # Check title message
    assert data["messages"][2]["content"] == "New Chat Title"
    assert data["messages"][2]["type"] == "chat/title"
