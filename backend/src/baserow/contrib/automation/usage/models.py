from django.db import models


class WorkspaceAutomationUsage(models.Model):
    """
    Track the usage of automation workflows for a workspace.

    TODO: this should be periodically cleaned up.
    """

    workspace = models.ForeignKey("core.Workspace", on_delete=models.CASCADE)

    period = models.DateField()

    dispatch_count = models.IntegerField(default=0, db_default=0)

    class Meta:
        unique_together = [["workspace", "period"]]
