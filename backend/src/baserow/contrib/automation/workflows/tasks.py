from typing import Dict, List, Optional, Union

from baserow.config.celery import app
from baserow.core.db import atomic_with_retry_on_deadlock


@app.task(bind=True, queue="automation_workflow")
@atomic_with_retry_on_deadlock()
def run_workflow(
    self,
    workflow_id: int,
    is_test_run: bool,
    event_payload: Optional[Union[Dict, List[Dict]]],
):
    from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler

    AutomationWorkflowHandler().start_workflow(workflow_id, is_test_run, event_payload)
