from django.db import models

from baserow.core.models import Workspace


class ApplicationUserOverLimit(models.Model):
    """
    Marks a workspace as being over its application user limit since the given
    moment. A record only exists while the workspace is over its limit and is
    deleted again as soon as usage is back within the limit. The `since` timestamp
    drives the grace period (`BASEROW_APPLICATION_USER_LIMIT_GRACE_PERIOD_HOURS`)
    after which logins are refused when the limit is enforced.
    """

    workspace = models.OneToOneField(
        Workspace,
        on_delete=models.CASCADE,
        related_name="application_user_over_limit",
    )
    since = models.DateTimeField(
        help_text="The moment the workspace was first detected to be over its "
        "application user limit.",
    )
