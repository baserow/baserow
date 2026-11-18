import json

import httpx
import httpx2
import openai
import pytest
from google.genai import errors as google_errors
from pydantic_ai.exceptions import ContentFilterError, ModelAPIError, ModelHTTPError

from baserow.core.generative_ai.exceptions import (
    GenerativeAIPromptError,
    get_user_friendly_error_message,
    is_provider_fault,
)
from baserow.test_utils.sentry import (
    make_openai_connection_error,
    make_openai_error,
    make_openai_stream_error,
    raised_from,
)


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


@pytest.mark.parametrize(
    "make_error",
    [
        lambda: make_openai_error(401),
        lambda: make_openai_error(402),
        lambda: make_openai_error(403),
        lambda: make_openai_error(408),
        lambda: make_openai_error(409),
        lambda: make_openai_error(429),
        lambda: make_openai_error(500),
        lambda: make_openai_error(503),
        make_openai_connection_error,
        lambda: google_errors.ClientError(429, {"error": {}}),
        # Google and Anthropic answer an invalid key or no credits left with a 400.
        lambda: google_errors.ClientError(
            400,
            {
                "error": {
                    "code": 400,
                    "message": "API key not valid. Please pass a valid API key.",
                    "status": "INVALID_ARGUMENT",
                    "details": [{"reason": "API_KEY_INVALID"}],
                }
            },
        ),
        lambda: raised_from(
            ModelHTTPError(
                status_code=400,
                model_name="m",
                body=json.dumps(
                    {
                        "type": "error",
                        "error": {
                            "type": "invalid_request_error",
                            "message": "Your credit balance is too low to access "
                            "the Anthropic API.",
                        },
                    }
                ),
            ),
            RuntimeError("anthropic.BadRequestError"),
        ),
        # How pydantic-ai raises the error of a provider whose SDK error isn't
        # known, like Groq or Mistral.
        lambda: raised_from(
            ModelHTTPError(status_code=401, model_name="m", body=None),
            RuntimeError("groq.AuthenticationError"),
        ),
        lambda: ModelHTTPError(
            status_code=400, model_name="m", body="Incorrect API key provided."
        ),
        # How pydantic-ai raises a connection failure of every provider.
        lambda: raised_from(
            ModelAPIError(model_name="m", message="Connection reset"),
            httpx2.ConnectError("Connection reset"),
        ),
        lambda: raised_from(
            ModelAPIError(model_name="m", message="Timed out"),
            make_openai_connection_error(),
        ),
        # An outage or rate limit reported inside a stream, which has no status:
        # by OpenAI, by OpenRouter with the status as code, and in a failed
        # Responses API answer, as pydantic-ai raises them.
        lambda: make_openai_stream_error("rate_limit_exceeded"),
        lambda: raised_from(
            ModelAPIError(model_name="m", message="Stream failed"),
            make_openai_stream_error("server_error"),
        ),
        lambda: raised_from(
            ModelAPIError(model_name="m", message="Stream failed"),
            make_openai_stream_error(502),
        ),
        lambda: raised_from(
            ModelAPIError(model_name="m", message="Stream failed"),
            make_openai_stream_error(None, error_type="server_error"),
        ),
        lambda: ModelAPIError(model_name="m", message="server_error: Try again."),
        lambda: ModelAPIError(model_name="m", message="rate_limit_exceeded: Slow."),
    ],
)
def test_is_provider_fault_accepts_errors_caused_by_the_provider(make_error):
    error = make_error()

    assert is_provider_fault(error)
    # Like `GenerativeAIModelType.prompt`.
    assert is_provider_fault(raised_from(GenerativeAIPromptError("x"), error))


@pytest.mark.parametrize(
    "make_error",
    [
        # The provider rejected the request Baserow built.
        lambda: make_openai_error(400),
        lambda: make_openai_error(404),
        lambda: make_openai_error(422),
        lambda: google_errors.ClientError(400, {"error": {}}),
        lambda: raised_from(
            ModelHTTPError(status_code=422, model_name="m", body=None),
            RuntimeError("mistralai.SDKError"),
        ),
        # A response that can't be validated, as pydantic-ai raises it, or an
        # error in a stream that isn't an outage or a rate limit.
        lambda: raised_from(
            ModelAPIError(model_name="m", message="Invalid response"),
            openai.APIResponseValidationError(
                response=httpx.Response(
                    200, request=httpx.Request("POST", "https://api.openai.com")
                ),
                body=None,
            ),
        ),
        lambda: ModelAPIError(model_name="m", message="invalid_prompt: flagged"),
        lambda: raised_from(
            ModelAPIError(model_name="m", message="Stream failed"),
            make_openai_stream_error("invalid_prompt"),
        ),
        lambda: make_openai_stream_error(400),
        lambda: make_openai_stream_error(None, error_type="invalid_request_error"),
        lambda: make_openai_stream_error(None),
        lambda: TypeError("unexpected keyword argument 'timeout'"),
        lambda: GenerativeAIPromptError("Test error"),
    ],
)
def test_is_provider_fault_rejects_errors_caused_by_baserow(make_error):
    error = make_error()

    assert not is_provider_fault(error)
    assert not is_provider_fault(raised_from(GenerativeAIPromptError("x"), error))
