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

@app.task(bind=True, queue="automation_workflow")
@atomic_with_retry_on_deadlock()
def dispatch_node_celery_task(self, workflow_id, node_id, dispatch_context_data, allowed_node_ids=None):
    from baserow.contrib.automation.automation_dispatch_context import AutomationDispatchContext
    from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
    from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler

    workflow = AutomationWorkflowHandler().get_workflow(workflow_id)
    node = AutomationNodeHandler().get_node(node_id)

    dispatch_context = AutomationDispatchContext.from_dict(workflow, dispatch_context_data)

    allowed_nodes = None
    if allowed_node_ids is not None:
        allowed_nodes = {AutomationNodeHandler().get_node(nid) for nid in allowed_node_ids}

    node_type = node.get_type()
    dispatch_result = node_type.dispatch(node, dispatch_context)
    dispatch_context.after_dispatch(node, dispatch_result)

    if children := node.get_children():
        node_data = dispatch_result.data["results"]
        iterations = [0] if dispatch_context.simulate_until_node else range(len(node_data))

        for index in iterations:
            sub_dispatch_context = dispatch_context.clone()
            sub_dispatch_context.set_current_iteration(node, index)

            for child in children:
                allowed_node_ids_list = [n.id for n in allowed_nodes] if allowed_nodes else None
                dispatch_node_celery_task.delay(
                    workflow_id,
                    child.id,
                    sub_dispatch_context.to_dict(),
                    allowed_node_ids_list,
                )

    next_nodes = node.get_next_nodes(dispatch_result.output_uid)
    for next_node in next_nodes:
        allowed_node_ids_list = [n.id for n in allowed_nodes] if allowed_nodes else None
        dispatch_node_celery_task.delay(
            workflow_id,
            next_node.id,
            dispatch_context.to_dict(),
            allowed_node_ids_list,
        )

