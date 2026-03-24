from baserow.core.registry import Instance, Registry

from .exceptions import AIFeatureTypeDoesNotExist


class AIFeatureType(Instance):
    """
    Base class for AI features that can use AI providers.
    Each feature registers itself so the UI can display which models
    support which features.
    """

    # Whether this feature needs a "default model" configured per scope.
    # E.g. AI Assistant needs one; AI Field lets users pick per-field.
    requires_default_model = False

    def get_name(self):
        """Human-readable name, e.g. 'AI Field'."""
        return self.type

    def get_description(self):
        """Short description of the feature."""
        return ""


class AIFeatureTypeRegistry(Registry):
    name = "ai_feature"
    does_not_exist_exception_class = AIFeatureTypeDoesNotExist


ai_feature_type_registry: AIFeatureTypeRegistry = AIFeatureTypeRegistry()
