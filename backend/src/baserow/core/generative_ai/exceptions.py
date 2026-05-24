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


def get_user_friendly_error_message(exc: Exception) -> str:
    """
    Extract a concise, user-facing message from a provider SDK exception.

    Provider SDKs (OpenAI, Anthropic, Mistral) include metadata like
    status_code and model_name in their ``__str__`` output. Users only
    care about the human-readable body/message part.

    :param exc: The exception raised by the provider SDK.
    :return: A concise error message suitable for displaying to users.
    """

    # OpenAI / Anthropic APIStatusError exposes a `.body` dict or string
    # with the actual error message from the provider.
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        msg = body.get("message") or body.get("error", {}).get("message")
        if msg:
            return str(msg)
    if isinstance(body, str) and body:
        return body

    # Fallback: use the full string representation.
    return str(exc)
