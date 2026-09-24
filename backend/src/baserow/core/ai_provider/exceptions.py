class AIProviderDoesNotExist(Exception):
    pass


class AIProviderModelDoesNotExist(Exception):
    pass


class AIProviderTypeNotSupported(Exception):
    pass


class AIProviderTypeAlreadyConfigured(Exception):
    pass


class AIProviderModelAlreadyConfigured(Exception):
    pass


class AIProviderIsReadOnly(Exception):
    pass


class AIProviderModelInUse(Exception):
    def __init__(self, model_identifier, feature_types):
        self.model_identifier = model_identifier
        self.feature_types = feature_types
        super().__init__(model_identifier, feature_types)


class AIProviderFeatureModelNotAvailable(Exception):
    def __init__(self, feature_type, model_id=None):
        self.feature_type = feature_type
        self.model_id = model_id
        super().__init__(feature_type, model_id)


class AIProviderFeatureModeNotAllowed(Exception):
    pass


class AIProviderModelFeatureTypeDoesNotExist(Exception):
    pass


class InvalidAIProviderSettings(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__(str(errors))
