import abc
import dataclasses
from typing import Dict, List, Optional

from baserow_premium.license.models import License

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
    # How many application users the license allows.
    application_users: int
    # How many application users are remaining.
    application_users_left: int


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

    @abc.abstractmethod
    def handle_seat_overflow(self, seats_taken: int, license_object: License):
        pass

    def get_builder_usage_summary(self, obj: License) -> Optional[BuilderUsageSummary]:
        """
        If it makes sense for a license to have builder usage then it should be
        calculated and returned here.
        If it doesn't make sense for this license type then this should return None.
        """

        return None

    def get_builder_usage_summary_for_workspace(
        self, workspace: Workspace
    ) -> Optional[BuilderUsageSummary]:
        """
        If it makes sense for a workspace to have builder usage, then this should return
        a summary of it. If it doesn't make sense for this license type then this
        should return None.
        """

        return None

    def handle_application_user_overflow(
        self, application_users_taken: int, license_object: License
    ):
        # TODO: send a notification, we are over limit.
        ...


class LicenseTypeRegistry(Registry[LicenseType]):
    name = "license_type"


license_type_registry: LicenseTypeRegistry = LicenseTypeRegistry()
