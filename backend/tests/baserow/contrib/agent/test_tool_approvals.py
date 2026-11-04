from uuid import uuid4

from django.test import override_settings

import pytest
from rest_framework.response import Response
from rest_framework.test import APIClient

from baserow.contrib.agent.actions import DecideAgentToolApprovalsActionType
from baserow.contrib.agent.models import (
    AgentMessage,
    AgentReplyStatus,
    AgentToolApproval,
)
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun, ChatRunStatus

from .utils import agent_url, new_conversation


def test_reply_statuses_are_run_statuses_plus_waiting():
    assert AgentReplyStatus.values == [*ChatRunStatus.values, "waiting"]


@pytest.fixture
def held_reply(data_fixture, configured_agent, api_user) -> AgentMessage:
    """A reply in the API user's conversation, holding a create and an update."""

    agent = configured_agent(user=api_user)
    conversation = data_fixture.create_agent_conversation(user=api_user, agent=agent)
    data_fixture.create_agent_message(conversation=conversation, content="Add a row")
    reply = data_fixture.create_agent_message(
        conversation=conversation,
        role=AgentMessage.Role.ASSISTANT,
        status=AgentReplyStatus.WAITING,
        content="",
    )
    for tool_name in ("create_rows", "update_rows"):
        data_fixture.create_agent_tool_approval(reply=reply, tool_name=tool_name)
    return reply


def decide(api_client: APIClient, reply: AgentMessage, *decisions: dict) -> Response:
    conversation = reply.conversation
    url = agent_url(
        conversation.agent, "approvals", conversation_uuid=conversation.uuid
    )
    return api_client.post(url, {"decisions": list(decisions)})


def statuses(reply: AgentMessage) -> tuple[str, list[str]]:
    reply.refresh_from_db()
    return reply.status, [approval.status for approval in reply.approvals.all()]


@pytest.mark.django_db
def test_the_last_decision_resumes_the_reply_and_each_is_audited_by_tool(
    api_client, api_user, held_reply, mocker
):
    created, updated = held_reply.approvals.all()
    conversation = held_reply.conversation
    audited = mocker.spy(DecideAgentToolApprovalsActionType, "send_action_done_signal")

    partial = decide(api_client, held_reply, {"id": created.id, "approved": True})

    assert (partial.status_code, partial.json()["run_id"]) == (200, None)
    assert statuses(held_reply) == ("waiting", ["approved", "pending"])
    assert not ChatRun.objects.exists()

    last = decide(
        api_client,
        held_reply,
        {"id": updated.id, "approved": False, "reason": "Wrong row"},
    )

    run = ChatRun.objects.get()
    assert run.context == {"reply_id": held_reply.id}
    assert (last.json()["status"], last.json()["run_id"]) == ("running", str(run.id))
    assert last.json()["approvals"] == [
        {
            "id": created.id,
            "step_id": created.step_id,
            "pause": 1,
            "tool": "create_rows",
            "status": "approved",
            "reason": "",
        },
        {
            "id": updated.id,
            "step_id": updated.step_id,
            "pause": 1,
            "tool": "update_rows",
            "status": "rejected",
            "reason": "Wrong row",
        },
    ]
    listed = api_client.get(
        agent_url(conversation.agent, "messages", conversation_uuid=conversation.uuid)
    ).json()["results"]
    assert listed[-1] == last.json()
    assert {
        (approval.decided_by_id, approval.decided_on is not None)
        for approval in held_reply.approvals.all()
    } == {(api_user.id, True)}
    ids = {
        "agent_id": conversation.agent_id,
        "conversation_id": conversation.id,
        "reply_id": held_reply.id,
    }
    assert [entry.args[1] for entry in audited.call_args_list] == [
        {**ids, "approved": ["create_rows"], "rejected": []},
        {**ids, "approved": [], "rejected": ["update_rows"]},
    ]


@pytest.mark.django_db
def test_a_waiting_reply_blocks_new_messages_but_not_their_retries(
    api_client, held_reply
):
    conversation = held_reply.conversation
    url = agent_url(conversation.agent, "messages", conversation_uuid=conversation.uuid)
    sent = conversation.messages.get(role=AgentMessage.Role.USER)

    blocked = api_client.post(url, {"uuid": str(uuid4()), "content": "And more"})
    retried = api_client.post(url, {"uuid": str(sent.uuid), "content": sent.content})

    assert (blocked.status_code, blocked.json()["error"]) == (
        409,
        "ERROR_AGENT_CONVERSATION_WAITING_FOR_APPROVAL",
    )
    assert retried.status_code == 200
    assert retried.json()["reply"]["id"] == held_reply.id
    assert conversation.messages.count() == 2
    assert not ChatRun.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("target", ["decided", "other conversation", "missing"])
