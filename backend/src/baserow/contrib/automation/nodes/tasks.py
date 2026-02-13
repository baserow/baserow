from typing import Dict, Optional

from baserow.config.celery import app
from baserow.core.db import atomic_with_retry_on_deadlock


@app.task(bind=True, queue="automation_workflow")
@atomic_with_retry_on_deadlock()
def dispatch_node_celery_task(
    self,
    node_id: int,
    history_id: int,
    current_iterations: Optional[Dict[int, int]] = None,
):
    from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

    AutomationNodeHandler().dispatch_node_async(
        node_id,
        history_id,
        current_iterations=current_iterations,
    )
