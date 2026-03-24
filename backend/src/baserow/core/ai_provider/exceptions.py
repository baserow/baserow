class AIProviderDoesNotExist(Exception):
    """Raised when the requested AI provider config does not exist."""


class AIProviderModelDoesNotExist(Exception):
    """Raised when the requested AI provider model does not exist."""


class AIFeatureTypeDoesNotExist(Exception):
    """Raised when the requested AI feature type does not exist in the registry."""


class AIProviderTestFailed(Exception):
    """Raised when testing an AI provider model connection fails."""

    def __init__(self, message=""):
        self.message = message
        super().__init__(message)
