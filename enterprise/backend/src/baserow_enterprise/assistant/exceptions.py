class AssistantException(Exception):
    pass


class AssistantChatDoesNotExist(AssistantException):
    pass


class AssistantModelNotSupportedError(AssistantException):
    pass


class AssistantChatMessagePredictionDoesNotExist(AssistantException):
    pass


class AssistantMessageCancelled(AssistantException):
    """Raised when a message generation is cancelled by the user."""

    pass
