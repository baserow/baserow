from typing import List, Optional

from baserow.contrib.builder.handler import BuilderHandler
from baserow.core.models import Workspace
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.registries import UserSourceType


class ApplicationUserUsageHandler:
    def aggregate_user_source_counts(
        self,
        workspace: Optional[Workspace] = None,
    ) -> int:
        """
        Responsible for returning the sum total of all user counts in the instance.
        Only user sources in published applications are counted, as those are the
        ones which count towards the application user quota.

        :param workspace: If provided, only count user sources in published
            applications within this workspace.
        :return: The total number of user sources in published applications.
        """

        queryset = UserSourceHandler().get_user_sources(
            base_queryset=UserSource.objects.filter(
                application__in=BuilderHandler().get_published_applications(workspace)
            )
        )

        user_source_counts: List[int] = []
        for user_source in queryset:
            user_source_type: UserSourceType = user_source.get_type()  # type: ignore
            user_source_count = user_source_type.get_user_count(user_source)
            if user_source_count is not None:
                user_source_counts.append(user_source_count.count)

        return sum(user_source_counts)
