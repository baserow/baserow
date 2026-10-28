from baserow_enterprise.assistant.tools.registries import AssistantToolType


class DashboardToolType(AssistantToolType):
    type = "dashboard"

    def get_tool_functions(self):
        from .tools import TOOL_FUNCTIONS

        return TOOL_FUNCTIONS

    def get_toolset(self):
        from .tools import dashboard_toolset

        return dashboard_toolset
