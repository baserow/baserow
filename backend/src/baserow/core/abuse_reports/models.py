from django.db import models


class AbuseReport(models.Model):
    resource_type = models.CharField(max_length=255)
    resource_id = models.PositiveIntegerField()
    resource_name = models.CharField(max_length=255)
    workspace = models.ForeignKey(
        "core.Workspace",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    workspace_name = models.CharField(max_length=165, blank=True)
    public_url = models.TextField()
    reporter_name = models.CharField(max_length=150)
    reporter_email = models.EmailField()
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    # Only reports that actually notified the admins count towards the notification
    # cooldown, so that a report that notified nobody can't suppress future ones.
    admins_notified = models.BooleanField(default=False, db_default=False)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_on"]
        indexes = [
            models.Index(fields=["resource_type", "resource_id", "created_on"]),
        ]
