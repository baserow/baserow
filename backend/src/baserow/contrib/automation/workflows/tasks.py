from typing import Optional

from django.utils import timezone

from celery.canvas import Signature

from baserow.config.celery import app
from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.automation.history.models import AutomationWorkflowHistory
from baserow.core.db import atomic_with_retry_on_deadlock


@app.task(queue="automation_workflow")
def start_workflow_celery_task(
    workflow_id: int,
    history_id: int,
):
    from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler

    @atomic_with_retry_on_deadlock()
    def _start():
        workflow = AutomationWorkflowHandler().get_workflow(workflow_id)
        history = AutomationHistoryHandler().get_workflow_history(history_id)
        return AutomationWorkflowHandler().start_workflow(
            workflow,
            history,
        )

    result = _start()

    if isinstance(result, Signature):
        # Schedule the workflow to be executed. We use delay() here instead of
        # replace() because replace internally calls `result.get()` which isn't
        # allowed in eager mode (which is used by tests).
        result.delay()


@app.task
def handle_workflow_dispatch_done(
    history_id: int,
    simulate_until_node_id: Optional[int] = None,
):
    """
    Hook for any post-workflow dispatch handling.

    If history_id is provided, the workflow's history is updated to 'success'.

    If simulate_until_node_id is provided, the related workflow history is deleted.
    """

    if simulate_until_node_id:
        # We just delete the history entry as we don't need it.
        AutomationWorkflowHistory.objects.filter(
            id=history_id, simulate_until_node_id=simulate_until_node_id
        ).delete()

    else:
        # Only update the history if it's still started.
        # If the workflow history was marked as failed by a specific node, we
        # don't want to overwrite it.
        AutomationWorkflowHistory.objects.filter(
            id=history_id,
            status=HistoryStatusChoices.STARTED,
        ).update(
            status=HistoryStatusChoices.SUCCESS,
            completed_on=timezone.now(),
        )
