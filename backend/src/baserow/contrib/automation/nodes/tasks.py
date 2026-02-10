from typing import Dict, List, Optional

from baserow.config.celery import app
from baserow.core.db import atomic_with_retry_on_deadlock


@app.task(bind=True, queue="automation_workflow")
@atomic_with_retry_on_deadlock()
def dispatch_node_celery_task(
    self,
    node_id: int,
    history_id: int,
    allowed_node_ids: Optional[List[int]] = None,
    current_iterations: Optional[Dict[int, int]] = None,
):
    from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

    AutomationNodeHandler().dispatch_node_async(
        node_id,
        history_id,
        allowed_node_ids=allowed_node_ids,
        current_iterations=current_iterations,
    )
