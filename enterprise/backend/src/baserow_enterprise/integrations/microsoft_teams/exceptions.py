class MicrosoftTeamsPickerError(Exception):
    """
    Listing teams, channels or chats failed.

    :param message: Safe to show: it never repeats what Microsoft answered.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
