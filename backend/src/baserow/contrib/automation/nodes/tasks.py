import time
from typing import Dict, Optional

from celery.canvas import Signature

from baserow.config.celery import app
from baserow.core.db import atomic_with_retry_on_deadlock


@app.task(bind=True, queue="automation_workflow")
def dispatch_node_celery_task(
    self,
    node_id: int,
    history_id: int,
    current_iterations: Optional[Dict[int, int]] = None,
) -> Signature | None:
    from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

    # The atomic context should only wrap the dispatch_node() call. If
    # it also wraps `self.replace()`, which internally raises `Ignore`,
    # the rollback will cause the node result to not be persisted.
    @atomic_with_retry_on_deadlock()
    def _dispatch():
        return AutomationNodeHandler().dispatch_node(
            node_id,
            history_id,
            current_iterations=current_iterations,
        )

    result = _dispatch()

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
    response = history_handler.get_workflow_history_response(deferred_history)
    timed_out = time.time() >= deadline
    if (
        response is None
        and deferred_history.status == HistoryStatusChoices.STARTED
        and not timed_out
    ):
        raise self.retry(
            countdown=history_handler.RESPONSE_POLL_INTERVAL_SECONDS,
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
