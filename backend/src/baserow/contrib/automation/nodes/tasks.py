from typing import Dict, Optional

from django.utils import timezone

from celery.canvas import Signature

from baserow.config.celery import app
from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.models import AutomationWorkflowHistory
from baserow.core.db import atomic_with_retry_on_deadlock


@app.task(bind=True, queue="automation_workflow")
def dispatch_node_celery_task(
    self,
    node_id: int,
    history_id: int,
    current_iterations: Optional[Dict[int, int]] = None,
):
    from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

    # The atomic context should only wrap the dispatch_node() call. If
    # it wraps `raise self.replace()`, the `raise` will cause a rollback,
    # which would cause the node result to not be persisted.
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
    # We call `self.replace()` which internally calls `.delay()` on the
    # signature; this schedules the signature (next node) to be picked up
    # by a worker (which again calls dispatch_node_celery_task). The `raise`
    # tells Celery to replace the current task.
    if isinstance(result, Signature):
        raise self.replace(result)


@app.task
def handle_node_dispatch_done(*args, history_id: Optional[int] = None, **kwargs):
    """
    Callback that gets called when all tasks in a chord group has completed.

    Chords require a callback at a minimum, which can just be a no-op. But
    we use this as a post-chord completion hook to update the workflow history
    when it is the last node in the workflow.
    """

    if history_id:
        AutomationWorkflowHistory.objects.filter(id=history_id).update(
            status=HistoryStatusChoices.SUCCESS,
            completed_on=timezone.now(),
        )
