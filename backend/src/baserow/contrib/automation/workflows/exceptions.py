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


class AutomationWorkflowNameNotUnique(AutomationWorkflowError):
    """When a new workflow's name conflicts an existing name."""

    def __init__(self, name=None, automation_id=None, *args, **kwargs):
        self.name = name
        self.automation_id = automation_id
        super().__init__(
            f"A workflow with the name {name} already exists in the automation with id "
            f"{automation_id}",
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
