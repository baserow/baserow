from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.contrib.agent.models import AgentApplication
from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.models import Workspace
from baserow.core.search.data_types import SearchContext
from baserow.core.search.search_types import ApplicationSearchType


class AgentSearchType(ApplicationSearchType):
    type = "agent"
    name = "Agent"
    model_class = AgentApplication
    priority = 5

    def get_search_queryset(
        self, user: AbstractUser, workspace: Workspace, context: SearchContext
    ) -> QuerySet:
        queryset = super().get_search_queryset(user, workspace, context)
        # Agents are hidden from users without the grant, so search must not list them.
        if not feature_flag_is_enabled(FF_AGENT_BUILDER, user=user):
            return queryset.none()
        return queryset
