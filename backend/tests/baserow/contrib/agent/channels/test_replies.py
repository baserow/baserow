from uuid import uuid4

from django.contrib.auth.models import AbstractUser

import pytest

from baserow.contrib.agent.constants import (
    TRIGGER_CONVERSATION_INSTRUCTIONS,
    UNATTENDED_REPLY_INSTRUCTIONS,
    VISITOR_CONVERSATION_INSTRUCTIONS,
)
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentChannel, AgentMessage
from baserow.contrib.agent.service import AgentService
from baserow.core.chat_runs.journal import ChatRunJournal
from baserow.core.chat_runs.models import ChatRun
from baserow.core.exceptions import PermissionDenied

from ..test_ask_person import turns
from ..test_replies import (
    add_row,
    allow_tools,
    decide,
    reply_state,
    respond,
    row_names,
    run_of,
)
from ..utils import run_reply


@pytest.fixture
def member(data_fixture) -> AbstractUser:
    return data_fixture.create_user()


@pytest.fixture
def channel(data_fixture, configured_agent, member) -> AgentChannel:
    return data_fixture.create_agent_channel(agent=configured_agent(user=member))


@pytest.mark.django_db
def test_a_channel_starts_a_shared_conversation_with_no_member_behind_it(channel):
    created = AgentHandler().start_channel_conversation(channel, "Hi")

    conversation = created.conversation
    assert (
        conversation.shared,
        conversation.owner_user_id,
        conversation.channel_id,
        conversation.started_by_channel,
    ) == (True, None, channel.id, True)
    assert [
        (message.role, message.unattended, message.sender_id)
        for message in (created.message, created.reply)
    ] == [("visitor", True, None), ("assistant", True, None)]
    assert ChatRun.objects.get(id=created.run_id).created_by_id is None


@pytest.mark.django_db
def test_a_visitor_reply_is_read_as_it_is_written_and_told_who_it_talks_to(
    channel, mocker
):
    received = respond(mocker)
    requested = mocker.spy(AgentHandler, "get_reply_request")

    created = AgentHandler().start_channel_conversation(channel, "Hi")
    run_reply(run_of(created.conversation))

    request = requested.spy_return
    assert (request.started_by_channel, request.unattended, request.may_ask_person) == (
        True,
        False,
        False,
    )
    assert reply_state(created.reply.id) == ("completed", "", "Done.")
    instructions = received[-1][-1].instructions
    assert VISITOR_CONVERSATION_INSTRUCTIONS in instructions
    assert TRIGGER_CONVERSATION_INSTRUCTIONS not in instructions
    assert UNATTENDED_REPLY_INSTRUCTIONS.format(trigger="A trigger") not in (
        instructions
    )


@pytest.mark.django_db
@pytest.mark.parametrize("can_call_tools", [True, False])
def test_a_visitor_reply_that_can_call_tools_streams_no_text(
    data_fixture, channel, mocker, can_call_tools
):
    if can_call_tools:
        allow_tools(data_fixture, channel.agent)
    respond(mocker)
    streamed = mocker.spy(ChatRunJournal, "emit_text")

    created = AgentHandler().start_channel_conversation(channel, "Hi")
    run_reply(run_of(created.conversation))

    assert bool(streamed.call_count) is not can_call_tools
    assert reply_state(created.reply.id) == ("completed", "", "Done.")


@pytest.mark.django_db
@pytest.mark.parametrize("change", ["disable", "trash", "delete"])
def test_a_visitor_reply_stops_once_its_channel_is_off(channel, change):
    conversation = AgentHandler().start_channel_conversation(channel, "Hi").conversation
    if change == "disable":
        channel.enabled = False
        channel.save(update_fields=["enabled"])
    elif change == "trash":
        channel.trashed = True
        channel.save(update_fields=["trashed"])
    else:
        channel.delete()

    run_reply(run_of(conversation))

    reply = AgentMessage.objects.get(conversation=conversation, role="assistant")
    assert reply_state(reply.id) == ("failed", "channel_off", "")


@pytest.mark.django_db
def test_a_visitor_message_stays_a_prompt_in_the_next_reply(channel, mocker):
    received = respond(mocker)
    handler = AgentHandler()
    conversation = handler.start_channel_conversation(channel, "Hi").conversation
    run_reply(run_of(conversation))

    created = handler.create_visitor_message(conversation, "And now?")
    run_reply(ChatRun.objects.get(id=created.run_id))

    assert turns(received[-1]) == [
        ("user-prompt", "Hi"),
        ("text", "Done."),
        ("user-prompt", "And now?"),
    ]


@pytest.mark.django_db
def test_a_member_cannot_write_in_a_channel_conversation(data_fixture, channel, member):
    conversation = data_fixture.create_channel_conversation(channel=channel)

    with pytest.raises(PermissionDenied):
        AgentService().create_message(
            member, channel.agent_id, conversation.uuid, uuid4(), "Hi"
        )

    assert not conversation.messages.exists()


@pytest.mark.django_db
def test_a_member_decides_a_held_call_and_the_visitor_reply_resumes(
    data_fixture, channel, member, mocker
):
    table = allow_tools(data_fixture, channel.agent, ask_first=("create_rows",))
    respond(mocker, ({0: add_row(table)},))
    created = AgentHandler().start_channel_conversation(channel, "Add a plan")
    run_reply(run_of(created.conversation))
    assert reply_state(created.reply.id) == ("waiting", "", "")

    run = decide(member, created.reply, approved=True)
    run_reply(run)

    assert reply_state(created.reply.id) == ("completed", "", "Done.")
    assert row_names(table) == ["Plan"]
    assert run.created_by_id is None
