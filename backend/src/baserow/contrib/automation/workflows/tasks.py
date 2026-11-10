from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone

from celery.canvas import Signature
from loguru import logger

from baserow.config.celery import app
from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.automation.history.models import AutomationWorkflowHistory
from baserow.contrib.automation.workflows.signals import (
    automation_workflow_dispatch_done,
)
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

    A run history that no longer exists is ignored: the workflow, and with it the
    run's history, can be deleted while the run is still in flight.
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
        history = AutomationWorkflowHistory.objects.filter(id=history_id).first()
        if history is None:
            # The run history is gone, for example because the workflow was
            # deleted while the run was still in flight (a waiting node can keep
            # a run alive for hours). Nothing is left to update.
            logger.warning(
                f"Workflow history with ID {history_id} was not found. It was "
                "likely deleted while the workflow was still running."
            )
            return

        AutomationHistoryHandler().ensure_default_response(history)
        AutomationWorkflowHistory.objects.filter(
            id=history_id,
            status=HistoryStatusChoices.STARTED,
        ).update(
            status=HistoryStatusChoices.SUCCESS,
            completed_on=timezone.now(),
        )

        history.refresh_from_db()
        automation_workflow_dispatch_done.send(
            sender=None,
            workflow_history=history,
        )


@app.task(queue="automation_workflow")
def automation_periodic_cleanup():
    from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
    from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler

    handler = AutomationWorkflowHandler()
    # The runs that are over their budget are resolved first, so that the
    # recovery sweep leaves their waiting nodes, which were just resolved with
    # them, alone.
    handler.mark_failure_for_timed_out_history()
    AutomationNodeHandler().resume_stale_waiting_nodes()
    handler.clear_old_history()


@app.on_after_finalize.connect
def setup_periodic_automation_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(
            minutes=settings.AUTOMATION_WORKFLOW_HISTORY_CLEANUP_INTERVAL_MINUTES
        ),
        automation_periodic_cleanup.s(),
    )
