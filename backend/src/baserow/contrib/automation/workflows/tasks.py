from typing import Dict, List, Optional, Union

from loguru import logger

from baserow.config.celery import app
from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeMisconfiguredService,
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

    try:
        AutomationWorkflowRunner().run(workflow, dispatch_context)
    except AutomationNodeMisconfiguredService as e:
        error = str(e)
        if e.__cause__:
            error += f" {e.__cause__}"

        logger.error(f"Error while running workflow {workflow_id}: {error}")
