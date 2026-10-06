from typing import Dict, Iterable, Iterator, Optional, Tuple

from django.db.models import QuerySet

from baserow.contrib.builder.handler import BuilderHandler
from baserow.core.models import Workspace
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.registries import UserSourceType


class ApplicationUserUsageHandler:
    def get_user_sources_in_published_applications(
        self, workspace: Optional[Workspace] = None
    ) -> QuerySet[UserSource]:
        """
        Returns the generic user sources that count towards the application user
        quota: the ones of published applications, as those are the only ones
        application users can log in to.

        :param workspace: If provided, only the user sources in published
            applications within this workspace.
        :return: A queryset of generic user sources.
        """

        return UserSource.objects.filter(
            application__in=BuilderHandler().get_published_applications(workspace)
        )

    def _get_user_source_counts(
        self, user_sources: Iterable[UserSource]
    ) -> Iterator[Tuple[UserSource, int]]:
        """
        Yields every given specific user source that has a user count, i.e. the
        configured ones, together with that count.

        :param user_sources: The specific user sources to count the users of.
        :return: An iterator of `(user_source, count)` tuples.
        """

        for user_source in user_sources:
            user_source_type: UserSourceType = user_source.get_type()  # type: ignore
            user_source_count = user_source_type.get_user_count(user_source)
            if user_source_count is not None:
                yield user_source, user_source_count.count

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

        user_sources = UserSourceHandler().get_user_sources(
            base_queryset=self.get_user_sources_in_published_applications(workspace)
        )
        return sum(count for _, count in self._get_user_source_counts(user_sources))

    def aggregate_user_source_counts_per_workspace(
        self, workspaces: Iterable[Workspace]
    ) -> Dict[int, int]:
        """
        Returns the application user usage of every given workspace, resolved in a
        single pass over the user sources in the published applications of all of
        them. This is the bulk counterpart of `aggregate_user_source_counts` for
        callers that need the usage of many workspaces at once, like the periodic
        application user limit check, which would otherwise query the user sources
        once per workspace.

        :param workspaces: The workspaces to resolve the usage of.
        :return: A `{workspace_id: usage}` dict with an entry for every given
            workspace, `0` for the ones without application users.
        """

        usage_per_workspace = {workspace.id: 0 for workspace in workspaces}
        user_sources = UserSourceHandler().get_user_sources(
            base_queryset=self.get_user_sources_in_published_applications().filter(
                application__workspace_id__in=usage_per_workspace.keys()
            )
        )
        for user_source, count in self._get_user_source_counts(user_sources):
            # The application is selected together with the user source, so this
            # doesn't query.
            usage_per_workspace[user_source.application.workspace_id] += count

        return usage_per_workspace
