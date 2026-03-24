from baserow.core.ai_provider.registries import AIFeatureType


class AIFieldFeatureType(AIFeatureType):
    type = "ai_field"
    requires_default_model = False

    def get_name(self):
        return "AI Field"

    def get_description(self):
        return "Use AI models to generate field values from prompts."
