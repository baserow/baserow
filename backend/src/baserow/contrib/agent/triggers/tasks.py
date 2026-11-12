from typing import Any

from celery import Celery, Task

from baserow.config.celery import app

from ..constants import QUEUED_TRIGGER_REPLY_SWEEP_SECONDS
from .handler import AgentTriggerHandler


@app.task
def start_trigger_conversation(
    trigger_id: int, content: str, failure: str | None
) -> None:
    """
    Apply the rules of a trigger that fired, after the event that fired it
    committed.

    :param trigger_id: The id of the trigger that fired.
    :param content: The resolved message opening the conversation.
    :param failure: The error code failing the reply instead of running it, or None.
    """

    from .dispatcher import agent_trigger_dispatcher

    agent_trigger_dispatcher.start(trigger_id, content, failure)


@app.task(bind=True, queue="export", ignore_result=True)
def start_queued_trigger_replies(self: Task) -> None:
    """
    Start the oldest queued reply of each trigger with nothing going: the safety
    net for a hand-off that found the trigger locked, never ran, or met the
    workspace's run limit. One query when nothing is queued.
    """

    from .dispatcher import agent_trigger_dispatcher

    for trigger in AgentTriggerHandler().list_idle_triggers_with_queued_replies():
        agent_trigger_dispatcher.start_next_queued_reply(trigger)


@app.on_after_finalize.connect
def setup_periodic_agent_trigger_tasks(sender: Celery, **kwargs: Any) -> None:
    """
    Schedules the queued reply sweep.

    :param sender: The Celery app.
    """

    sender.add_periodic_task(
        QUEUED_TRIGGER_REPLY_SWEEP_SECONDS, start_queued_trigger_replies.s()
    )
