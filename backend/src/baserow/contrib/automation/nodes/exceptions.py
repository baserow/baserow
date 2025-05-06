class AutomationNodeNotInWorkflow(Exception):
    """When the specified node does not belong to a specific workflow."""

    def __init__(self, node_id=None, *args, **kwargs):
        self.node_id = node_id
        super().__init__(
            f"The node {node_id} does not belong to the workflow.",
            *args,
            **kwargs,
        )


class AutomationNodeDoesNotExist(Exception):
    """When the node doesn't exist."""

    def __init__(self, node_id=None, *args, **kwargs):
        self.node_id = node_id
        super().__init__(
            f"The node {node_id} does not exist.",
            *args,
            **kwargs,
        )
