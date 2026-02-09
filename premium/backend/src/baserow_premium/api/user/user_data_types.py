from typing import List

from baserow.api.user.registries import UserDataType
from baserow.core.models import Workspace
from baserow.core.registries import plugin_registry
from baserow_premium.license.registries import LicenseType


class ActiveLicensesDataType(UserDataType):
    type = "active_licenses"

    def get_user_data(self, user, request) -> dict:
        """
        Someone who authenticates via the API should know beforehand if the related
        user has active licenses.
        """

        from baserow_premium.plugins import PremiumPlugin

        license_plugin = plugin_registry.get_by_type(PremiumPlugin).get_license_plugin()

        per_workspace_licenses = {
            workspace_id: {license_type.type: True for license_type in license_types}
            for workspace_id, license_types in license_plugin.get_active_per_workspace_licenses(
                user
            ).items()
        }
        instance_wide_licenses = {
            license_type.type: True
            for license_type in license_plugin.get_active_instance_wide_license_types(
                user
            )
        }
        return {
            "instance_wide": instance_wide_licenses,
            "per_workspace": per_workspace_licenses,
        }

    @classmethod
    def realtime_message_to_disable_instancewide_license(
        cls, license_to_disable: LicenseType
    ):
        """
        The message body for a realtime event of type user_data_updated which will
        disable a instance-wide license a user has.
        """

        return cls.realtime_message_to_update_user_data(
            {cls.type: {"instance_wide": {license_to_disable.type: False}}}
        )

    @classmethod
    def realtime_message_to_enable_instancewide_license(
        cls, license_to_enable: LicenseType
    ):
        """
        The message body for a realtime event of type user_data_updated which will
        enable a instance-wide license a user has.
        """

        return cls.realtime_message_to_update_user_data(
            {cls.type: {"instance_wide": {license_to_enable.type: True}}}
        )

    @classmethod
    def realtime_message_to_disable_workspace_license(
        cls, workspace: Workspace, license_to_disable: LicenseType
    ):
        """
        The message body for a realtime event of type user_data_updated which will
        disable a workspace license a user has.
        """

        return cls.realtime_message_to_update_user_data(
            {
                cls.type: {
                    "per_workspace": {workspace.id: {license_to_disable.type: False}}
                }
            }
        )

    @classmethod
    def realtime_message_to_enable_workspace_license(
        cls, workspace: Workspace, license_to_enable: LicenseType
    ):
        """
        The message body for a realtime event of type user_data_updated which will
        enable a workspace license a user has.
        """

        return cls.realtime_message_to_update_user_data(
            {
                cls.type: {
                    "per_workspace": {workspace.id: {license_to_enable.type: True}}
                }
            }
        )

    @classmethod
    def realtime_message_to_disable_all_licenses_from_workspace(
        cls, workspace: Workspace
    ):
        """
        The message body for a realtime event of type user_data_updated which will
        disable all licenses the user got directly for a workspace.
        """

        return cls.realtime_message_to_update_user_data(
            {cls.type: {"per_workspace": {workspace.id: False}}}
        )

    @classmethod
    def realtime_message_to_enable_multiple_workspace_licenses(
        cls, workspace: Workspace, licenses_to_enable: List[LicenseType]
    ):
        """
        The message body for a realtime event of type user_data_updated which will
        grant multiple different licenses from a workspace.
        """

        return cls.realtime_message_to_update_user_data(
            {
                cls.type: {
                    "per_workspace": {
                        workspace.id: {
                            active_license.type: True
                            for active_license in licenses_to_enable
                        }
                    }
                }
            }
        )
