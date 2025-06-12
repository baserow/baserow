from typing import Dict, List, Optional, Union

from baserow.config.celery import app
from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.workflows.runner import AutomationWorkflowRunner
from baserow.core.db import atomic_with_retry_on_deadlock


@app.task(bind=True, queue="automation_workflow")
@atomic_with_retry_on_deadlock()
def run_workflow(
    self, workflow_id: int, event_payload: Optional[Union[Dict, List[Dict]]]
):
    from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler

    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)
    dispatch_context = AutomationDispatchContext(workflow, event_payload)

    AutomationWorkflowRunner().run(workflow, dispatch_context)
