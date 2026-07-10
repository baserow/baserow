from typing import Optional

from baserow.contrib.builder.handler import BuilderHandler
from baserow.core.models import Workspace
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.models import UserSource


class ApplicationUserUsageHandler:
    def aggregate_user_source_counts(
        self,
        workspace: Optional[Workspace] = None,
    ) -> int:
        """
        The builder implementation of the `UserSourceHandler.aggregate_user_counts`
        method, we need it to only count user sources in published applications.

        :param workspace: If provided, only count user sources in published
            applications within this workspace.
        :return: The total number of user sources in published applications.
        """

        queryset = UserSourceHandler().get_user_sources(
            base_queryset=UserSource.objects.filter(
                application__in=BuilderHandler().get_published_applications(workspace)
            )
        )
        return UserSourceHandler().aggregate_user_counts(workspace, queryset)
