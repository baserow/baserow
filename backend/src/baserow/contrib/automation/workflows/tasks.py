from typing import Dict, List, Optional, Union

from django.utils import timezone

from baserow.config.celery import app
from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.models import AutomationWorkflowHistory
from baserow.core.db import atomic_with_retry_on_deadlock


@app.task(bind=True, queue="automation_workflow")
@atomic_with_retry_on_deadlock()
def start_workflow_celery_task(
    self,
    workflow_id: int,
    event_payload: Optional[Union[Dict, List[Dict]]],
    simulate_until_node_id: Optional[int] = None,
):
    from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler

    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)

    AutomationWorkflowHandler().start_workflow(
        workflow,
        event_payload,
        simulate_until_node_id=simulate_until_node_id,
    )


@app.task
def handle_workflow_dispatch_done(
    history_id: Optional[int] = None,
    simulate_until_node_id: Optional[int] = None,
):
    """
    Hook for any post-workflow dispatch handling.

    If history_id is provided, the workflow's history is updated to 'success'.

    If simulate_until_node_id is provided, the related workflow history is deleted.
    """

    if simulate_until_node_id:
        AutomationWorkflowHistory.objects.filter(
            simulate_until_node_id=simulate_until_node_id
        ).delete()

    if history_id:
        AutomationWorkflowHistory.objects.filter(id=history_id).update(
            status=HistoryStatusChoices.SUCCESS,
            completed_on=timezone.now(),
        )
