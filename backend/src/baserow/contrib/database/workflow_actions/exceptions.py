class WorkflowActionNotInField(Exception):
    """The workflow action does not belong to the given button field."""

    def __init__(self, workflow_action_id=None, *args, **kwargs):
        self.workflow_action_id = workflow_action_id
        super().__init__(
            f"The workflow action {workflow_action_id} does not belong to the field.",
            *args,
            **kwargs,
        )
