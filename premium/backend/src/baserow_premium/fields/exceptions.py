class GenerativeAITypeDoesNotSupportFileField(Exception):
    """
    Raised when file field is not supported for the particular
    generative AI model type.
    """


class AIFieldEmptyPromptError(Exception):
    """
    Raised when the resolved prompt for an AI field is empty, meaning there
    is nothing to send to the model.
    """