def test_only_held_calls_still_pending_in_the_waiting_reply_can_be_decided(
    api_client, api_user, data_fixture, held_reply, target
):
    created, updated = held_reply.approvals.all()
    if target == "decided":
        created.status = AgentToolApproval.Status.APPROVED
        created.save()
        target_id = created.id
    elif target == "other conversation":
        target_id = data_fixture.create_agent_tool_approval(user=api_user).id
    else:
        target_id = updated.id + 100

    response = decide(
        api_client,
        held_reply,
        {"id": updated.id, "approved": True},
        {"id": target_id, "approved": True},
    )

    assert (response.status_code, response.json()["error"]) == (
        409,
        "ERROR_AGENT_TOOL_APPROVAL_NOT_PENDING",
    )
    updated.refresh_from_db()
    assert updated.status == AgentToolApproval.Status.PENDING
    assert not ChatRun.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "decisions",
    [
        [],
        [{"id": 1, "approved": True, "reason": "Looks right"}],
        [{"id": 1, "approved": False, "reason": "x" * 1001}],
        [{"id": 1, "approved": True}, {"id": 1, "approved": False}],
        [{"id": 1, "approved": True, "note": "Unknown"}],
    ],
    ids=["none", "approval-reason", "long-reason", "duplicate", "unknown-field"],
)
def test_decisions_are_validated(api_client, held_reply, decisions):
    response = decide(api_client, held_reply, *decisions)

    assert (response.status_code, response.json()["error"]) == (
        400,
        "ERROR_REQUEST_BODY_VALIDATION",
    )
    assert statuses(held_reply) == ("waiting", ["pending", "pending"])


def fill_the_workspace(api_client: APIClient, reply: AgentMessage) -> None:
    api_client.post(
        agent_url(reply.conversation.agent, "conversations"), new_conversation()
    )


def unready_the_agent(api_client: APIClient, reply: AgentMessage) -> None:
    agent = reply.conversation.agent
    agent.instructions = ""
    agent.save()


@pytest.mark.django_db
@override_settings(BASEROW_AGENT_MAX_ACTIVE_RUNS_PER_WORKSPACE=1)
@pytest.mark.parametrize(
    "refuse,status_code,error",
    [
        (fill_the_workspace, 429, "ERROR_AGENT_BUSY"),
        (unready_the_agent, 400, "ERROR_AGENT_NOT_READY"),
    ],
    ids=["busy-workspace", "not-ready"],
)
def test_a_refused_resume_keeps_every_held_call_pending(
    api_client, held_reply, refuse, status_code, error
):
    refuse(api_client, held_reply)

    response = decide(
        api_client,
        held_reply,
        *[
            {"id": approval.id, "approved": True}
            for approval in held_reply.approvals.all()
        ],
    )

    assert (response.status_code, response.json()["error"]) == (status_code, error)
    assert statuses(held_reply) == ("waiting", ["pending", "pending"])


@pytest.mark.django_db
def test_pending_approvals_are_counted_per_agent_and_per_conversation(
    data_fixture, api_client, api_user, held_reply
):
    waiting = held_reply.conversation
    agent = waiting.agent
    other_agent = data_fixture.create_agent_application(workspace=agent.workspace)
    idle_agent = data_fixture.create_agent_application(workspace=agent.workspace)
    data_fixture.create_agent_tool_approval(
        reply=held_reply, status=AgentToolApproval.Status.APPROVED
    )
    for conversation in [
        data_fixture.create_agent_conversation(
            user=api_user, agent=agent, trashed=True
        ),
        data_fixture.create_agent_conversation(agent=agent),
        data_fixture.create_agent_conversation(user=api_user, agent=other_agent),
    ]:
        data_fixture.create_agent_tool_approval(conversation=conversation)
    idle = data_fixture.create_agent_conversation(user=api_user, agent=agent)
    url = agent_url(agent, "conversations")

    counts = agent.get_type().get_pending_counts(
        api_user, [agent, other_agent, idle_agent]
    )
    listed = api_client.get(url).json()["results"]
    filtered = api_client.get(url, {"has_pending_approvals": "true"}).json()
    renamed = api_client.patch(
        agent_url(agent, "conversation", conversation_uuid=waiting.uuid),
        {"title": "Renamed"},
    )

    assert counts == {agent.id: 2, other_agent.id: 1}
    assert {item["uuid"]: item["pending_approval_count"] for item in listed} == {
        str(waiting.uuid): 2,
        str(idle.uuid): 0,
    }
    assert [item["uuid"] for item in filtered["results"]] == [str(waiting.uuid)]
    assert renamed.json()["pending_approval_count"] == 2


@pytest.mark.django_db
def test_each_decision_sends_the_owner_the_pending_count_left(
    api_user, held_reply, mocker, django_capture_on_commit_callbacks
):
    agent = held_reply.conversation.agent
    broadcast = mocker.patch("baserow.ws.tasks.broadcast_to_users")
    # Eager Celery would otherwise run the resumed reply.
    mocker.patch.object(ChatRunHandler, "_enqueue")

    for approval in held_reply.approvals.all():
        with django_capture_on_commit_callbacks(execute=True):
            DecideAgentToolApprovalsActionType.do(
                api_user,
                agent.id,
                held_reply.conversation.uuid,
                [{"id": approval.id, "approved": True}],
            )

    assert [sent.args for sent in broadcast.delay.call_args_list] == [
        (
            [api_user.id],
            {
                "type": "application_pending_count_updated",
                "application_id": agent.id,
                "pending_count": left,
            },
        )
        for left in (1, 0)
    ]
