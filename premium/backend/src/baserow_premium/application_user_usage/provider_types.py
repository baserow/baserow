from typing import Optional, Tuple

from baserow.core.models import Workspace
from baserow_premium.application_user_usage.handler import ApplicationUserUsageHandler
from baserow_premium.application_user_usage.registries import (
    ApplicationUserUsageProviderType,
)
from baserow_premium.license.models import License


class PremiumApplicationUserUsageProviderType(ApplicationUserUsageProviderType):
    """
    Resolves the instance-wide application user usage and limit from the installed
    licenses. The limit is the sum of the `application_users` of all active licenses
    that define one. Usage is the instance-wide application user count.
    """

    type = "premium_instance_wide"

    # Lower than the SaaS per-workspace provider so that, when both are installed, the
    # per-workspace quota takes precedence.
    order = 10

    def get_usage_and_limit(
        self, workspace: Workspace
    ) -> Optional[Tuple[int, Optional[int]]]:
        """
        Counts the total limit by aggregating all active license limits.
        """

        total_limit = 0
        has_limit = False
        for license_object in License.objects.all():
            if not license_object.valid_payload or not license_object.is_active:
                continue
            if license_object.application_users is None:
                continue
            has_limit = True
            total_limit += license_object.application_users

        # No active license carries an application_users limit, either the
        # install is unlicensed, or its license predates v1.32 and has no
        # application_users field.
        # Either way, no limit is enforced and no notifications fire.
        if not has_limit:
            return None

        usage = ApplicationUserUsageHandler().aggregate_user_source_counts()
        return usage, total_limit

    def is_over_login_limit(self, workspace: Workspace) -> Optional[bool]:
        """
        Returns None so that self-hosted installs never hard-block logins.

        The base implementation blocks every login once the instance-wide
        usage exceeds the summed license limit (get_usage_and_limit() returns None
        for unlicensed or pre v1.32 installs, so those are never blocked).
        """

        return None
