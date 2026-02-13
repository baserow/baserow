class GenerativeAITypeDoesNotSupportFileField(Exception):
    """
    Raised when file field is not supported for the particular
    generative AI model type.
    """


class AiFieldOutputParserException(Exception):
    """
    Raised when the output from the AI model could not be parsed correctly.
    """
