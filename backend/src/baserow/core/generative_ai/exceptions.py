import json
from contextlib import AbstractContextManager

from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior

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


def get_provider_api_error_types() -> tuple[type[Exception], ...]:
    """
    The errors raised when a request fails at the provider, for the provider SDKs
    whose Sentry integration captures client errors before re-raising them: OpenAI
    (also used by the OpenAI-compatible providers), Anthropic and Google. They
    cover an unreachable host, a timeout, an invalid key, a rate limit and every
    error status the provider answers with, 4xx included, so a request rejected by
    the provider is dropped too. That's fine where the error is shown to the user,
    like when testing a model.

    :return: The base error classes of these SDKs. Google doesn't wrap transport
        failures in its own errors, so the `httpx2` transport error is included.
    """

    from anthropic import APIError as AnthropicAPIError
    from google.genai.errors import APIError as GoogleAPIError
    from httpx2 import TransportError as GoogleTransportError
    from openai import APIError as OpenAIAPIError

    return (OpenAIAPIError, AnthropicAPIError, GoogleAPIError, GoogleTransportError)


# The statuses a provider answers when its settings or the provider itself are at
# fault: an invalid key, no credits or access, a timeout, a conflict and a rate
# limit. Server errors (5xx) are too.
PROVIDER_FAULT_STATUS_CODES = frozenset({401, 402, 403, 408, 409, 429})


def _get_status_code(exc: BaseException) -> int | None:
    # Google's errors have a `code`, the other SDKs and pydantic-ai a `status_code`.
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        status_code = getattr(exc, "code", None)
    return status_code if isinstance(status_code, int) else None


def is_provider_fault(exc: BaseException) -> bool:
    """
    Whether a request failed because of the provider or its settings rather than
    because of the request Baserow built: an invalid key, no credits, a rate limit,
    a timeout, an unreachable host or a provider server error. A rejected request
    (400, 404, 422) or a response that doesn't validate is Baserow's to fix, so it
    isn't.

    The causes are checked too, up to the first provider error: one of
    `get_provider_api_error_types`, or pydantic-ai's `ModelAPIError`, which it
    raises from the error of every provider.

    :param exc: The exception to check.
    :return: True when the first provider error found is the provider's fault.
    """

    provider_error_types = (*get_provider_api_error_types(), ModelAPIError)
    seen = set()
    while exc is not None and id(exc) not in seen:
        if isinstance(exc, provider_error_types):
            status_code = _get_status_code(exc)
            return (
                status_code is None
                or status_code in PROVIDER_FAULT_STATUS_CODES
                or status_code >= 500
            )
        seen.add(id(exc))
        exc = exc.__cause__
    return False


def ignore_provider_faults_in_sentry() -> AbstractContextManager[None]:
    """
    Drops the Sentry events of the provider errors captured inside the block that
    are the provider's fault, see `is_provider_fault`. The AI client integrations
    of Sentry capture these before Baserow can show them to the user. Other
    exceptions, including a provider rejecting the request Baserow built, are
    still sent.
    """

    from baserow.core.sentry import ignore_sentry_exceptions_if

    return ignore_sentry_exceptions_if(is_provider_fault)


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
