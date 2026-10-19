from unittest.mock import patch
from uuid import uuid4

from django.db import DEFAULT_DB_ALIAS
from django.test import override_settings
from django.urls import reverse

import pytest
from freezegun import freeze_time

from baserow.test_utils.helpers import AnyStr
from baserow_enterprise.assistant.models import (
    AssistantChat,
    AssistantChatMessage,
    AssistantChatPrediction,
)
from baserow_enterprise.assistant.types import (
    AiMessage,
    HumanMessage,
    UIContext,
    UserUIContext,
    WorkspaceUIContext,
)


@pytest.fixture(autouse=True)
def no_feature_flags(settings):
    """Kuma API behavior does not require feature flags."""

    settings.FEATURE_FLAGS = []


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
        created_chats = AssistantChat.objects.bulk_create(chats)
        messages = [
            AssistantChatMessage(
                role=AssistantChatMessage.Role.HUMAN,
                content="What's the weather like?",
                chat=chat,
            )
            for chat in created_chats
        ]
    AssistantChatMessage.objects.bulk_create(messages)

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
            "chat_id": created_chats[i].id,
            "user_id": user.id,
            "workspace_id": workspace.id,
            "title": f"Chat {i}",
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
        "chat_id": created_chats[2].id,
        "user_id": user.id,
        "workspace_id": workspace.id,
        "title": "Chat 2",
        "created_on": "2024-01-14T12:00:00Z",
        "updated_on": "2024-01-14T12:00:00Z",
    }
    assert data["previous"] is not None
    assert data["next"] is not None


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_not_list_empty_assistant_chats(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chats = [
        AssistantChat(workspace=workspace, user=user, title=""),
        AssistantChat(workspace=workspace, user=user, title="test"),
        AssistantChat(workspace=workspace, user=user, title="test2"),
    ]
    chats = AssistantChat.objects.bulk_create(chats)

    messages = [
        AssistantChatMessage(
            id=1,
            role=AssistantChatMessage.Role.HUMAN,
            content="What's the weather like?",
            chat=chats[0],
        ),
        AssistantChatMessage(
            id=2,
            role=AssistantChatMessage.Role.HUMAN,
            content="What's the weather like?",
            chat=chats[2],
        ),
    ]
    AssistantChatMessage.objects.bulk_create(messages)

    rsp = api_client.get(
        reverse("assistant:list") + f"?workspace_id={workspace.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == 200
    data = rsp.json()
    assert data["count"] == 1
    assert len(data["results"]) == 1
    # The first chat does not have a title, and the second one does not have any
    # messages. They should therefore both be excluded.
    assert data["results"][0]["uuid"] == str(chats[2].uuid)


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
    with patch(
        "baserow_enterprise.api.assistant.views.set_db_alias"
    ) as mock_set_db_alias:
        rsp = api_client.post(
            reverse("assistant:chat_messages", kwargs={"chat_uuid": chat_uuid}),
            data={
                "content": "Hello AI",
                "ui_context": {
                    "workspace": {"id": workspace.id, "name": workspace.name}
                },
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    mock_set_db_alias.assert_called_once_with(DEFAULT_DB_ALIAS)
    assert rsp.status_code == 400
    assert rsp.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_enterprise.api.assistant.views.check_lm_ready_or_raise")
@patch("baserow_enterprise.api.assistant.views.resolve_assistant_model")
def test_cannot_reuse_chat_uuid_from_another_workspace(
    mock_resolve_model,
    mock_check_lm,
    api_client,
    enterprise_data_fixture,
    enable_enterprise,
):
    user, token = enterprise_data_fixture.create_user_and_token()
    chat_workspace = enterprise_data_fixture.create_workspace(user=user)
    requested_workspace = enterprise_data_fixture.create_workspace(user=user)
    chat = AssistantChat.objects.create(user=user, workspace=chat_workspace)
    url = reverse("assistant:chat_messages", kwargs={"chat_uuid": chat.uuid})
    request_data = {
        "content": "Hello AI",
        "ui_context": {
            "workspace": {
                "id": requested_workspace.id,
                "name": requested_workspace.name,
            }
        },
    }

    response = api_client.post(
        url,
        data=request_data,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 404
    assert response.json()["error"] == "ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST"
    mock_resolve_model.assert_not_called()
    mock_check_lm.assert_not_called()
    assert not AssistantChatMessage.objects.filter(chat=chat).exists()

    chat_workspace.workspaceuser_set.get(user=user).delete()
    response = api_client.post(
        url,
        data=request_data,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 404
    assert response.json()["error"] == "ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST"
    mock_resolve_model.assert_not_called()
    mock_check_lm.assert_not_called()
    assert not AssistantChatMessage.objects.filter(chat=chat).exists()


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
def test_get_messages_returns_chat_history(api_client, enterprise_data_fixture):
    """Test that the endpoint returns the chat message history"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create a chat
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )

    # Mock message history - only HumanMessage and AiMessage are returned
    message_history = [
        AssistantChatMessage(
            id=1,
            role=AssistantChatMessage.Role.HUMAN,
            content="What's the weather like?",
            chat=chat,
        ),
        AssistantChatMessage(
            id=2,
            role=AssistantChatMessage.Role.AI,
            content="I don't have access to real-time weather data.",
            chat=chat,
        ),
        AssistantChatMessage(
            id=3,
            role=AssistantChatMessage.Role.HUMAN,
            content="Can you help me with Baserow?",
            chat=chat,
        ),
        AssistantChatMessage(
            id=4,
            role=AssistantChatMessage.Role.AI,
            content="Of course! I'd be happy to help you with Baserow.",
            chat=chat,
        ),
    ]
    AssistantChatMessage.objects.bulk_create(message_history)

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


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_messages_returns_empty_list_for_new_chat(
    api_client, enterprise_data_fixture
):
    """Test that the endpoint returns an empty list for a chat with no messages"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create a chat
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Empty Chat"
    )

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
def test_get_messages_with_different_message_types(api_client, enterprise_data_fixture):
    """Test that the endpoint correctly handles different message types"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create a chat
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )

    # Mock message history - only HumanMessage and AiMessage are returned
    message_history = [
        AssistantChatMessage(
            id=1, role=AssistantChatMessage.Role.HUMAN, content="Hello", chat=chat
        ),
        AssistantChatMessage(
            id=2,
            role=AssistantChatMessage.Role.AI,
            content="Hi there! How can I help you?",
            chat=chat,
        ),
        AssistantChatMessage(
            id=3,
            role=AssistantChatMessage.Role.HUMAN,
            content="Tell me about Baserow",
            chat=chat,
        ),
        AssistantChatMessage(
            id=4,
            role=AssistantChatMessage.Role.AI,
            content="Baserow is an open-source no-code database platform.",
            chat=chat,
        ),
    ]
    AssistantChatMessage.objects.bulk_create(message_history)

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
def test_get_messages_includes_can_submit_feedback_field(
    api_client, enterprise_data_fixture
):
    """
    Test that AI messages include can_submit_feedback field based on prediction state
    """

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create a chat with messages
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )

    # Create human message
    human_message_1 = AssistantChatMessage.objects.create(
        chat=chat,
        role=AssistantChatMessage.Role.HUMAN,
        content="First question",
    )

    # Create AI message WITH prediction (no feedback yet)
    ai_message_1 = AssistantChatMessage.objects.create(
        chat=chat,
        role=AssistantChatMessage.Role.AI,
        content="First answer",
    )
    AssistantChatPrediction.objects.create(
        human_message=human_message_1,
        ai_response=ai_message_1,
        prediction={"reasoning": "test"},
    )

    # Create second human message
    human_message_2 = AssistantChatMessage.objects.create(
        chat=chat,
        role=AssistantChatMessage.Role.HUMAN,
        content="Second question",
    )

    # Create AI message WITHOUT prediction
    ai_message_2 = AssistantChatMessage.objects.create(
        chat=chat,
        role=AssistantChatMessage.Role.AI,
        content="Second answer",
    )

    # Create third human message
    human_message_3 = AssistantChatMessage.objects.create(
        chat=chat,
        role=AssistantChatMessage.Role.HUMAN,
        content="Third question",
    )

    # Create AI message WITH prediction AND existing feedback
    ai_message_3 = AssistantChatMessage.objects.create(
        chat=chat,
        role=AssistantChatMessage.Role.AI,
        content="Third answer",
    )
    AssistantChatPrediction.objects.create(
        human_message=human_message_3,
        ai_response=ai_message_3,
        prediction={"reasoning": "test"},
        human_sentiment=1,  # Already has feedback
        human_feedback="Great answer",
    )

    rsp = api_client.get(
        reverse(
            "assistant:chat_messages",
            kwargs={"chat_uuid": str(chat.uuid)},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200
    data = rsp.json()

    assert len(data["messages"]) == 6

    assert data["messages"][0]["type"] == "human"
    assert "can_submit_feedback" not in data["messages"][0]
    assert "human_sentiment" not in data["messages"][0]

    # First AI message: has prediction, no feedback yet -> can submit
    assert data["messages"][1]["type"] == "ai/message"
    assert data["messages"][1]["can_submit_feedback"] is True
    assert data["messages"][1]["human_sentiment"] is None

    assert data["messages"][2]["type"] == "human"
    assert "can_submit_feedback" not in data["messages"][2]
    assert "human_sentiment" not in data["messages"][2]

    # Second AI message: no prediction -> cannot submit
    assert data["messages"][3]["type"] == "ai/message"
    assert data["messages"][3]["can_submit_feedback"] is False
    assert data["messages"][3]["human_sentiment"] is None

    assert data["messages"][4]["type"] == "human"
    assert "can_submit_feedback" not in data["messages"][4]
    assert "human_sentiment" not in data["messages"][4]

    # Third AI message: has prediction with existing feedback
    assert data["messages"][5]["type"] == "ai/message"
    assert data["messages"][5]["can_submit_feedback"] is True
    assert data["messages"][5]["human_sentiment"] == "LIKE"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_messages_includes_human_sentiment_when_feedback_exists(
    api_client, enterprise_data_fixture
):
    """Test that human_sentiment is included in AI messages when feedback exists"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create a chat
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )

    # Create messages with LIKE feedback
    human_message_1 = AssistantChatMessage.objects.create(
        chat=chat,
        role=AssistantChatMessage.Role.HUMAN,
        content="Question 1",
    )
    ai_message_1 = AssistantChatMessage.objects.create(
        chat=chat,
        role=AssistantChatMessage.Role.AI,
        content="Answer 1",
    )
    AssistantChatPrediction.objects.create(
        human_message=human_message_1,
        ai_response=ai_message_1,
        prediction={"reasoning": "test"},
        human_sentiment=1,  # LIKE
        human_feedback="Very helpful",
    )

    # Create messages with DISLIKE feedback
    human_message_2 = AssistantChatMessage.objects.create(
        chat=chat,
        role=AssistantChatMessage.Role.HUMAN,
        content="Question 2",
    )
    ai_message_2 = AssistantChatMessage.objects.create(
        chat=chat,
        role=AssistantChatMessage.Role.AI,
        content="Answer 2",
    )
    AssistantChatPrediction.objects.create(
        human_message=human_message_2,
        ai_response=ai_message_2,
        prediction={"reasoning": "test"},
        human_sentiment=-1,  # DISLIKE
        human_feedback="Not accurate",
    )

    message_history = [
        HumanMessage(
            id=human_message_1.id,
            content="Question 1",
            ui_context=UIContext(
                workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
                user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
            ),
        ),
        AiMessage(
            id=ai_message_1.id,
            content="Answer 1",
            can_submit_feedback=False,
            human_sentiment="LIKE",
        ),
        HumanMessage(
            id=human_message_2.id,
            content="Question 2",
            ui_context=UIContext(
                workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
                user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
            ),
        ),
        AiMessage(
            id=ai_message_2.id,
            content="Answer 2",
            can_submit_feedback=False,
            human_sentiment="DISLIKE",
        ),
    ]

    rsp = api_client.get(
        reverse(
            "assistant:chat_messages",
            kwargs={"chat_uuid": str(chat.uuid)},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 200
    data = rsp.json()

    # First AI message: LIKE sentiment
    assert data["messages"][1]["type"] == "ai/message"
    assert data["messages"][1]["human_sentiment"] == "LIKE"
    assert data["messages"][1]["can_submit_feedback"] is True

    # Second AI message: DISLIKE sentiment
    assert data["messages"][3]["type"] == "ai/message"
    assert data["messages"][3]["human_sentiment"] == "DISLIKE"
    assert data["messages"][3]["can_submit_feedback"] is True


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


# =============================================================================
# Tests for AssistantChatMessageFeedbackView
# =============================================================================


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_submit_feedback_with_like_sentiment(api_client, enterprise_data_fixture):
    """Test submitting positive feedback (LIKE) for a message"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create a chat with messages and prediction
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )

    # Create human message
    human_message = AssistantChatMessage.objects.create(
        chat=chat,
        role=AssistantChatMessage.Role.HUMAN,
        content="Hello",
    )

    # Create AI message
    ai_message = AssistantChatMessage.objects.create(
        chat=chat,
        role=AssistantChatMessage.Role.AI,
        content="Hi there!",
    )

    # Create prediction
    prediction = AssistantChatPrediction.objects.create(
        human_message=human_message,
        ai_response=ai_message,
        prediction={"reasoning": "test"},
    )

    # Submit feedback
    rsp = api_client.put(
        reverse("assistant:message_feedback", kwargs={"message_id": ai_message.id}),
        data={"sentiment": "LIKE"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 204

    # Verify feedback was saved
    prediction.refresh_from_db()
    assert prediction.human_sentiment == 1  # LIKE = 1
    assert prediction.human_feedback == ""


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_submit_feedback_with_dislike_sentiment_and_text(
    api_client, enterprise_data_fixture
):
    """Test submitting negative feedback (DISLIKE) with feedback text"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create chat and messages
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )
    human_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Question"
    )
    ai_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.AI, content="Answer"
    )
    prediction = AssistantChatPrediction.objects.create(
        human_message=human_message,
        ai_response=ai_message,
        prediction={"reasoning": "test"},
    )

    # Submit negative feedback with text
    feedback_text = "The answer was not helpful"
    rsp = api_client.put(
        reverse("assistant:message_feedback", kwargs={"message_id": ai_message.id}),
        data={"sentiment": "DISLIKE", "feedback": feedback_text},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 204

    # Verify feedback was saved
    prediction.refresh_from_db()
    assert prediction.human_sentiment == -1  # DISLIKE = -1
    assert prediction.human_feedback == feedback_text


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_existing_feedback(api_client, enterprise_data_fixture):
    """Test updating feedback that was already submitted"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create chat and messages with existing feedback
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )
    human_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Question"
    )
    ai_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.AI, content="Answer"
    )
    prediction = AssistantChatPrediction.objects.create(
        human_message=human_message,
        ai_response=ai_message,
        prediction={"reasoning": "test"},
        human_sentiment=1,  # Initially LIKE
        human_feedback="Was helpful",
    )

    # Update to DISLIKE with new feedback
    new_feedback = "Actually, it wasn't accurate"
    rsp = api_client.put(
        reverse("assistant:message_feedback", kwargs={"message_id": ai_message.id}),
        data={"sentiment": "DISLIKE", "feedback": new_feedback},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 204

    # Verify feedback was updated
    prediction.refresh_from_db()
    assert prediction.human_sentiment == -1  # Changed to DISLIKE
    assert prediction.human_feedback == new_feedback


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_submit_feedback_with_null_sentiment(api_client, enterprise_data_fixture):
    """Test clearing/removing feedback by setting sentiment to null"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create chat and messages with existing feedback
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )
    human_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Question"
    )
    ai_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.AI, content="Answer"
    )
    prediction = AssistantChatPrediction.objects.create(
        human_message=human_message,
        ai_response=ai_message,
        prediction={"reasoning": "test"},
        human_sentiment=1,
        human_feedback="Was helpful",
    )

    # Clear feedback by sending null sentiment
    rsp = api_client.put(
        reverse("assistant:message_feedback", kwargs={"message_id": ai_message.id}),
        data={"sentiment": None},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 204

    # Verify feedback was cleared
    prediction.refresh_from_db()
    assert prediction.human_sentiment is None
    assert prediction.human_feedback == ""


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_submit_feedback_for_message_without_prediction(
    api_client, enterprise_data_fixture
):
    """Test that submitting feedback fails if message has no prediction"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create chat and AI message WITHOUT prediction
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )
    ai_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.AI, content="Answer"
    )

    # Try to submit feedback
    rsp = api_client.put(
        reverse("assistant:message_feedback", kwargs={"message_id": ai_message.id}),
        data={"sentiment": "LIKE"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 400
    assert rsp.json()["error"] == "ERROR_CANNOT_SUBMIT_MESSAGE_FEEDBACK"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_submit_feedback_for_nonexistent_message(
    api_client, enterprise_data_fixture
):
    """Test that submitting feedback fails for non-existent message"""

    _, token = enterprise_data_fixture.create_user_and_token()
    enterprise_data_fixture.enable_enterprise()

    # Try to submit feedback for non-existent message
    rsp = api_client.put(
        reverse("assistant:message_feedback", kwargs={"message_id": 999999}),
        data={"sentiment": "LIKE"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 404
    assert rsp.json()["error"] == "ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_submit_feedback_for_another_users_message(
    api_client, enterprise_data_fixture
):
    """Test that users cannot submit feedback on other users' messages"""

    user1, _ = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(members=[user1, user2])
    enterprise_data_fixture.enable_enterprise()

    # Create chat and message for user1
    chat = AssistantChat.objects.create(
        user=user1, workspace=workspace, title="User1's Chat"
    )
    human_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Question"
    )
    ai_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.AI, content="Answer"
    )
    AssistantChatPrediction.objects.create(
        human_message=human_message,
        ai_response=ai_message,
        prediction={"reasoning": "test"},
    )

    # Try to submit feedback as user2
    rsp = api_client.put(
        reverse("assistant:message_feedback", kwargs={"message_id": ai_message.id}),
        data={"sentiment": "LIKE"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )

    assert rsp.status_code == 404
    assert rsp.json()["error"] == "ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_submit_feedback_validates_sentiment_choice(
    api_client, enterprise_data_fixture
):
    """Test that feedback endpoint validates sentiment choices"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create chat and messages
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )
    human_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Question"
    )
    ai_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.AI, content="Answer"
    )
    AssistantChatPrediction.objects.create(
        human_message=human_message,
        ai_response=ai_message,
        prediction={"reasoning": "test"},
    )

    # Try to submit with invalid sentiment
    rsp = api_client.put(
        reverse("assistant:message_feedback", kwargs={"message_id": ai_message.id}),
        data={"sentiment": "INVALID"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 400
    assert "sentiment" in str(rsp.json()).lower()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_submit_feedback_requires_sentiment_field(api_client, enterprise_data_fixture):
    """Test that feedback endpoint requires sentiment field"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create chat and messages
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )
    human_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Question"
    )
    ai_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.AI, content="Answer"
    )
    AssistantChatPrediction.objects.create(
        human_message=human_message,
        ai_response=ai_message,
        prediction={"reasoning": "test"},
    )

    # Try to submit without sentiment field
    rsp = api_client.put(
        reverse("assistant:message_feedback", kwargs={"message_id": ai_message.id}),
        data={"feedback": "Just some feedback"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 400
    assert "sentiment" in str(rsp.json()).lower()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_submit_feedback_without_feedback_text(api_client, enterprise_data_fixture):
    """Test that feedback text is optional"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create chat and messages
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )
    human_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Question"
    )
    ai_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.AI, content="Answer"
    )
    prediction = AssistantChatPrediction.objects.create(
        human_message=human_message,
        ai_response=ai_message,
        prediction={"reasoning": "test"},
    )

    # Submit feedback without text (only sentiment)
    rsp = api_client.put(
        reverse("assistant:message_feedback", kwargs={"message_id": ai_message.id}),
        data={"sentiment": "DISLIKE"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 204

    # Verify feedback was saved without text
    prediction.refresh_from_db()
    assert prediction.human_sentiment == -1
    assert prediction.human_feedback == ""


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_submit_feedback_with_empty_feedback_text(api_client, enterprise_data_fixture):
    """Test that empty feedback text is stored as empty string"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create chat and messages
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )
    human_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Question"
    )
    ai_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.AI, content="Answer"
    )
    prediction = AssistantChatPrediction.objects.create(
        human_message=human_message,
        ai_response=ai_message,
        prediction={"reasoning": "test"},
    )

    # Submit with empty feedback string
    rsp = api_client.put(
        reverse("assistant:message_feedback", kwargs={"message_id": ai_message.id}),
        data={"sentiment": "LIKE", "feedback": ""},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 204

    # Verify empty string is stored
    prediction.refresh_from_db()
    assert prediction.human_sentiment == 1
    assert prediction.human_feedback == ""


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_submit_feedback_toggles_sentiment_from_like_to_dislike(
    api_client, enterprise_data_fixture
):
    """Test changing sentiment from LIKE to DISLIKE"""

    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    # Create chat and messages
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )
    human_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Question"
    )
    ai_message = AssistantChatMessage.objects.create(
        chat=chat, role=AssistantChatMessage.Role.AI, content="Answer"
    )
    prediction = AssistantChatPrediction.objects.create(
        human_message=human_message,
        ai_response=ai_message,
        prediction={"reasoning": "test"},
        human_sentiment=1,  # Start with LIKE
    )

    # Change to DISLIKE
    rsp = api_client.put(
        reverse("assistant:message_feedback", kwargs={"message_id": ai_message.id}),
        data={"sentiment": "DISLIKE", "feedback": "Changed my mind"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 204

    # Verify change
    prediction.refresh_from_db()
    assert prediction.human_sentiment == -1
    assert prediction.human_feedback == "Changed my mind"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cancel_message_requires_auth(api_client, enterprise_data_fixture):
    """Test that cancel endpoint requires authentication"""

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.enable_enterprise()

    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )

    # Call without auth
    rsp = api_client.delete(
        reverse("assistant:cancel_message", kwargs={"chat_uuid": chat.uuid}),
    )

    assert rsp.status_code == 401


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cancel_message_requires_workspace_access(api_client, enterprise_data_fixture):
    """Test that user must have access to workspace"""

    user, token = enterprise_data_fixture.create_user_and_token()
    other_user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=other_user)
    enterprise_data_fixture.enable_enterprise()

    chat = AssistantChat.objects.create(
        user=other_user, workspace=workspace, title="Test Chat"
    )

    rsp = api_client.delete(
        reverse("assistant:cancel_message", kwargs={"chat_uuid": chat.uuid}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == 404
    assert rsp.json()["error"] == "ERROR_ASSISTANT_CHAT_DOES_NOT_EXIST"
