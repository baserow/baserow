from baserow.core.ai_provider.registries import AIFeatureType


class AIAssistantFeatureType(AIFeatureType):
    type = "ai_assistant"
    requires_default_model = True

    def get_name(self):
        return "AI Assistant"

    def get_description(self):
        return "AI-powered assistant for database, builder, and automation tasks."
