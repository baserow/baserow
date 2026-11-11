from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction

import pytest

from baserow.contrib.agent.actions import DeleteAgentConversationActionType
from baserow.contrib.agent.constants import AGENT_RUN_TYPE
from baserow.contrib.agent.models import AgentConversation, AgentToolApproval
from baserow.contrib.agent.service import AgentService
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import UpdateApplicationActionType
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun, ChatRunStatus
from baserow.core.handler import CoreHandler
from baserow.core.models import Application


def start_session() -> int:
    """
    Bound every statement of this thread's connection so a lost race fails fast.

    :return: The connection's backend pid.
    """

    with connection.cursor() as cursor:
        cursor.execute("SET statement_timeout = '10s'")
        cursor.execute("SELECT pg_backend_pid()")
        return cursor.fetchone()[0]


def wait_until_blocked(pid: int, waiter: Future) -> bool:
    """
    Poll until a backend waits for a lock, or its thread ends.

    :param pid: The backend pid of the waiting thread's connection.
    :param waiter: The waiting thread.
    :return: Whether the backend waited for a lock within five seconds.
    """

    deadline = monotonic() + 5
    while monotonic() < deadline and not waiter.done():
        with connection.cursor() as cursor:
            cursor.execute("SELECT cardinality(pg_blocking_pids(%s))", [pid])
            if cursor.fetchone()[0] > 0:
                return True
        sleep(0.01)
    return False


@pytest.mark.django_db(transaction=True)
def test_configuration_update_and_application_rename_are_serialized(data_fixture):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(
        user=user, name="Original name", instructions="Original instructions"
    )
    rename_locked = Event()
    release_rename = Event()
    configuration_connected = Event()
    configuration_pid = []

    def rename_application():
        try:
            start_session()
            with transaction.atomic():
                # The generic application PATCH locks its parent before its action.
                application = (
                    CoreHandler()
                    .get_application(
                        agent.id,
                        base_queryset=Application.objects.select_for_update(
                            of=("self",)
                        ),
                    )
                    .specific
                )
                rename_locked.set()
                assert release_rename.wait(10), "The rename was never released"
                action_type_registry.get_by_type(UpdateApplicationActionType).do(
                    user, application, name="Renamed agent"
                )
        finally:
            connections.close_all()

    def update_configuration():
        try:
            configuration_pid.append(start_session())
            configuration_connected.set()
            AgentService().update_configuration(
                user, agent.id, instructions="Updated instructions"
            )
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        rename = executor.submit(rename_application)
        try:
            assert rename_locked.wait(10)
            configuration = executor.submit(update_configuration)
            assert configuration_connected.wait(10)
            assert wait_until_blocked(configuration_pid[0], configuration), (
                "The configuration update did not wait for the rename"
            )
        finally:
            release_rename.set()
        rename.result(timeout=10)
        configuration.result(timeout=10)

    agent.refresh_from_db()
    assert (agent.name, agent.instructions) == ("Renamed agent", "Updated instructions")


@pytest.mark.django_db(transaction=True)
def test_deleting_a_conversation_while_its_run_ends_does_not_deadlock(data_fixture):
    user = data_fixture.create_user()
    conversation = data_fixture.create_agent_conversation(user=user)
    run = ChatRun.objects.create(
        run_type=AGENT_RUN_TYPE,
        chat_id=conversation.id,
        workspace=conversation.agent.workspace,
        created_by=user,
        status=ChatRunStatus.RUNNING,
    )
    run_locked = Event()
    release_run = Event()
    delete_connected = Event()
    delete_pid = []

    def end_run():
        try:
            start_session()
            # Like the worker saving its reply: the run, then the conversation.
            with transaction.atomic():
                assert ChatRunHandler().lock_running_run(run.id)
                run_locked.set()
                assert release_run.wait(10), "The run was never released"
                conversation.save(update_fields=["updated_on"])
        finally:
            connections.close_all()

    def delete_conversation():
        try:
            delete_pid.append(start_session())
            delete_connected.set()
            action_type_registry.get_by_type(DeleteAgentConversationActionType).do(
                user, conversation.agent_id, conversation.uuid
            )
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        ending = executor.submit(end_run)
        try:
            assert run_locked.wait(10)
            deleting = executor.submit(delete_conversation)
            assert delete_connected.wait(10)
            assert wait_until_blocked(delete_pid[0], deleting), (
                "The delete did not wait for the run"
            )
        finally:
            release_run.set()
        ending.result(timeout=10)
        deleting.result(timeout=10)

    run.refresh_from_db()
    assert run.cancel_requested_at is not None


@pytest.mark.django_db(transaction=True)
def test_the_last_two_decisions_arriving_together_resume_the_reply_once(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    reply = data_fixture.create_agent_message(
        user=user, agent=agent, role="assistant", status="waiting"
    )
    approvals = [data_fixture.create_agent_tool_approval(reply=reply) for _ in range(2)]
    # An eager resume would run the reply in a deciding thread.
    mocker.patch.object(ChatRunHandler, "_enqueue")
    decider_pids = []

    def decide(approval: AgentToolApproval) -> bool:
        try:
            decider_pids.append(start_session())
            actor = get_user_model().objects.get(id=user.id)
            _, run_id = AgentService().decide_approvals(
                actor,
                agent.id,
                reply.conversation.uuid,
                [{"id": approval.id, "approved": True}],
            )
            return run_id is not None
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        with transaction.atomic():
            AgentConversation.objects.select_for_update().get(id=reply.conversation_id)
            decisions = [executor.submit(decide, approval) for approval in approvals]
            deadline = monotonic() + 5
            blocked = 0
            while monotonic() < deadline and blocked < 2:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT count(*) FROM unnest(%s::int[]) AS pid "
                        "WHERE cardinality(pg_blocking_pids(pid)) > 0",
                        [decider_pids],
                    )
                    blocked = cursor.fetchone()[0]
                sleep(0.01)
            assert blocked == 2, "The decisions did not wait for the conversation"
        resumed = sorted(decision.result(timeout=10) for decision in decisions)

    assert resumed == [False, True]
    assert ChatRun.objects.get().context == {"reply_id": reply.id}
    reply.refresh_from_db()
    assert reply.status == "running"
