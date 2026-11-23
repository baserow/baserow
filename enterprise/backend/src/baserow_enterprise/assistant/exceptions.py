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


class AssistantChatWaitingForApproval(AssistantException):
    """Raised when a message is sent while Kuma waits for an approval decision."""


class AssistantToolApprovalNotPending(AssistantException):
    """Raised when an approval is decided already or isn't waiting in the chat."""
