from typing import Dict, List, Optional, Union

from django.utils import timezone

from loguru import logger

from baserow.config.celery import app
from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.workflows.runner import AutomationWorkflowRunner
from baserow.core.db import atomic_with_retry_on_deadlock
from baserow.core.services.exceptions import DispatchException


@app.task(bind=True, queue="automation_workflow")
@atomic_with_retry_on_deadlock()
def run_workflow(
    self, workflow_id: int, event_payload: Optional[Union[Dict, List[Dict]]]
):
    from baserow.contrib.automation.history.handler import AutomationHistoryHandler
    from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler

    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)
    dispatch_context = AutomationDispatchContext(workflow, event_payload)
    history_handler = AutomationHistoryHandler()

    try:
        AutomationWorkflowRunner().run(workflow, dispatch_context)
    except DispatchException as e:
        history_message = str(e)
        history_status = HistoryStatusChoices.ERROR
    except Exception as e:
        # For unexpected errors, store a generic message in history
        original_workflow = workflow.automation.published_from
        history_message = (
            f"Unexpected error while running workflow {original_workflow.id}"
        )
        history_status = HistoryStatusChoices.ERROR

        logger.error(f"{history_message}. Error: {str(e)}")
    else:
        history_message = ""
        history_status = HistoryStatusChoices.SUCCESS
    finally:
        history_handler.create_workflow_history(
            workflow,
            completed_on=timezone.now(),
            status=history_status,
            message=history_message,
        )

        # The allow_test_run_until value must be reset after the history is
        # created, since the history creation accesses this value.
        if workflow.allow_test_run_until:
            workflow.allow_test_run_until = None
            workflow.save(update_fields=["allow_test_run_until"])
