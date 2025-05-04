from typing import Optional

from baserow_premium.license.features import PREMIUM
from baserow_premium.license.models import License
from baserow_premium.license.registries import LicenseType, SeatUsageSummary

from baserow.core.models import Workspace
from baserow_enterprise.features import (
    ADVANCED_WEBHOOKS,
    AUDIT_LOG,
    BUILDER_FILE_INPUT,
    BUILDER_NO_BRANDING,
    BUILDER_SSO,
    DATA_SYNC,
    ENTERPRISE_SETTINGS,
    FIELD_LEVEL_PERMISSIONS,
    RBAC,
    SECURE_FILE_SERVE,
    SSO,
    SUPPORT,
    TEAMS,
)
from baserow_enterprise.role.seat_usage_calculator import (
    RoleBasedSeatUsageSummaryCalculator,
)


class AdvancedLicenseType(LicenseType):
    """
    The advanced plan is similar to the enterprise plan. The main difference is that it
    doesn't allow branding and secure file serving. Other than that it includes all
    enterprise features. The seat limit is also enforced because it can be bought self
    served.
    """

    type = "advanced"
    order = 75
    features = [
        PREMIUM,
        RBAC,
        SSO,
        TEAMS,
        AUDIT_LOG,
        DATA_SYNC,
        BUILDER_SSO,
        BUILDER_NO_BRANDING,
        ADVANCED_WEBHOOKS,
        FIELD_LEVEL_PERMISSIONS,
        BUILDER_FILE_INPUT,
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
        # @TODO prevent the instance from inviting more users when over limit for a
        #  certain amount of time.
        pass

    def handle_application_user_overflow(
        self, application_users_taken: int, license_object: License
    ):
        # We don't have to do anything because the application user limit is a soft
        # limit.
        pass


class EnterpriseWithoutSupportLicenseType(AdvancedLicenseType):
    type = "enterprise_without_support"
    order = 100
    features = AdvancedLicenseType.features + [SECURE_FILE_SERVE, ENTERPRISE_SETTINGS]

    def handle_seat_overflow(self, seats_taken: int, license_object: License):
        # We don't have to do anything because the seat limit is a soft limit.
        pass

    def handle_application_user_overflow(
        self, application_users_taken: int, license_object: License
    ):
        # We don't have to do anything because the application user limit is a soft
        # limit.
        pass


class EnterpriseLicenseType(EnterpriseWithoutSupportLicenseType):
    type = "enterprise"
    order = 101
    features = EnterpriseWithoutSupportLicenseType.features + [SUPPORT]
