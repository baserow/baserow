from typing import Dict, Generator, List, Optional, Set

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db.models import Q, QuerySet

from baserow_premium.license.exceptions import InvalidLicenseError
from baserow_premium.license.models import License
from baserow_premium.license.registries import LicenseType, SeatUsageSummary

from baserow.core.cache import local_cache
from baserow.core.models import Workspace

User = get_user_model()
LICENSE_CACHE_KEY_PREFIX = "license"


class LicensePlugin:
    """
    A collection of methods used to query for what licenses a user has access to and
    hence which features they can use.
    """

    def __init__(self, cache_queries: bool = False):
        self.cache_queries = cache_queries
        self.queried_licenses_per_user = {}

    def user_has_feature(
        self,
        feature: str,
        user: AbstractUser,
        workspace: Workspace,
    ) -> bool:
        """
        Returns if the provided user has a feature enabled for a specific workspace from
        an active license or if they have that feature enabled instance wide and hence
        also for this workspace.

        :param feature: A string identifying a particular feature or set of features
            a license can grant a user.
        :param user: The user to check to see if they have a license active granting
            them the feature.
        :param workspace: The workspace to check to see if the user has the feature for.
        """

        return self.user_has_feature_instance_wide(feature, user) or (
            self._has_license_feature_only_for_specific_workspace(
                feature, user, workspace
            )
        )

    def instance_has_feature(
        self,
        feature: str,
    ) -> bool:
        """
        Checks if the Baserow instance has a particular feature granted by an active
        instance wide license.

        :param feature: The feature to check to see if active. Look for features.py
            files for these constant strings to use.
        :return: True if the feature is enabled globally for all users.
        """

        return any(
            feature in license_type.features
            for license_type in self.get_active_instance_wide_license_types(user=None)
        )

    def workspace_has_feature(self, feature: str, workspace: Workspace) -> bool:
        """
        Checks if the Baserow instance has a particular feature granted by an active
        instance wide license.

        :param feature: The feature to check to see if active. Look for features.py
            files for these constant strings to use.
        :param workspace: The workspace to get workspace wide features for.
        :return: True if the feature is enabled globally for all users.
        """

        return self.instance_has_feature(feature) or any(
            feature in license_type.features
            for license_type in self.get_active_workspace_licenses(workspace)
        )

    def user_has_feature_instance_wide(self, feature: str, user: AbstractUser) -> bool:
        """
        Returns if the provided user has a feature enabled for the entire site,
        and not only for one specific workspace from an active license.

        :param feature: A string identifying a particular feature or set of features
            a license can grant a user.
        :param user: The user to check to see if they have a license active granting
            them the feature.
        """

        return any(
            feature in license_type.features
            for license_type in self.get_active_instance_wide_license_types(user)
        )

    def _has_license_feature_only_for_specific_workspace(
        self, feature: str, user: AbstractUser, workspace: Workspace
    ) -> bool:
        """
        Returns if the provided user has a feature enabled for a specific workspace from
        an active license, but ignoring any instance-wide licenses they might have.

        :param feature: A string identifying a particular feature or set of features
            a license can grant a user.
        :param user: The user to check to see if they have a workspace level license
            active granting them the feature.
        :param workspace: The workspace to check to see if the user has the feature for.
        """

        def _available_features():
            active_licenses = self.get_active_specific_licenses_only_for_workspace(
                user, workspace
            )
            return set().union(*[license.features for license in active_licenses])

        available_features = local_cache.get(
            f"{LICENSE_CACHE_KEY_PREFIX}_features_{workspace.id}_{user.id}",
            _available_features,
        )
        return feature in available_features

    def get_active_instance_wide_license_types(
        self, user: Optional[AbstractUser]
    ) -> Generator[LicenseType, None, None]:
        for available_license in self.get_active_instance_wide_licenses(user):
            yield available_license.license_type

    def get_active_instance_wide_licenses(
        self, user: Optional[User]
    ) -> Generator[License, None, None]:
        """
        For the provided user returns the active licenses they have instance wide.
        If no user is provided then returns any licenses that are globally active for
        every single user in the instance.

        :param user: The user to lookup active instance wide licenses for.
        """

        yield from self._get_active_instance_wide_licenses(
            user.id if user is not None else None
        )

    def _get_active_instance_wide_licenses(
        self, user_id: Optional[int]
    ) -> Generator[License, None, None]:
        if self.cache_queries and user_id in self.queried_licenses_per_user:
            available_licenses = self.queried_licenses_per_user[user_id]
        else:
            available_license_q = Q(cached_untrusted_instance_wide=True)
            if user_id is not None:
                available_license_q |= Q(users__user_id__in=[user_id])

            def _get_available_licenses():
                return License.objects.filter(available_license_q).distinct()

            available_licenses = local_cache.get(
                f"{LICENSE_CACHE_KEY_PREFIX}_{user_id}_instance_wide_licenses",
                _get_available_licenses,
            )

        for available_license in available_licenses:
            try:
                if available_license.is_active:
                    yield available_license
            except InvalidLicenseError:
                pass

        if self.cache_queries:
            self.queried_licenses_per_user[user_id] = available_licenses

    def get_active_specific_licenses_only_for_workspace(
        self, user: AbstractUser, workspace: Workspace
    ) -> Generator[LicenseType, None, None]:
        """
        Generates all the licenses for a specific workspace that a user has. Should not
        return any instance-wide licenses the user has.

        Provided as an overridable hook incase querying for only one specific workspace
        can be optimized. By default just defers to the `get_per_workspace_licenses`
        function.

        :param user: The user to get active licenses in the workspace for.
        :param workspace: The workspace to check to see any specific active licenses are
            enabled for.
        :return: A generator which produces the license types that the user has enabled
            for the workspace.
        """

        per_workspace_licenses = self.get_active_per_workspace_licenses(user)
        for active_license in per_workspace_licenses.get(workspace.id, set()):
            yield active_license

    def get_active_per_workspace_licenses(
        self, user: AbstractUser
    ) -> Dict[int, Set[LicenseType]]:
        """
        For the provided user returns the active licenses they have active per
        workspace. Does not take into account any instance wide licenses the user
        might have and only active licenses for specific workspaces.

        :param user: The user to lookup active per workspace licenses for.
        """

        return {}

    def get_active_workspace_licenses(
        self,
        workspace: Workspace,
    ) -> Generator[LicenseType, None, None]:
        """
        For the provided workspace returns which licenses are active.
        """

        return
        yield

    def get_workspaces_to_periodically_update_seats_taken_for(self) -> QuerySet:
        """
        Should return a queryset of all the workspaces that should have their
        seats_taken attribute periodically updated by the nightly usage job when
        enabled.
        """

        return Workspace.objects.filter(template__isnull=True)

    def get_seat_usage_for_workspace(
        self, workspace: Workspace
    ) -> Optional[SeatUsageSummary]:
        """
        Returns for the most important (the license type with the highest order) active
        license type on a workspace the seat usage summary for that workspace.

        If it doesn't make sense for that license type to have usage at the workspace
        level None will be returned.
        """

        sorted_licenses = sorted(
            self.get_active_instance_wide_license_types(user=None),
            key=lambda t: t.order,
            reverse=True,
        )
        if sorted_licenses:
            most_relevant_license_type = sorted_licenses[0]
            return most_relevant_license_type.get_seat_usage_summary_for_workspace(
                workspace
            )
        else:
            return None

    def get_seat_usage_for_specific_users(
        self, user_ids: List[int]
    ) -> Optional[SeatUsageSummary]:
        """
        Returns for the most important (the license type with the highest order) active
        license type for specific users the seat usage.

        If it doesn't make sense for that license type to have usage at the user level
        None will be returned.
        """

        sorted_licenses = sorted(
            self.get_active_instance_wide_license_types(user=None),
            key=lambda t: t.order,
            reverse=True,
        )
        if sorted_licenses:
            most_relevant_license_type = sorted_licenses[0]
            return most_relevant_license_type.get_seat_usage_summary_for_specific_users(
                user_ids
            )
        else:
            return None
