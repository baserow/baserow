from baserow.contrib.automation.exceptions import AutomationError


class AutomationWorkflowHistoryError(AutomationError):
    pass


class AutomationWorkflowHistoryDoesNotExist(AutomationWorkflowHistoryError):
    """When the history entry doesn't exist."""

    def __init__(self, history_id=None, *args, **kwargs):
        self.history_id = history_id
        super().__init__(
            f"The automation workflow history {history_id} does not exist.",
            *args,
            **kwargs,
        )


class AutomationWorkflowHistoryNodeResultDoesNotExist(AutomationWorkflowHistoryError):
    """When the result entry doesn't exist for the given node/history."""


class AutomationNodeHistoryDoesNotExist(AutomationWorkflowHistoryError):
    """When the node history entry doesn't exist."""

    def __init__(self, node_history_id=None, *args, **kwargs):
        self.node_history_id = node_history_id
        super().__init__(
            f"The automation node history {node_history_id} does not exist.",
            *args,
            **kwargs,
        )
