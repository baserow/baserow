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
    self,
    workflow_id: int,
    is_test_run: bool,
    event_payload: Optional[Union[Dict, List[Dict]]],
):
    from baserow.contrib.automation.history.handler import AutomationHistoryHandler
    from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler

    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)
    original_workflow = workflow.automation.published_from
    dispatch_context = AutomationDispatchContext(workflow, event_payload)
    history_handler = AutomationHistoryHandler()

    start_time = timezone.now()

    history = history_handler.create_workflow_history(
        workflow if is_test_run else original_workflow,
        started_on=start_time,
        is_test_run=is_test_run,
    )

    try:
        AutomationWorkflowRunner().run(workflow, dispatch_context)
    except DispatchException as e:
        history_message = str(e)
        history_status = HistoryStatusChoices.ERROR
    except Exception as e:
        history_message = (
            f"Unexpected error while running workflow {original_workflow.id}. "
            f"Error: {str(e)}"
        )
        history_status = HistoryStatusChoices.ERROR

        logger.exception(history_message)
    else:
        history_message = ""
        history_status = HistoryStatusChoices.SUCCESS
    finally:
        history.completed_on = timezone.now()
        history.message = history_message
        history.status = history_status
        history.save()
