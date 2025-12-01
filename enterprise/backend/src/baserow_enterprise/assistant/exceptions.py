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

    def __init__(self, message_id: str):
        self.message_id = message_id

    def __str__(self):
        return (
            f"Message generation for message ID {self.message_id} has been cancelled."
        )
