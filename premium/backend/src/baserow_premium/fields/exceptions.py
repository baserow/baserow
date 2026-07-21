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


class AIFieldPromptInvalidError(Exception):
    """
    Raised when an AI field's prompt formula is broken (unparseable or references a
    field that no longer exists), so values cannot be generated.
    """
