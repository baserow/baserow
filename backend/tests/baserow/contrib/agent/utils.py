from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from time import monotonic, sleep
from typing import TypeVar
from uuid import uuid4

from django.db import connection, connections, transaction
from django.urls import reverse

from baserow.contrib.agent.constants import AGENT_RUN_TYPE
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentApplication, AgentMessage, AgentTrigger
from baserow.core.chat_runs.models import ChatRun
from baserow.core.chat_runs.tasks import execute_chat_run
from baserow.core.models import Application

T = TypeVar("T")


def agent_url(agent: Application, view: str, **kwargs: object) -> str:
    return reverse(f"api:agent:{view}", kwargs={"agent_id": agent.id, **kwargs})


def new_conversation(content: str = "Hello\nworld") -> dict[str, str]:
    return {"uuid": str(uuid4()), "message_uuid": str(uuid4()), "content": content}


def run_reply(run: ChatRun) -> None:
    """Answer the run like a worker, whose tasks never reuse a request's cache."""

    execute_chat_run.apply(args=[str(run.id)])


def queued_reply(
    trigger: AgentTrigger, content: str = "Check the inbox"
) -> AgentMessage:
    """A trigger conversation started without a run, as a waiting firing queues it."""

    return (
        AgentHandler()
        .start_trigger_conversation(trigger, content, start_run=False)
        .reply
    )


def hold_a_workspace_run(data_fixture, agent: AgentApplication) -> ChatRun:
    """An active run of a private conversation, filling a slot of the workspace."""

    user = data_fixture.create_user()
    private = data_fixture.create_agent_conversation(user=user, agent=agent)
    return ChatRun.objects.create(
        run_type=AGENT_RUN_TYPE,
        chat_id=private.id,
        workspace=agent.workspace,
        created_by=user,
    )


def in_another_connection(work: Callable[[], T]) -> Future[T]:
    """Run ``work`` in a transaction of its own connection, as a concurrent caller."""

    def run() -> T:
        try:
            with transaction.atomic():
                return work()
        finally:
            connections.close_all()

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(run)
    executor.shutdown(wait=False)
    return future


def wait_for_a_lock_waiter() -> None:
    """Return once another connection waits for a lock this transaction holds."""

    deadline = monotonic() + 10
    with connection.cursor() as cursor:
        while monotonic() < deadline:
            # Statistics views keep their first snapshot for the whole transaction.
            cursor.execute("SELECT pg_stat_clear_snapshot()")
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                "WHERE pg_backend_pid() = ANY(pg_blocking_pids(pid)))"
            )
            if cursor.fetchone()[0]:
                return
            sleep(0.01)
    raise AssertionError("Nothing waited for a lock")
