from typing import Optional

from baserow_premium.license.features import PREMIUM
from baserow_premium.license.models import License
from baserow_premium.license.registries import (
    BuilderUsageSummary,
    LicenseType,
    SeatUsageSummary,
)

from baserow.contrib.builder.handler import BuilderHandler
from baserow.core.models import Workspace
from baserow_enterprise.features import (
    AUDIT_LOG,
    BUILDER_CUSTOM_CSS_JS,
    BUILDER_PAYMENT_ELEMENT,
    BUILDER_PRODUCT_SPECIALIST,
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
        BUILDER_CUSTOM_CSS_JS,
        BUILDER_PAYMENT_ELEMENT,
        BUILDER_PRODUCT_SPECIALIST,
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

    def get_builder_usage_summary(self, obj: License) -> Optional[BuilderUsageSummary]:
        """
        This method is used to calculate the number of application users that are
        being used and how many are remaining.

        :param obj: The License instance.
        :return: A summary of the builder usage.
        """

        application_users_taken = (
            obj.application_users_taken
            if hasattr(obj, "application_users_taken")
            else BuilderHandler().aggregate_user_source_counts()
        )
        return BuilderUsageSummary(
            application_users_taken=application_users_taken,
        )

    def handle_application_user_overflow(
        self, application_users_taken: int, license_object: License
    ):
        # We don't have to do anything because the application user limit
        # is a soft limit?
        pass


class EnterpriseLicenseType(EnterpriseWithoutSupportLicenseType):
    type = "enterprise"
    features = EnterpriseWithoutSupportLicenseType.features + [SUPPORT]
