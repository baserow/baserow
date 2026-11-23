from django.db import models

# Allows a workflow to triggerable within the next 5 minutes.
ALLOW_TEST_RUN_MINUTES = 5


class WorkflowState(models.TextChoices):
    DRAFT = "draft"
    LIVE = "live"
    PAUSED = "paused"
    DISABLED = "disabled"
    TEST_CLONE = "test_clone"


WORKFLOW_DIRTY_CACHE_KEY = "wa_workflow_dirty_{}"
# How long a test run copy can be reused after it's made, unless the workflow
# changes first. Past that, the next test run makes a new copy.
WORKFLOW_TEST_CLONE_REUSE_SECONDS = 24 * 60 * 60

# The stall sweep resolves at most this many runs per pass, oldest first. A full
# batch means more remain, and the next pass takes them.
STALLED_RUN_SWEEP_BATCH_SIZE = 100
# Distinct from the run timeout messages, so the two cases can be told apart in
# the history.
STALLED_RUN_ERROR = "This run was interrupted before it could finish."
STALLED_RUN_CANCELLED_ERROR = (
    "Cancellation was requested and the run was stopped after being interrupted."
)
