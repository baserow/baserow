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
# Seconds to wait before retry 1, 2, ... `AUTOMATION_NODE_MAX_RETRIES`.
AUTOMATION_NODE_RETRY_COUNTDOWNS = (1, 1, 2, 3, 6)

# The node fields that make up its error policy. Only action node types accept
# them; triggers never fail during a run, so they keep the defaults.
ERROR_POLICY_FIELDS = [
    "on_failure",
    "max_retries",
    "retry_condition",
]

# A node that suspended itself (e.g. a "Wait" node) is resumed by a Celery task
# scheduled with a countdown. The broker redelivers a message that stays unacked
# longer than its visibility timeout (3600 s by default with Redis), and a
# countdown message is unacked until it runs, so a long wait is cut into chunks
# of at most this many seconds: the resume task wakes up, and reschedules itself
# while the node is not due. Must stay well below the visibility timeout.
AUTOMATION_PENDING_NODE_COUNTDOWN_CHUNK_SECONDS = 600
# A waiting node whose resume is overdue by more than this many seconds lost its
# resume task (the broker lost the message): the periodic cleanup resumes it. A
# live task is never this late: visibility timeout, plus one chunk, plus margin.
AUTOMATION_PENDING_NODE_STALE_SECONDS = 3600 + 600 + 300
