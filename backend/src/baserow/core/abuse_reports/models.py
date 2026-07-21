from django.db import models


class AbuseReport(models.Model):
    """
    An abuse report submitted by an anonymous visitor of a publicly shared resource.
    There is deliberately no foreign key to the reported resource because any
    registered abuse report resource type can be reported, and the report must remain
    available even if the resource is deleted.
    """

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
    # Whether the instance admins were actually notified about this report. Only
    # these reports count towards the notification cooldown window, because a report
    # that didn't notify anyone, for example when there were no active admins yet,
    # must not suppress future notifications.
    admins_notified = models.BooleanField(default=False, db_default=False)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_on"]
        indexes = [
            models.Index(fields=["resource_type", "resource_id", "created_on"]),
        ]
