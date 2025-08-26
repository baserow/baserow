from django.db import models


class HistoryStatusChoices(models.TextChoices):
    SUCCESS = "success"
    ERROR = "error"
    DISABLED = "disabled"
    STARTED = "started"
