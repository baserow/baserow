from functools import partial
from unittest.mock import call
from uuid import UUID, uuid4

from django.db import transaction

import pytest
from rest_framework.fields import DateTimeField

from baserow.contrib.agent.actions import (
    CreateAgentConversationActionType,
    CreateAgentMessageActionType,
)
from baserow.contrib.agent.models import AgentConversation, AgentMessage


def conversation_write(data_fixture, user, agent, kind):
    if kind == "message":
        conversation = data_fixture.create_agent_conversation(user=user, agent=agent)
        return partial(
            CreateAgentMessageActionType.do,
            user,
            agent.id,
            conversation.uuid,
            uuid4(),
            "PRIVATE MESSAGE",
        )
    return partial(
        CreateAgentConversationActionType.do,
        user,
        agent.id,
        uuid4(),
        uuid4(),
        "PRIVATE MESSAGE",
    )


def update_of(conversation: AgentConversation, run_id: UUID | None = None) -> dict:
    return {
        "type": "agent_conversation_updated",
        "agent_id": conversation.agent_id,
        "conversation_uuid": str(conversation.uuid),
        "run_id": str(run_id) if run_id else None,
        "updated_on": DateTimeField().to_representation(conversation.updated_on),
    }


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["conversation", "message"])
def test_a_reply_start_and_end_notify_only_the_owner_after_commit_and_not_on_retry(
    data_fixture, configured_agent, mocker, django_capture_on_commit_callbacks, kind
):
    user = data_fixture.create_user(web_socket_id="source-tab")
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[other_user])
    agent = configured_agent(workspace=workspace)
    write = conversation_write(data_fixture, user, agent, kind)
    broadcast = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_to_users.delay"
    )

    with django_capture_on_commit_callbacks(execute=True):
        result = write()
        broadcast.assert_not_called()

    # The sending tab has the start from its response; every tab needs the end.
    ended = AgentConversation.objects.get(id=result.conversation.id)
    assert broadcast.call_args_list == [
        call(
            [user.id],
            update_of(result.conversation, result.run_id),
            ignore_web_socket_id="source-tab",
        ),
        call([user.id], update_of(ended), ignore_web_socket_id=None),
    ]

    with django_capture_on_commit_callbacks(execute=True):
        retried = write()

    assert retried.message.id == result.message.id
    assert not retried.created
    assert broadcast.call_count == 2


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["conversation", "message"])
def test_rolled_back_content_does_not_notify_other_sessions(
    data_fixture, configured_agent, mocker, django_capture_on_commit_callbacks, kind
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    write = conversation_write(data_fixture, user, agent, kind)
    broadcast = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_to_users.delay"
    )

    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError):
            with transaction.atomic():
                write()
                raise RuntimeError("Abort the outer transaction")

    assert not AgentMessage.objects.exists()
    broadcast.assert_not_called()
