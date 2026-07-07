from typing import Optional, Tuple

from baserow.contrib.builder.handler import BuilderHandler
from baserow.core.models import Workspace
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
        total_limit = 0
        has_limit = False
        for license_object in License.objects.all():
            if not license_object.valid_payload or not license_object.is_active:
                continue
            if license_object.application_users is None:
                continue
            has_limit = True
            total_limit += license_object.application_users

        if not has_limit:
            return None

        usage = BuilderHandler().aggregate_user_source_counts()
        return usage, total_limit
