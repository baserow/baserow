from typing import Optional, Sequence


class WorkflowActionNotInField(Exception):
    """The workflow action does not belong to the given button field."""

    def __init__(self, workflow_action_id: Optional[int] = None, *args, **kwargs):
        self.workflow_action_id = workflow_action_id
        super().__init__(
            f"The workflow action {workflow_action_id} does not belong to the field.",
            *args,
            **kwargs,
        )


class WorkflowActionDispatchInProgress(Exception):
    """A click is already running for this button field and row."""


class WorkflowActionTypeDeactivated(Exception):
    """
    The action type cannot be used here. Carries a reason for the person
    configuring the button.
    """

    def __init__(self, reason: str, *args, **kwargs):
        self.reason = reason
        super().__init__(reason, *args, **kwargs)


class WorkflowActionDispatchError(Exception):
    """An action in the sequence failed. Earlier actions have already run."""

    def __init__(
        self,
        workflow_action_id: int,
        message: str,
        position: int,
        completed: Sequence[int] = (),
        *args,
        **kwargs,
    ):
        self.workflow_action_id = workflow_action_id
        # 1-based place in the field's action list, which the clicker can count
        # in the editor. The id means nothing to them.
        self.position = position
        self.message = message
        # The positions of the actions that ran before this one. They are not
        # rolled back, so the clicker is told rather than left to assume
        # nothing happened. Named rather than counted: a frontend-only action
        # holds a position without running here, so a count would not say
        # which ones ran.
        self.completed = tuple(completed)
        super().__init__(self.detail, *args, **kwargs)

    @property
    def detail(self) -> str:
        if not self.completed:
            return f"Action {self.position} failed: {self.message}"
        *first, last = (str(position) for position in self.completed)
        ran = f"Actions {', '.join(first)} and {last}" if first else f"Action {last}"
        return f"{ran} ran before action {self.position} failed: {self.message}"


class WorkflowActionInvalidIntegration(Exception):
    """
    The integration cannot be attached to this action. Carries a reason for
    the person configuring the button.
    """

    def __init__(self, reason: str, *args, **kwargs):
        self.reason = reason
        super().__init__(reason, *args, **kwargs)
