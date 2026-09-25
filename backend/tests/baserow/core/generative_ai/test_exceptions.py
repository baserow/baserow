from pydantic_ai.exceptions import ContentFilterError, ModelHTTPError

from baserow.core.generative_ai.exceptions import get_user_friendly_error_message


def test_get_user_friendly_error_message_hides_the_model_response_dump():
    exc = ContentFilterError("Content filter triggered.", body='[{"parts": []}]')

    assert get_user_friendly_error_message(exc) == "Content filter triggered."


def test_get_user_friendly_error_message_keeps_the_provider_error_body():
    exc = ModelHTTPError(
        status_code=429,
        model_name="gpt-4o",
        body={"message": "Rate limit reached."},
    )

    assert get_user_friendly_error_message(exc) == "Rate limit reached."
