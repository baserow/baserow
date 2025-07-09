from baserow.contrib.automation.exceptions import AutomationError


class AutomationNodeError(AutomationError):
    pass


class AutomationNodeNotInWorkflow(AutomationNodeError):
    """When the specified node does not belong to a specific workflow."""

    def __init__(self, node_id=None, *args, **kwargs):
        self.node_id = node_id
        super().__init__(
            f"The node {node_id} does not belong to the workflow.",
            *args,
            **kwargs,
        )


class AutomationNodeDoesNotExist(AutomationNodeError):
    """When the node doesn't exist."""

    def __init__(self, node_id=None, *args, **kwargs):
        self.node_id = node_id
        super().__init__(
            f"The node {node_id} does not exist.",
            *args,
            **kwargs,
        )


class AutomationNodeBeforeInvalid(Exception):
    """
    Raised when trying to create an automation node `before` another, but it is invalid.
    This can happen if the `before` is a trigger, or if `before.workflow` belongs to a
    different workflow to the one supplied.
    """


class AutomationNodeMisconfiguredService(AutomationNodeError):
    """When the node's service is misconfigured."""

    def __init__(self, node_id=None, *args, **kwargs):
        self.node_id = node_id
        super().__init__(
            f"The node {node_id} has a misconfigured service.",
            *args,
            **kwargs,
        )


class AutomationTriggerModificationDisallowed(AutomationNodeError):
    """
    Raised when trying to create, delete or duplicate a trigger node. There can only
    be one trigger node per workflow, and it is created automatically when the workflow
    is created. Users can only change the trigger node type, not create a new one.
    """


class AutomationNodeTypeNotReplaceable(AutomationNodeError):
    """
    Raised when an API consumer tries to update an automation node with a
    new type, but the source type and update type are irreplaceable. This
    happens, for example, if you try and replace a trigger node with an action.
    """
