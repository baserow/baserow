import time
from typing import Dict, Optional

from celery.canvas import Signature

from baserow.config.celery import app
from baserow.core.db import atomic_with_retry_on_deadlock


# `max_retries=None`: the node's own `max_retries` bounds the retries (see
# AutomationNodeHandler._can_retry), Celery's default of 3 would otherwise raise
# MaxRetriesExceededError on the 4th retry of a node allowed 5.
@app.task(bind=True, queue="automation_workflow", max_retries=None)
def dispatch_node_celery_task(
    self,
    node_id: int,
    history_id: int,
    current_iterations: Optional[Dict[int, int]] = None,
    attempt: int = 1,
) -> Signature | None:
    from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
    from baserow.contrib.automation.nodes.types import NodeDispatchRetry

    # The atomic context should only wrap the dispatch_node() call. If
    # it also wraps `self.replace()`, which internally raises `Ignore`,
    # the rollback will cause the node result to not be persisted.
    @atomic_with_retry_on_deadlock()
    def _dispatch():
        return AutomationNodeHandler().dispatch_node(
            node_id,
            history_id,
            current_iterations=current_iterations,
            attempt=attempt,
        )

    result = _dispatch()

    if isinstance(result, NodeDispatchRetry):
        # Raised outside the atomic block, like the webhook task does, so the
        # attempt's history row stays committed. Celery rebuilds the signature
        # from the request, keeping its chain/chord/group options, so a retried
        # iterator child still completes its group and the run's chain goes on.
        # The positional args are kept as they are; only `attempt` is replaced.
        raise self.retry(
            countdown=result.countdown,
            kwargs={**(self.request.kwargs or {}), "attempt": result.attempt + 1},
        )

    # When result is a Signature (chord, group, etc), it represents the next
    # node that needs to be dispatched as an async task.
    #
    # We call `self.replace()` which internally calls `.delay()` then
    # raises `Ignore` to signal to Celery that the current task should be
    # replaced. This results in the signature (next node) to be picked up
    # by a worker (which again calls dispatch_node_celery_task).
    if isinstance(result, Signature):
        return self.replace(result)

    return None


@app.task(bind=True, queue="automation_workflow", max_retries=None)
def resume_deferred_node_celery_task(
    self,
    node_history_id: int,
    deferred_history_id: int,
    iteration_path: str,
    deadline: float,
    current_iterations: Optional[Dict[int, int]] = None,
) -> Signature | None:
    """
    Polls without blocking a worker until a child response, completion, or timeout.
    """

    from baserow.contrib.automation.history.constants import HistoryStatusChoices
    from baserow.contrib.automation.history.handler import AutomationHistoryHandler
    from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

    history_handler = AutomationHistoryHandler()
    deferred_history = history_handler.get_workflow_history(deferred_history_id)
    timed_out = time.time() >= deadline
    response = (
        None
        if timed_out
        else history_handler.get_workflow_history_response(deferred_history)
    )
    if (
        response is None
        and deferred_history.status == HistoryStatusChoices.STARTED
        and not timed_out
    ):
        raise self.retry(
            countdown=history_handler.RESPONSE_POLL_INITIAL_INTERVAL_SECONDS,
        )

    @atomic_with_retry_on_deadlock()
    def _resume():
        return AutomationNodeHandler().complete_deferred_node(
            node_history_id,
            deferred_history_id,
            iteration_path,
            timed_out,
            current_iterations,
        )

    result = _resume()
    if isinstance(result, Signature):
        return self.replace(result)
    return None
