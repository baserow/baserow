import abc
import dataclasses
from typing import Dict, List, Optional

from baserow_premium.license.models import License

from baserow.contrib.builder.handler import BuilderHandler
from baserow.core.cache import local_cache
from baserow.core.models import Workspace
from baserow.core.registry import Instance, Registry


@dataclasses.dataclass
class SeatUsageSummary:
    seats_taken: int
    free_users_count: int
    num_users_with_highest_role: Dict[str, int] = dataclasses.field(
        default_factory=dict
    )
    highest_role_per_user_id: Dict[int, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class BuilderUsageSummary:
    # How many application users are currently being used.
    application_users_taken: int


class LicenseType(abc.ABC, Instance):
    """
    A type of license that a user can install into Baserow to unlock extra
    functionality. This interface provides the ability for different types of licenses
    to have different behaviour by implementing the various hook methods differently.
    """

    # A list of features that this license type grants.
    features: List[str] = []

    # The higher the order the more features/more expensive the license is. Out of
    # all instance-wide licenses a user might have, the one with the highest order will
    # be shown as a badge in the top of the sidebar in the GUI.
    order: int

    # When true every user in the instance will have this license if it is active
    # regardless of if they are added to a seat on the license or not.
    instance_wide: bool = False

    seats_manually_assigned: bool = True

    def has_feature(self, feature: str) -> bool:
        return feature in self.features

    def get_seat_usage_summary(
        self, license_object_of_this_type: License
    ) -> Optional[SeatUsageSummary]:
        """
        If it makes sense for a license to have seat usage then it should be calculated
        and returned here.
        If it doesn't make sense for this license type then this should return None.
        """

        return None

    def get_seat_usage_summary_for_workspace(
        self, workspace: Workspace
    ) -> Optional[SeatUsageSummary]:
        """
        If it makes sense for a workspace to have seat usage, then this should return
        a summary of it. If it doesn't make sense for this license type then this
        should return None.
        """

        return None

    def get_seat_usage_summary_for_specific_users(
        self, user_ids: List[int]
    ) -> Optional[SeatUsageSummary]:
        """
        If it makes sense for specific user ids to have seat usage, then this should
        return a summary of it. If it doesn't make sense for this license type then this
        should return None.
        """

        return None

    @abc.abstractmethod
    def handle_seat_overflow(self, seats_taken: int, license_object: License):
        pass

    def _calculate_stacked_license_builder_usage(
        self, total_application_users_taken: int
    ) -> dict[str, BuilderUsageSummary]:
        """
        Given the total count of application users used in this instance, this method
        is responsible for returning a `BuilderUsageSummary` for each license in this
        instance.

        The `BuilderUsageSummary.application_users_taken` is the key here. If there are
        multiple stacked licenses, then we will spread the usage of the application
        users across these licenses, filling the `application_users_taken` up, starting
        with the earliest license first.

        :param total_application_users_taken: the total number of application users
            taken in the instance.
        :return: A dictionary of `license_id` to `BuilderUsageSummary`.
        """

        # How many licenses do we have with application users?
        all_licenses = License.objects.all()
        builder_enabled_licenses = [
            license
            for license in all_licenses
            if license.valid_payload  # Ensure the license can be decoded
            and license.application_users is not None  # Restrict to only builder usage
        ]

        # Pluck out all the active licenses. We'll only iterate over these when we
        # spread the builder usage. Any expired licenses will have a usage of 0.
        active_builder_licenses = [
            license for license in builder_enabled_licenses if license.is_active
        ]

        # 1) If there are multiple stacked licenses, and we know that they have
        #    application users assigned to them, then the usage of those application
        #    users will be spread across these licenses. For example:
        #       - LicenseA: application_users=10
        #       - LicenseB: application_users=15
        #       - `total_application_users_taken` = 26
        #   LicenseA will have 10 `application_users_taken`, and LicenseB will have 16
        #   `application_users_taken` (one over limit).
        # 2) If the instance just has a single license, then the usage of the
        #    application users will be the total count.
        # 3) Any expired licenses will report an application user usage of 0.

        usage_per_license = {
            license.license_id: BuilderUsageSummary(application_users_taken=0)
            for license in all_licenses
        }

        # Fill the licenses with the smallest application user quotas first.
        active_builder_licenses.sort(
            key=lambda license: (license.application_users, license.id)
        )
        for index, builder_license in enumerate(active_builder_licenses):
            if index < len(active_builder_licenses) - 1:
                assignable = min(
                    builder_license.application_users, total_application_users_taken
                )
                usage_per_license[builder_license.license_id] = BuilderUsageSummary(
                    application_users_taken=assignable
                )
                total_application_users_taken -= assignable
            else:
                usage_per_license[builder_license.license_id] = BuilderUsageSummary(
                    application_users_taken=total_application_users_taken
                )

        return usage_per_license

    def get_builder_usage_summary(self, license_object: License) -> BuilderUsageSummary:
        """
        This method is used to calculate the number of application users that are
        being used and how many are remaining.

        :param license_object: The License instance.
        :return: A summary of the builder usage.
        """

        # Count the total number of application users in this instance
        total_application_users_taken = BuilderHandler().aggregate_user_source_counts()

        # If there are no user source users, just exit early here.
        if not total_application_users_taken:
            return BuilderUsageSummary(
                application_users_taken=total_application_users_taken
            )

        # Do we have a short-lived cache of the stacked license builder usage?
        cached_stacked_summary = local_cache.get(
            "stacked_instance_builder_license_usage",
            lambda: self._calculate_stacked_license_builder_usage(
                total_application_users_taken
            ),
        )

        return cached_stacked_summary[license_object.license_id]

    def get_builder_usage_summary_for_workspace(
        self, workspace: Workspace
    ) -> Optional[BuilderUsageSummary]:
        """
        This method is used to calculate the number of external users that are being
        used in this workspace and how many are remaining.

        :param workspace: The workspace we are calculating the builder usage for.
        :return: A summary of the builder usage.
        """

        from baserow.contrib.builder.handler import BuilderHandler

        return BuilderUsageSummary(
            application_users_taken=BuilderHandler().aggregate_user_source_counts(
                workspace
            )
        )

    def handle_application_user_overflow(
        self, application_users_taken: int, license_object: License
    ):
        # TODO: send a notification, we are over limit.
        ...


class LicenseTypeRegistry(Registry[LicenseType]):
    name = "license_type"


license_type_registry: LicenseTypeRegistry = LicenseTypeRegistry()
