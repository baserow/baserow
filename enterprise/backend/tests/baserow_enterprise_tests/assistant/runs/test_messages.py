from django.urls import reverse

import pytest

from baserow.test_utils.helpers import AnyStr
from baserow_enterprise.assistant.assistant import assistant_message_payload
from baserow_enterprise.assistant.models import (
    AssistantChat,
    AssistantChatMessage,
    AssistantChatPrediction,
)


@pytest.mark.django_db
def test_a_reloaded_chat_shows_how_each_answer_ended(
    api_client, enterprise_data_fixture, enable_enterprise
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    chat = AssistantChat.objects.create(user=user, workspace=workspace)
    human = chat.messages.create(role=AssistantChatMessage.Role.HUMAN, content="Hi")
    stopped = chat.messages.create(
        role=AssistantChatMessage.Role.AI,
        content="Partial",
        artifacts={
            "sources": ["https://baserow.io/docs"],
            "run": {"status": "failed", "error_code": "interrupted"},
        },
    )
    AssistantChatPrediction.objects.create(human_message=human, ai_response=stopped)
    chat.messages.create(role=AssistantChatMessage.Role.AI, content="Done")

    response = api_client.get(
        reverse("assistant:chat_messages", kwargs={"chat_uuid": chat.uuid}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    saved = chat.messages.select_related("prediction").order_by("id")
    messages = response.json()["messages"]
    assert messages == [assistant_message_payload(message) for message in saved]
    assert messages[1] == {
        "id": stopped.id,
        "type": "ai/message",
        "content": "Partial",
        "timestamp": AnyStr(),
        "sources": ["https://baserow.io/docs"],
        "can_submit_feedback": True,
        "human_sentiment": None,
        "run_status": "failed",
        "error_code": "interrupted",
    }
    assert (messages[2]["run_status"], messages[2]["error_code"]) == (None, None)
