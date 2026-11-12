from typing import Any

from celery import Celery, Task

from baserow.config.celery import app

from ..constants import QUEUED_TRIGGER_REPLY_SWEEP_SECONDS
from .handler import AgentTriggerHandler


@app.task
def start_trigger_conversations(
    trigger_id: int,
    service_id: int,
    firings: list[list[str | None]],
    dropped_batches: int = 0,
    can_read: bool = True,
) -> None:
    """
    Apply the rules of a trigger to each firing of one event, after the event
    that fired it committed.

    :param trigger_id: The id of the trigger that fired.
    :param service_id: The id of the service the firings were resolved from.
    :param firings: Each firing's resolved message and the error code failing its
        reply, or None, in the event's order.
    :param dropped_batches: How many batches of the event were left out.
    :param can_read: Whether the run identity could read the event's data.
    """

    from .dispatcher import agent_trigger_dispatcher

    agent_trigger_dispatcher.start(
        trigger_id, service_id, firings, dropped_batches, can_read
    )


@app.task(ignore_result=True)
def hand_off_trigger_queue(trigger_id: int) -> None:
    """
    Start the queued replies a trigger has room for, once one of its replies
    ended.

    :param trigger_id: The id of the trigger whose reply ended.
    """

    from .dispatcher import agent_trigger_dispatcher

    agent_trigger_dispatcher.hand_off(trigger_id)


@app.task(bind=True, queue="export", ignore_result=True)
def start_queued_trigger_replies(self: Task) -> None:
    """
    Start the queued replies of each trigger whose overlap rule has room: the
    safety net for a hand-off that found the trigger locked or unable to run,
    never ran, or met the workspace's run limit. One query when nothing is
    queued.
    """

    from .dispatcher import agent_trigger_dispatcher

    for trigger in AgentTriggerHandler().list_triggers_with_room_for_queued_replies():
        agent_trigger_dispatcher.start_queued_replies(trigger)


@app.on_after_finalize.connect
def setup_periodic_agent_trigger_tasks(sender: Celery, **kwargs: Any) -> None:
    """
    Schedules the queued reply sweep.

    :param sender: The Celery app.
    """

    sender.add_periodic_task(
        QUEUED_TRIGGER_REPLY_SWEEP_SECONDS, start_queued_trigger_replies.s()
    )
