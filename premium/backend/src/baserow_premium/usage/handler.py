from datetime import datetime, timezone
from typing import Optional

from baserow.core.models import Workspace
from baserow.core.registries import plugin_registry
from baserow.core.utils import grouper
from baserow_premium.license.plugin import LicensePlugin
from baserow_premium.plugins import PremiumPlugin


class PremiumUsageHandler:
    @classmethod
    def calculate_per_workspace_seats_taken(cls) -> int:
        """
        Calculates the paid number of seats per workspace for workspaces with
        licenses that can have seats per specific workspace.

        :return: The amount of workspaces that have been updated.
        """

        count, chunk_size = 0, 256

        cached_license_plugin = plugin_registry.get_by_type(
            PremiumPlugin
        ).get_license_plugin(cache_queries=True)

        workspaces_queryset = cached_license_plugin.get_workspaces_to_periodically_update_seats_taken_for().iterator(
            chunk_size=chunk_size
        )

        for workspaces in grouper(chunk_size, workspaces_queryset):
            now = datetime.now(tz=timezone.utc)
            for workspace in workspaces:
                workspace.seats_taken = cls.calculate_seats_taken_for_workspace(
                    cached_license_plugin, workspace
                )
                workspace.seats_taken_updated_at = now

            Workspace.objects.bulk_update(
                workspaces,
                ["seats_taken", "seats_taken_updated_at"],
            )
            count += len(workspaces)

        return count

    @classmethod
    def calculate_seats_taken_for_workspace(
        cls, license_plugin: LicensePlugin, workspace: Workspace
    ) -> Optional[int]:
        """
        Returns the number of users with seats taken
        workspace cannot have any paid roles then None will be returned.

        :param license_plugin: The license plugin to get usage with.
        :param workspace: The workspace to count paid roles per user for.
        :return: The number of users with a paid role or None if users cannot have
            paid roles in this workspace.
        """

        usage = license_plugin.get_seat_usage_for_workspace(workspace)

        if usage:
            return usage.seats_taken
        else:
            return None
