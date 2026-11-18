import json

import httpx
import openai
import pytest
from google.genai import errors as google_errors
from pydantic_ai.exceptions import ContentFilterError, ModelAPIError, ModelHTTPError

from baserow.core.generative_ai.exceptions import (
    GenerativeAIPromptError,
    get_user_friendly_error_message,
    is_provider_fault,
)
from baserow.test_utils.sentry import make_openai_error


def test_get_user_friendly_error_message_hides_the_model_response_dump():
    exc = ContentFilterError("Content filter triggered.", body='[{"parts": []}]')

    assert get_user_friendly_error_message(exc) == "Content filter triggered."


@pytest.mark.parametrize("encode_as_json", [False, True])
@pytest.mark.parametrize(
    "body",
    [
        {"message": "Rate limit reached."},
        {"error": {"message": "Rate limit reached.", "type": "rate_limit_error"}},
        {"error": "Rate limit reached."},
        {"message": "Rate limit reached.", "error": None},
    ],
)
def test_get_user_friendly_error_message_extracts_the_provider_message(
    body, encode_as_json
):
    exc = ModelHTTPError(
        status_code=429,
        model_name="gpt-4o",
        body=json.dumps(body) if encode_as_json else body,
    )

    assert get_user_friendly_error_message(exc) == "Rate limit reached."


@pytest.mark.parametrize("error", [None, [], ["Overloaded"], 42, False, {}])
def test_get_user_friendly_error_message_handles_unknown_error_shapes(error):
    exc = ModelHTTPError(
        status_code=503,
        model_name="gpt-4o",
        body={"error": error},
    )

    assert get_user_friendly_error_message(exc) == str(exc)


@pytest.mark.parametrize(
    "body", ["Overloaded", '{"unknown": "Overloaded"}', "[null]", "null", "{"]
)
def test_get_user_friendly_error_message_preserves_unrecognized_string_bodies(body):
    exc = ModelHTTPError(status_code=503, model_name="gpt-4o", body=body)

    assert get_user_friendly_error_message(exc) == body


def test_get_user_friendly_error_message_preserves_exceptions_without_a_body():
    exc = ValueError("Invalid model.")

    assert get_user_friendly_error_message(exc) == "Invalid model."


def _raised_from(error, cause):
    try:
        raise error from cause
    except Exception as exc:
        return exc


def _connection_error():
    return openai.APIConnectionError(
        request=httpx.Request("POST", "https://api.openai.com/v1/responses")
    )


@pytest.mark.parametrize(
    "make_error",
    [
        lambda: make_openai_error(401),
        lambda: make_openai_error(403),
        lambda: make_openai_error(429),
        lambda: make_openai_error(503),
        _connection_error,
        lambda: google_errors.ClientError(429, {"error": {}}),
        # How pydantic-ai raises the error of a provider whose SDK error isn't
        # known, like Groq or Mistral.
        lambda: _raised_from(
            ModelHTTPError(status_code=401, model_name="m", body=None),
            RuntimeError("groq.AuthenticationError"),
        ),
        lambda: ModelAPIError(model_name="m", message="Connection reset"),
    ],
)
def test_is_provider_fault_accepts_errors_caused_by_the_provider(make_error):
    error = make_error()

    assert is_provider_fault(error)
    # Like `GenerativeAIModelType.prompt`.
    assert is_provider_fault(_raised_from(GenerativeAIPromptError("x"), error))


@pytest.mark.parametrize(
    "make_error",
    [
        # The provider rejected the request Baserow built.
        lambda: make_openai_error(400),
        lambda: make_openai_error(404),
        lambda: google_errors.ClientError(400, {"error": {}}),
        lambda: _raised_from(
            ModelHTTPError(status_code=422, model_name="m", body=None),
            RuntimeError("mistralai.SDKError"),
        ),
        lambda: TypeError("unexpected keyword argument 'timeout'"),
        lambda: GenerativeAIPromptError("Test error"),
    ],
)
def test_is_provider_fault_rejects_errors_caused_by_baserow(make_error):
    error = make_error()

    assert not is_provider_fault(error)
    assert not is_provider_fault(_raised_from(GenerativeAIPromptError("x"), error))


def test_is_provider_fault_rejects_a_response_that_does_not_validate():
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    error = openai.APIResponseValidationError(
        response=httpx.Response(200, request=request), body=None
    )

    assert not is_provider_fault(error)
