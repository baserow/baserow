import json

from pydantic_ai.exceptions import UnexpectedModelBehavior

from baserow.core.exceptions import InstanceTypeDoesNotExist

MODEL_NOT_AVAILABLE_MESSAGE = (
    "The selected AI model is disabled or no longer available."
)


class GenerativeAITypeDoesNotExist(InstanceTypeDoesNotExist):
    """Raised when trying to get a generative AI type that does not exist."""


class ModelDoesNotBelongToType(Exception):
    """Raised when the selected model is not currently available for use."""

    def __init__(self, model_name, *args, **kwargs):
        self.model_name = model_name
        super().__init__(MODEL_NOT_AVAILABLE_MESSAGE, *args, **kwargs)


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

    # Its `.body` is a JSON dump of the whole model response, not a message.
    if isinstance(exc, UnexpectedModelBehavior):
        return exc.message

    # Provider SDKs expose a `.body` dict or string, including JSON-encoded
    # strings, with the actual error message from the provider.
    body = getattr(exc, "body", None)
    parsed_body = body
    if isinstance(body, str):
        try:
            parsed_body = json.loads(body)
        except ValueError:
            pass
    if isinstance(parsed_body, dict):
        msg = parsed_body.get("message")
        if not msg:
            error = parsed_body.get("error")
            if isinstance(error, dict):
                msg = error.get("message")
            elif isinstance(error, str):
                msg = error
        if msg:
            return str(msg)
    if isinstance(body, str) and body:
        return body

    # Fallback: use the full string representation.
    return str(exc)
