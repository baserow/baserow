from baserow_premium.license.features import PREMIUM
from baserow_premium.license.models import License, LicenseUser
from baserow_premium.license.registries import LicenseType, SeatUsageSummary

from baserow.core.models import User


class PremiumLicenseType(LicenseType):
    type = "premium"
    order = 10
    features = [PREMIUM]

    def get_seat_usage_summary(self, license_object: License) -> SeatUsageSummary:
        # The attributes will exist on `license_object` if this method is
        # called at least once by `LicenseSerializer`.
        seats_taken = (
            license_object.seats_taken
            if hasattr(license_object, "seats_taken")
            else license_object.users.all().count()
        )
        total_users = (
            license_object.total_users
            if hasattr(license_object, "total_users")
            else User.objects.count()
        )
        free_users = total_users - seats_taken
        return SeatUsageSummary(
            seats_taken=seats_taken,
            free_users_count=free_users,
        )

    def handle_seat_overflow(self, seats_taken: int, license_object: License):
        # If there are more seats taken than the license allows, we need to
        # remove the active seats that are outside the limit.
        LicenseUser.objects.filter(
            pk__in=license_object.users.all()
            .order_by("pk")
            .values_list("pk")[license_object.seats : seats_taken]
        ).delete()
