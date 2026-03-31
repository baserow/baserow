from baserow.contrib.automation.exceptions import AutomationError


class AutomationWorkflowError(AutomationError):
    pass


class AutomationWorkflowNotInAutomation(AutomationWorkflowError):
    """When the specified workflow does not belong to a specific automation."""

    def __init__(self, workflow_id=None, *args, **kwargs):
        self.workflow_id = workflow_id
        super().__init__(
            f"The workflow {workflow_id} does not belong to the automation.",
            *args,
            **kwargs,
        )


class AutomationWorkflowDoesNotExist(AutomationWorkflowError):
    """When the workflow doesn't exist."""

    pass


class AutomationWorkflowBeforeRunError(AutomationWorkflowError):
    pass


class AutomationWorkflowRateLimited(AutomationWorkflowBeforeRunError):
    """When the workflow is run too many times in a certain window."""

    pass


class AutomationWorkflowTooManyErrors(AutomationWorkflowBeforeRunError):
    """When the workflow has too many consecutive errors."""

    pass
