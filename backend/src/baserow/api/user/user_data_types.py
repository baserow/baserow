from typing import List

from baserow.api.user.registries import UserDataType
from baserow.core.feature_flags import get_user_feature_flags
from baserow.core.handler import CoreHandler


class GlobalPermissionsDataType(UserDataType):
    type = "permissions"

    def get_user_data(self, user, request) -> List[dict]:
        """
        Responsible for annotating `User` responses with global permissions
        (which don't relate to a `Workspace`).
        """

        return CoreHandler().get_permissions(user)


class UserFeatureFlagsDataType(UserDataType):
    type = "feature_flags"

    def get_user_data(self, user, request) -> List[str]:
        """
        The feature flags granted to the user.
        """

        return sorted(get_user_feature_flags(user))
