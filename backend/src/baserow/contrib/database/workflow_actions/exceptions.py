class WorkflowActionNotInField(Exception):
    """The workflow action does not belong to the given button field."""

    def __init__(self, workflow_action_id=None, *args, **kwargs):
        self.workflow_action_id = workflow_action_id
        super().__init__(
            f"The workflow action {workflow_action_id} does not belong to the field.",
            *args,
            **kwargs,
        )


class WorkflowActionDispatchInProgress(Exception):
    """A click is already running for this button field and row."""


class WorkflowActionDispatchError(Exception):
    """An action in the sequence failed. Earlier actions have already run."""

    def __init__(self, workflow_action_id, message, position, *args, **kwargs):
        self.workflow_action_id = workflow_action_id
        # 1-based place in the field's action list, which the clicker can count
        # in the editor. The id means nothing to them.
        self.position = position
        self.message = message
        super().__init__(
            f"Action {position} failed: {message}",
            *args,
            **kwargs,
        )
