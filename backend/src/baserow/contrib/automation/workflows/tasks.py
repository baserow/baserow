from typing import Dict, List, Optional, Union

from baserow.config.celery import app
from baserow.core.db import atomic_with_retry_on_deadlock


@app.task(bind=True, queue="automation_workflow")
@atomic_with_retry_on_deadlock()
def start_workflow_celery_task(
    self,
    workflow_id: int,
    event_payload: Optional[Union[Dict, List[Dict]]],
    simulate_until_node_id: Optional[int] = None,
):
    from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
    from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler

    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)

    simulate_until_node = (
        AutomationNodeHandler().get_node(simulate_until_node_id)
        if simulate_until_node_id
        else None
    )

    AutomationWorkflowHandler().start_workflow(
        workflow,
        event_payload,
        simulate_until_node=simulate_until_node,
    )
