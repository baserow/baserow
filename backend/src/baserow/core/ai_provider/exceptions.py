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


class InvalidAIProviderSettings(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__(str(errors))
