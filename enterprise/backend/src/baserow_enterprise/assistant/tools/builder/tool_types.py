from baserow_enterprise.assistant.tools.registries import AssistantToolType


class BuilderToolType(AssistantToolType):
    type = "builder"

    def get_tool_functions(self):
        from .tools import TOOL_FUNCTIONS

        return TOOL_FUNCTIONS

    def get_toolset(self):
        from .tools import builder_toolset

        return builder_toolset

    def get_routing_rules(self):
        from .tools import ROUTING_RULES

        return ROUTING_RULES
