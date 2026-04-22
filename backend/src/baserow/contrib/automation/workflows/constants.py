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
