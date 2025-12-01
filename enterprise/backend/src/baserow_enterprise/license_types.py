from typing import List, Optional

from baserow_premium.license.features import PREMIUM
from baserow_premium.license.models import License
from baserow_premium.license.registries import LicenseType, SeatUsageSummary

from baserow.core.models import Workspace
from baserow_enterprise.features import (
    ADVANCED_WEBHOOKS,
    AUDIT_LOG,
    BUILDER_CUSTOM_CODE,
    BUILDER_FILE_INPUT,
    BUILDER_NO_BRANDING,
    BUILDER_SSO,
    DATA_SYNC,
    DATE_DEPENDENCY,
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

COMMON_ADVANCED_FEATURES = [
    # core
    PREMIUM,
    RBAC,
    TEAMS,
    AUDIT_LOG,
    # database
    DATA_SYNC,
    ADVANCED_WEBHOOKS,
    FIELD_LEVEL_PERMISSIONS,
    DATE_DEPENDENCY,
    # application builder
    BUILDER_SSO,
    BUILDER_NO_BRANDING,
    BUILDER_FILE_INPUT,
    BUILDER_CUSTOM_CODE,
    # only self-hosted
    SSO,
]


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
        *COMMON_ADVANCED_FEATURES,
        SUPPORT,
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

    def get_seat_usage_summary_for_specific_users(
        self, user_ids: List[int]
    ) -> Optional[SeatUsageSummary]:
        return RoleBasedSeatUsageSummaryCalculator.get_seat_usage_for_specific_users(
            user_ids
        )

    def handle_seat_overflow(self, seats_taken: int, license_object: License):
        # We don't have to do anything because the seat limit is a soft limit. This is
        # okay for now because we'll be monitoring the usage manually.
        pass

    def handle_application_user_overflow(
        self, application_users_taken: int, license_object: License
    ):
        # We don't have to do anything because the application user limit is a soft
        # limit. This is okay for now because we'll be monitoring the usage manually.
        pass


class EnterpriseWithoutSupportLicenseType(AdvancedLicenseType):
    type = "enterprise_without_support"
    order = 100
    features = [
        *COMMON_ADVANCED_FEATURES,
        ENTERPRISE_SETTINGS,
        SECURE_FILE_SERVE,
    ]

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
