from django.contrib.auth.models import AbstractUser

from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.models import Workspace
from baserow_enterprise.assistant.tools.registries import AssistantToolType


class AgentToolType(AssistantToolType):
    """Kuma's tools for building, editing and testing Agents."""

    type = "agent"

    def can_use(self, user: AbstractUser, workspace: Workspace) -> bool:
        return feature_flag_is_enabled(FF_AGENT_BUILDER, user=user)

    def get_tool_functions(self):
        from .tools import TOOL_FUNCTIONS

        return TOOL_FUNCTIONS

    def get_toolset(self):
        from .tools import agent_toolset

        return agent_toolset
