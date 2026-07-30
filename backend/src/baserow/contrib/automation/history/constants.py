from django.db import models


class HistoryStatusChoices(models.TextChoices):
    SUCCESS = "success"
    ERROR = "error"
    DISABLED = "disabled"
    STARTED = "started"
    # The node ran without doing anything, e.g. a "Go to node" whose
    # condition resolved to false, so no jump was followed.
    SKIPPED = "skipped"
