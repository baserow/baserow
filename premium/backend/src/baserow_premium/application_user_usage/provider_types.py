from typing import TYPE_CHECKING, Optional, Tuple

from baserow.contrib.builder.handler import BuilderHandler
from baserow.core.models import Workspace
from baserow_premium.application_user_usage.registries import (
    ApplicationUserUsageProviderType,
)
from baserow_premium.license.models import License

if TYPE_CHECKING:
    from baserow.core.user_sources.models import UserSource


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

        usage = BuilderHandler().aggregate_user_source_counts()
        return usage, total_limit

    def is_over_login_limit(self, user_source: "UserSource", user) -> Optional[bool]:
        """
        TODO: Returns None for now for these reasons:

        1. Not yet implemented. This is eventually how we hard-block logins on
            self-hosted. But we first need to decide, within the instance-wide
            scope, how we compute the total count across all user sources (not
            the per-source position the SaaS uses).
        2. Can we have unlicensed self-hosted installs and is Application users
            a core feature? I.e. an instance with no license (or a pre v1.32
            license without application_users). If yes, then we have to return
            None to not block logins.
        """

        return None
