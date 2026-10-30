from uuid import uuid4

from django.urls import reverse

from baserow.core.chat_runs.models import ChatRun
from baserow.core.chat_runs.tasks import execute_chat_run
from baserow.core.models import Application


def agent_url(agent: Application, view: str, **kwargs: object) -> str:
    return reverse(f"api:agent:{view}", kwargs={"agent_id": agent.id, **kwargs})


def new_conversation(content: str = "Hello\nworld") -> dict[str, str]:
    return {"uuid": str(uuid4()), "message_uuid": str(uuid4()), "content": content}


def run_reply(run: ChatRun) -> None:
    """Answer the run like a worker, whose tasks never reuse a request's cache."""

    execute_chat_run.apply(args=[str(run.id)])
