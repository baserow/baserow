from baserow_enterprise.assistant.tools.registries import AssistantToolType


class NavigationToolType(AssistantToolType):
    type = "navigation"

    def get_tool_functions(self):
        from .tools import TOOL_FUNCTIONS

        return TOOL_FUNCTIONS

    def get_toolset(self):
        from .tools import navigation_toolset

        return navigation_toolset
