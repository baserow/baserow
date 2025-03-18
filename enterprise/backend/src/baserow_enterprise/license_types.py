from typing import Optional

from baserow_premium.license.features import PREMIUM
from baserow_premium.license.models import License
from baserow_premium.license.registries import LicenseType, SeatUsageSummary

from baserow.core.models import Workspace
from baserow_enterprise.features import (
    ADVANCED_WEBHOOKS,
    AUDIT_LOG,
    BUILDER_SSO,
    CHART_WIDGET,
    DATA_SYNC,
    ENTERPRISE_SETTINGS,
    RBAC,
    SECURE_FILE_SERVE,
    SSO,
    SUPPORT,
    TEAMS,
)
from baserow_enterprise.role.seat_usage_calculator import (
    RoleBasedSeatUsageSummaryCalculator,
)


class EnterpriseWithoutSupportLicenseType(LicenseType):
    type = "enterprise_without_support"
    order = 100
    features = [
        PREMIUM,
        RBAC,
        SSO,
        TEAMS,
        AUDIT_LOG,
        SECURE_FILE_SERVE,
        ENTERPRISE_SETTINGS,
        DATA_SYNC,
        CHART_WIDGET,
        BUILDER_SSO,
        ADVANCED_WEBHOOKS,
    ]
    instance_wide = True
    seats_manually_assigned = False

    def get_seat_usage_summary(
        self, license_object_of_this_type: License
    ) -> SeatUsageSummary:
        return RoleBasedSeatUsageSummaryCalculator.get_seat_usage_for_entire_instance()

    def get_seat_usage_summary_for_workspace(
        self, workspace: Workspace
    ) -> Optional[SeatUsageSummary]:
        return RoleBasedSeatUsageSummaryCalculator.get_seat_usage_for_workspace(
            workspace
        )

    def handle_seat_overflow(self, seats_taken: int, license_object: License):
        # We don't have to do anything because the seat limit is a soft limit.
        pass

    def handle_application_user_overflow(
        self, application_users_taken: int, license_object: License
    ):
        # We don't have to do anything because the application user limit
        # is a soft limit?
        pass


class EnterpriseLicenseType(EnterpriseWithoutSupportLicenseType):
    type = "enterprise"
    features = EnterpriseWithoutSupportLicenseType.features + [SUPPORT]
