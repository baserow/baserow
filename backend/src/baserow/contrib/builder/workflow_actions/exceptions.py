class WorkflowActionNotInElement(Exception):
    """Raised when trying to get a workflow action that does not belong to an element"""

    def __init__(self, workflow_action_id=None, *args, **kwargs):
        self.workflow_action_id = workflow_action_id
        super().__init__(
            f"The workflow action {workflow_action_id} does not belong to the element.",
            *args,
            **kwargs,
        )


class BuilderWorkflowActionCannotBeDispatched(Exception):
    """
    Raised when a WorkflowAction is dispatched,
    and it does not have a service related to it.
    """
