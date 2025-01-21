from baserow_premium.license.features import PREMIUM
from baserow_premium.license.models import License, LicenseUser
from baserow_premium.license.registries import LicenseType, SeatUsageSummary

from baserow.core.models import User


class FreeLicenseType(LicenseType):
    type = "free"
    order = 1
    features = []

    def handle_seat_overflow(self, seats_taken: int, license_object: License):
        """
        Free licenses do not have any seats, so we can ignore
        what happens when they overflow.
        """


class PremiumLicenseType(LicenseType):
    type = "premium"
    order = 10
    features = [PREMIUM]

    def get_seat_usage_summary(self, obj: License) -> SeatUsageSummary:
        # The attributes will exist on `obj` if this method is
        # called at least once by `LicenseSerializer`.
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

    def handle_seat_overflow(self, seats_taken: int, license_object: License):
        # If there are more seats taken than the license allows, we need to
        # remove the active seats that are outside the limit.
        LicenseUser.objects.filter(
            pk__in=license_object.users.all()
            .order_by("pk")
            .values_list("pk")[license_object.seats : seats_taken]
        ).delete()
