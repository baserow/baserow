from baserow.core.registry import Instance, Registry


class AIAssistantToolType(Instance):
    pass


class AIAssistantToolTypeRegistry(Registry[AIAssistantToolType]):
    pass


ai_assistant_tool_type_registry = AIAssistantToolTypeRegistry()
