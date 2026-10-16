from django.db import models

from baserow.core.models import Application


class AgentApplication(Application):
    """A single reusable agent, owned and managed as a workspace application."""

    instructions = models.TextField(blank=True, default="", db_default="")
    provider_type = models.CharField(
        max_length=255, null=True, blank=True, db_default=None
    )
    model_identifier = models.CharField(
        max_length=255, null=True, blank=True, db_default=None
    )
