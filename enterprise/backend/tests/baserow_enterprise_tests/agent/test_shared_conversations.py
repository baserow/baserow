import contextlib

from django.db import transaction

import pytest

from baserow.contrib.agent.chat_run_type import AgentChatRunType
from baserow.contrib.agent.exceptions import AgentConversationReadOnly
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentConversation,
    AgentMessage,
    AgentReplyStatus,
    AgentToolApproval,
)
from baserow.contrib.agent.service import AgentService
from baserow.core.chat_runs.models import ChatRun
from baserow.core.exceptions import PermissionException
from baserow.core.models import Agent
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role

READ = {"list", "read", "follow"}
CHANGE = READ | {"stop", "pin", "rename", "delete"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_uid,allowed,send_error",
    [
        (None, set(), PermissionException),
        ("NO_ACCESS", set(), PermissionException),
        ("VIEWER", READ, PermissionException),
        ("EDITOR", READ, AgentConversationReadOnly),
        ("BUILDER", CHANGE, AgentConversationReadOnly),
        ("ADMIN", CHANGE, AgentConversationReadOnly),
    ],
    ids=["non-member", "no-access", "viewer", "editor", "builder", "admin"],
)
def test_shared_conversations_are_read_by_every_role_and_changed_by_builders(
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    role_uid,
    allowed,
    send_error,
):
    """Viewers and editors watch; builders change and stop them; nobody sends."""

    admin = enterprise_data_fixture.create_user()
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, members=[user] if role_uid else []
    )
    if role_uid:
        RoleAssignmentHandler().assign_role(
            user, workspace, Role.objects.get(uid=role_uid)
        )
    agent = enterprise_data_fixture.create_agent_application(workspace=workspace)
    trigger = enterprise_data_fixture.create_agent_trigger(agent=agent)
    conversation = (
        AgentHandler().start_trigger_conversation(trigger, "Tick").conversation
    )
    run = ChatRun.objects.get(run_type="agent", chat_id=conversation.id)
    service, run_type = AgentService(), AgentChatRunType()
    attempts = {
        "list": lambda: (
            conversation.uuid
            in {item.uuid for item in service.list_conversations(user, agent.id)}
        ),
        "read": lambda: (
            service.list_messages(user, agent.id, conversation.uuid)[0] == conversation
            and run_type.can_read(user, run)
        ),
        "follow": lambda: run_type.can_follow_chat(user, conversation.id),
        "stop": lambda: run_type.can_cancel(user, run),
        "pin": lambda: (
            service.update_conversation(user, agent.id, conversation.uuid, pinned=True)
            is not None
        ),
        "rename": lambda: (
            service.update_conversation(
                user, agent.id, conversation.uuid, title="Renamed"
            )
            is not None
        ),
        "delete": lambda: (
            service.delete_conversation(user, agent.id, conversation.uuid) is not None
        ),
    }

    with pytest.raises(send_error):
        service.create_message(user, agent.id, conversation.uuid, run.id, "Hello")
    outcomes = {}
    # The order matters: a successful delete ends the conversation's visibility.
    for name in ["list", "read", "follow", "stop", "pin", "rename", "delete"]:
        try:
            with transaction.atomic():
                outcomes[name] = bool(attempts[name]())
        except PermissionException:
            outcomes[name] = False

    assert {name for name, ok in outcomes.items() if ok} == allowed
    conversation.refresh_from_db()
    assert conversation.trashed is ("delete" in allowed)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_uid,renames_own,restores_shared",
    [
        ("VIEWER", False, False),
        ("COMMENTER", False, False),
        ("EDITOR", True, False),
        ("BUILDER", True, True),
    ],
    ids=["viewer", "commenter", "editor", "builder"],
)
def test_members_delete_their_own_conversations_and_builders_restore_shared_ones(
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    role_uid,
    renames_own,
    restores_shared,
):
    """A viewer can still delete a private conversation left from an older role."""

    admin = enterprise_data_fixture.create_user()
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=admin, members=[user])
    RoleAssignmentHandler().assign_role(user, workspace, Role.objects.get(uid=role_uid))
    agent = enterprise_data_fixture.create_agent_application(workspace=workspace)
    shared = enterprise_data_fixture.create_shared_agent_conversation(agent=agent)
    private = enterprise_data_fixture.create_agent_conversation(user=user, agent=agent)
    trashed = enterprise_data_fixture.create_agent_conversation(user=user, agent=agent)
    service = AgentService()
    service.delete_conversation(admin, agent.id, shared.uuid)
    AgentHandler().delete_conversation(user, trashed)

    with (
        contextlib.nullcontext() if renames_own else pytest.raises(PermissionException)
    ):
        service.update_conversation(user, agent.id, private.uuid, title="Renamed")
    service.delete_conversation(user, agent.id, private.uuid)
    TrashHandler.restore_item(user, "agent_conversation", trashed.id)
    with (
        contextlib.nullcontext()
        if restores_shared
        else pytest.raises(PermissionException)
    ):
        TrashHandler.restore_item(user, "agent_conversation", shared.id)

    assert set(AgentConversation.objects.values_list("id", flat=True)) == {
        trashed.id,
        *([shared.id] if restores_shared else []),
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_uid,decides,always_allows",
    [
        ("VIEWER", False, False),
        ("COMMENTER", False, False),
        ("EDITOR", True, False),
        ("BUILDER", True, True),
    ],
    ids=["viewer", "commenter", "editor", "builder"],
)
def test_editors_decide_held_calls_in_shared_conversations_and_builders_always_allow(
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    role_uid,
    decides,
    always_allows,
):
    admin = enterprise_data_fixture.create_user()
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=admin, members=[user])
    RoleAssignmentHandler().assign_role(user, workspace, Role.objects.get(uid=role_uid))
    agent = enterprise_data_fixture.create_agent_application(workspace=workspace)
    AgentHandler().update_configuration(
        agent,
        run_as_subject_type="core.Agent",
        run_as_subject_id=Agent.objects.create(workspace=workspace, name="Ops").id,
        allowed_tools=["create_rows"],
        ask_first_tools=["create_rows"],
    )
    conversation = enterprise_data_fixture.create_shared_agent_conversation(agent=agent)
    reply = enterprise_data_fixture.create_agent_message(
        conversation=conversation,
        role=AgentMessage.Role.ASSISTANT,
        status=AgentReplyStatus.WAITING,
        content="",
    )
    first, second, third = [
        enterprise_data_fixture.create_agent_tool_approval(reply=reply)
        for _ in range(3)
    ]

    def decide(approval: AgentToolApproval, always_allow: bool, allowed: bool):
        with (
            contextlib.nullcontext() if allowed else pytest.raises(PermissionException)
        ):
            AgentService().decide_approvals(
                user,
                agent.id,
                conversation.uuid,
                [{"id": approval.id, "approved": True}],
                always_allow=always_allow,
            )

    decide(first, always_allow=False, allowed=decides)
    decide(second, always_allow=True, allowed=always_allows)

    assert [
        approval.status
        for approval in AgentToolApproval.objects.filter(reply=reply).order_by("id")
    ] == [
        "approved" if decides else "pending",
        "approved" if always_allows else "pending",
        "pending",
    ]
    assert agent.allowed_tools.get(name="create_rows").ask_first is not always_allows


