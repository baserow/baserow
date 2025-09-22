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


class AutomationTriggerModificationDisallowed(AutomationNodeError):
    """
    Raised when trying to create, delete or duplicate a trigger node. There can only
    be one trigger node per workflow, and it is created automatically when the workflow
    is created. Users can only change the trigger node type, not create a new one.
    """


class AutomationNodeNotDeletable(AutomationNodeError):
    """
    Raised when an automation node is not deletable. This can happen if
    the node's type dictates that it cannot be deleted.
    """


class AutomationNodeNotReplaceable(AutomationNodeError):
    """
    Raised when an automation node is not replaceable. This can happen if
    the node's type dictates that it cannot be replaced, or if a trigger
    is being replaced with an action, or vice versa.
    """


class AutomationNodeSimulateDispatchError(AutomationNodeError):
    """Raised when there is an error while simulating a dispatch of a node."""
