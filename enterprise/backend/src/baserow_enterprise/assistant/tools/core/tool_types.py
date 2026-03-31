from baserow_enterprise.assistant.tools.registries import AssistantToolType


class CoreToolType(AssistantToolType):
    type = "core"

    def get_tool_functions(self):
        from .tools import TOOL_FUNCTIONS

        return TOOL_FUNCTIONS

    def get_toolset(self):
        from .tools import core_toolset

        return core_toolset
