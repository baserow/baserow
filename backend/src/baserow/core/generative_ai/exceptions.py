from baserow.core.exceptions import InstanceTypeDoesNotExist


class GenerativeAITypeDoesNotExist(InstanceTypeDoesNotExist):
    """Raised when trying to get a generative AI type that does not exist."""


class ModelDoesNotBelongToType(Exception):
    """Raised when trying to get a model that does not belong to the type."""

    def __init__(self, model_name, *args, **kwargs):
        self.model_name = model_name
        super().__init__(*args, **kwargs)


class GenerativeAIPromptError(Exception):
    """Raised when an error occurs while prompting the model."""
