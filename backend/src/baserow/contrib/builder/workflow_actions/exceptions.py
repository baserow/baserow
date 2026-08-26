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


class InvalidWorkflowActionEvent(Exception):
    """
    Raised when a workflow action is created or updated with an `event` that the
    element it is attached to can never fire.
    """

    def __init__(
        self,
        event: str,
        valid_events: list[str],
        element_type: str | None = None,
        *args,
        **kwargs,
    ):
        self.event = event
        self.valid_events = valid_events
        self.element_type = element_type
        target = (
            f"the {element_type} element"
            if element_type
            else "a workflow action without an element"
        )
        valid = ", ".join(valid_events) if valid_events else "none"
        super().__init__(
            f"The event '{event}' is not valid for {target}. Valid events: {valid}.",
            *args,
            **kwargs,
        )
