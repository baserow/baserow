class AssistantException(Exception):
    pass


class AssistantChatDoesNotExist(AssistantException):
    pass


class AssistantModelNotSupportedError(AssistantException):
    pass


class AssistantModelDisabledError(AssistantModelNotSupportedError):
    """Raised when Kuma is explicitly disabled for the requested scope."""


class AssistantConfiguredModelNotAvailableError(AssistantModelNotSupportedError):
    """Raised when Kuma's database-selected model cannot serve a request."""


class AssistantChatMessagePredictionDoesNotExist(AssistantException):
    pass


class ServiceFilterGenerationFailed(AssistantException):
    """Raised when the assistant could not produce valid filter changes."""