@pytest.mark.django_db
@pytest.mark.enable_signals(
    "baserow.ws.tasks.broadcast_application_pending_counts.delay"
)
def test_shared_held_calls_count_for_users_who_may_decide_them(
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    mocker,
    django_capture_on_commit_callbacks,
):
    admin, viewer, editor = [enterprise_data_fixture.create_user() for _ in range(3)]
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, members=[viewer, editor]
    )
    for user, role_uid in [(viewer, "VIEWER"), (editor, "EDITOR")]:
        RoleAssignmentHandler().assign_role(
            user, workspace, Role.objects.get(uid=role_uid)
        )
    agent = enterprise_data_fixture.create_agent_application(workspace=workspace)
    shared = enterprise_data_fixture.create_shared_agent_conversation(agent=agent)
    reply = enterprise_data_fixture.create_agent_message(
        conversation=shared,
        role=AgentMessage.Role.ASSISTANT,
        status=AgentReplyStatus.WAITING,
        content="",
    )
    held = [
        enterprise_data_fixture.create_agent_tool_approval(reply=reply)
        for _ in range(2)
    ]
    for conversation in [
        enterprise_data_fixture.create_shared_agent_conversation(
            agent=agent, trashed=True
        ),
        enterprise_data_fixture.create_agent_conversation(user=editor, agent=agent),
    ]:
        enterprise_data_fixture.create_agent_tool_approval(conversation=conversation)
    broadcast = mocker.patch("baserow.ws.tasks.broadcast_to_users_individual_payloads")

    counts = agent.get_type().get_pending_counts([admin, viewer, editor], [agent])
    with django_capture_on_commit_callbacks(execute=True):
        AgentService().decide_approvals(
            editor, agent.id, shared.uuid, [{"id": held[0].id, "approved": True}]
        )

    assert counts == {admin.id: {agent.id: 2}, editor.id: {agent.id: 3}}
    assert {
        user_id: payload["pending_count"]
        for user_id, payload in broadcast.call_args.args[0].items()
    } == {str(admin.id): 1, str(viewer.id): 0, str(editor.id): 2}
