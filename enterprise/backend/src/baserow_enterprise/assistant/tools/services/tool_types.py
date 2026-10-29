from baserow_enterprise.assistant.tools.registries import AssistantToolType


class ServicesToolType(AssistantToolType):
    type = "services"

    def get_tool_functions(self):
        from .tools import TOOL_FUNCTIONS

        return TOOL_FUNCTIONS

    def get_toolset(self):
        from .tools import services_toolset

        return services_toolset
