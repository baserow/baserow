class AutomationWorkflowDoesNotExist(Exception):
    """When the AutomationWorkflow doesn't exist."""


class AutomationWorkflowNotInAutomation(Exception):
    """When the specified workflow does not belong to a specific automation."""


class AutomationWorkflowNameNotUnique(Exception):
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


class AutomationWorkflowDoesNotExist(Exception):
    """When the workflow doesn't exist."""
