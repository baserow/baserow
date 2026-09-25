import json

import pytest
from pydantic_ai.exceptions import ContentFilterError, ModelHTTPError

from baserow.core.generative_ai.exceptions import get_user_friendly_error_message


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
