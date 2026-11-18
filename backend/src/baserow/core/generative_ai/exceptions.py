import json
from contextlib import AbstractContextManager
from functools import cache
from typing import Any

import httpx
import httpx2
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

# The statuses that the codes OpenAI sends in an error inside an answer or a stream
# stand for, when it is down or rate limited. Other OpenAI-compatible providers,
# like OpenRouter, send the status itself as the code.
ERROR_CODE_STATUS_CODES = {"server_error": 500, "rate_limit_exceeded": 429}


@cache
def _get_transport_error_types() -> tuple[type[BaseException], ...]:
    # The failed or broken connections the provider SDKs raise or chain. Imported
    # only when an error is checked, because the SDKs are loaded lazily.
    from anthropic import APIConnectionError as AnthropicConnectionError
    from groq import APIConnectionError as GroqConnectionError
    from openai import APIConnectionError as OpenAIConnectionError

    return (
        httpx.TransportError,
        httpx2.TransportError,
        OpenAIConnectionError,
        AnthropicConnectionError,
        GroqConnectionError,
    )


def _get_status_code(exc: BaseException) -> int | None:
    # Google's errors have a `code`, the other SDKs and pydantic-ai a `status_code`.
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        status_code = getattr(exc, "code", None)
    return status_code if isinstance(status_code, int) else None


def _get_body(exc: BaseException) -> Any:
    # Google's errors keep the response in `details`, the other SDKs and
    # pydantic-ai in `body`.
    body = getattr(exc, "body", None)
    return getattr(exc, "details", None) if body is None else body


def _get_error_object(exc: BaseException) -> dict:
    # The `error` object of the body, which can also be a JSON string.
    body = _get_body(exc)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return {}
    error = body.get("error") if isinstance(body, dict) else None
    return error if isinstance(error, dict) else {}


def is_transport_failure(error: BaseException) -> bool:
    """
    A provider can also report a failure inside a 200 answer, without a status, so
    only a failed connection proves the request got no answer.

    :param error: What the model or its SDK raised.
    :return: Whether the connection to the provider failed or broke, according to
        the error or one of its causes.
    """

    return _find_provider_error(error, _get_transport_error_types()) is not None


def is_google_invalid_api_key(error: BaseException) -> bool:
    """
    Google answers an invalid API key with a 400 and names the reason in the body.

    :param error: What the model or the Google SDK raised.
    :return: Whether Google refused the API key.
    """

    if _get_status_code(error) != 400:
        return False
    details = _get_error_object(error).get("details")
    return isinstance(details, list) and any(
        isinstance(detail, dict) and detail.get("reason") == "API_KEY_INVALID"
        for detail in details
    )


def is_xai_invalid_api_key(error: BaseException) -> bool:
    """
    xAI answers an invalid API key with a 400 whose only sign is its message.

    :param error: What the model or the OpenAI SDK raised.
    :return: Whether xAI refused the API key.
    """

    body = _get_body(error)
    return (
        _get_status_code(error) == 400
        and isinstance(body, str)
        and body.startswith("Incorrect API key")
    )


def is_out_of_credits(error: BaseException) -> bool:
    """
    Providers answer a request without credits left with a 402, also as the code of
    an error inside a stream, except Anthropic, which answers a 400 and says so in
    its message.

    :param error: A provider error, see `find_provider_error`.
    :return: Whether the provider account has no credits left.
    """

    status_code = get_provider_status_code(error)
    if status_code == 402:
        return True
    message = _get_error_object(error).get("message")
    return (
        status_code == 400
        and isinstance(message, str)
        and "credit balance is too low" in message
    )


def _is_fault_status(status_code: int) -> bool:
    return status_code in PROVIDER_FAULT_STATUS_CODES or status_code >= 500


def _get_error_code(error: BaseException) -> str | None:
    # The code of an error the provider sent inside an answer or a stream, which has
    # no status. The OpenAI SDK keeps it in `code`, or only in `type` when the code
    # is null, like for a server error, and pydantic-ai puts the code of a failed
    # Responses API answer before its message.
    sdk_error = _find_provider_error(error, get_provider_api_error_types())
    if sdk_error is not None:
        code = getattr(sdk_error, "code", None)
        if code is None:
            code = getattr(sdk_error, "type", None)
        return str(code) if code is not None else None
    code, separator, _ = str(getattr(error, "message", "")).partition(": ")
    return code if separator else None


def get_provider_status_code(error: BaseException) -> int | None:
    """
    :param error: A provider error, see `find_provider_error`.
    :return: The status the provider answered with or, for an error inside an
        answer or a stream, the status its code stands for. None for an error
        without either, like a connection failure.
    """

    status_code = _get_status_code(error)
    if status_code is not None:
        return status_code
    code = _get_error_code(error)
    if code is None:
        return None
    return int(code) if code.isdigit() else ERROR_CODE_STATUS_CODES.get(code)


def _find_provider_error(
    exc: BaseException | None,
    error_types: tuple[type[BaseException], ...],
) -> BaseException | None:
    # The exception or the first of its causes that is one of `error_types`.
    seen = set()
    while exc is not None and id(exc) not in seen:
        if isinstance(exc, error_types):
            return exc
        seen.add(id(exc))
        exc = exc.__cause__
    return None


def find_provider_error(exc: BaseException) -> BaseException | None:
    """
    :param exc: The exception to check, with its causes.
    :return: The first provider error: one of `get_provider_api_error_types`, or
        pydantic-ai's `ModelAPIError`, which it raises from the error of every
        provider.
    """

    return _find_provider_error(exc, (*get_provider_api_error_types(), ModelAPIError))


def is_provider_fault(exc: BaseException) -> bool:
    """
    Whether a request failed because of the provider or its settings rather than
    because of the request Baserow built: an invalid key, no credits, a rate limit,
    a timeout, an unreachable host or a provider server error. A rejected request
    (400, 404, 422), or a response that can't be validated or decoded, is Baserow's
    to fix, so it isn't, except for the 400s Google and xAI answer for an invalid
    key and Anthropic for no credits left. An error without a status, like an error
    inside a stream, is only when the connection failed or its code says the
    provider is down or rate limited.

    :param exc: The exception to check, see `find_provider_error`.
    :return: True when the first provider error found is the provider's fault.
    """

    provider_error = find_provider_error(exc)
    if provider_error is None:
        return False
    if is_out_of_credits(provider_error):
        return True
    status_code = get_provider_status_code(provider_error)
    if status_code is None:
        return is_transport_failure(provider_error)
    return (
        _is_fault_status(status_code)
        or is_google_invalid_api_key(provider_error)
        or is_xai_invalid_api_key(provider_error)
    )


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
