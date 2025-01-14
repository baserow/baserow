from typing import Optional

from baserow_premium.license.features import PREMIUM
from baserow_premium.license.models import License, LicenseUser
from baserow_premium.license.registries import (
    BuilderUsageSummary,
    LicenseType,
    SeatUsageSummary,
)

from baserow.contrib.builder.handler import BuilderHandler
from baserow.core.models import User


class PremiumLicenseType(LicenseType):
    type = "premium"
    order = 10
    features = [PREMIUM]

    def get_seat_usage_summary(self, obj: License) -> SeatUsageSummary:
        seats_taken = (
            obj.seats_taken if hasattr(obj, "seats_taken") else obj.users.all().count()
        )
        total_users = (
            obj.total_users if hasattr(obj, "total_users") else User.objects.count()
        )
        free_users = total_users - seats_taken
        return SeatUsageSummary(
            seats_taken=seats_taken,
            free_users_count=free_users,
        )

    def get_builder_usage_summary(
        self, license_object_of_this_type: License
    ) -> Optional[BuilderUsageSummary]:
        external_users_taken = BuilderHandler().aggregate_user_source_counts()
        external_users_licensed = (
            license_object_of_this_type.external_users
            if license_object_of_this_type.external_users is not None
            else 0
        )
        external_users_remaining = external_users_licensed - external_users_taken
        return BuilderUsageSummary(
            page_views_generated=0,
            external_users_taken=external_users_taken,
            external_users_licensed=external_users_licensed,
            external_users_remaining=external_users_remaining,
        )

    def handle_seat_overflow(self, seats_taken: int, license_object: License):
        # If there are more seats taken than the license allows, we need to
        # remove the active seats that are outside the limit.
        LicenseUser.objects.filter(
            pk__in=license_object.users.all()
            .order_by("pk")
            .values_list("pk")[license_object.seats : seats_taken]
        ).delete()

    def handle_external_user_overflow(
        self, external_users_taken: int, license_object: License
    ):
        # TODO: send a notification, we are over limit.
        ...
