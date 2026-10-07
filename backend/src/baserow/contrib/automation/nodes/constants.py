from django.db import models


class AutomationNodeOnFailure(models.TextChoices):
    """
    What the runner does when a dispatch of the node fails.
    """

    # The node and the run are marked as errored and nothing else runs.
    STOP = "stop"
    # The node is dispatched again, up to `max_retries` times, before the run
    # is marked as errored.
    RETRY = "retry"


AUTOMATION_NODE_MIN_RETRIES = 1
AUTOMATION_NODE_MAX_RETRIES = 5
AUTOMATION_NODE_DEFAULT_RETRIES = 2

# The node fields that make up its error policy. Only action node types accept
# them; triggers never fail during a run, so they keep the defaults.
ERROR_POLICY_FIELDS = [
    "on_failure",
    "max_retries",
    "retry_on_failure",
    "retry_on_condition",
    "retry_condition",
]
