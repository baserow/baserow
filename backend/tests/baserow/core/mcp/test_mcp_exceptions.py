from rest_framework.exceptions import APIException

from baserow.core.mcp.exceptions import ToolInputError, to_mcp_error
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)


def test_to_mcp_error_returns_detail_of_client_api_exception():
    class PaymentRequired(APIException):
        status_code = 402
        default_detail = "The feature is not available."

    assert to_mcp_error(PaymentRequired()) == "The feature is not available."


def test_to_mcp_error_hides_server_api_exception():
    assert to_mcp_error(APIException()) is None


class PaymentRequired(APIException):
    # Rendered by the API as an error code and a message.
    status_code = 402

    def __init__(self, error):
        super().__init__({"error": error, "detail": "From the API."})


def test_to_mcp_error_returns_message_of_error_code_detail():
    error = PaymentRequired("ERROR_APPLICATION_USER_LIMIT_REACHED")

    assert to_mcp_error(error) == "From the API."


def test_to_mcp_error_says_a_licence_is_missing():
    error = PaymentRequired("ERROR_FEATURE_NOT_AVAILABLE")

    assert "needs a licence" in to_mcp_error(error)


def test_to_mcp_error_reports_improperly_configured_service():
    assert to_mcp_error(ServiceImproperlyConfiguredDispatchException("No field.")) == (
        "Invalid value. No field."
    )


def test_to_mcp_error_gives_the_model_the_hint_after_the_message():
    error = ToolInputError("Field 9 isn't in this table.", hint="Use 3, 7.")

    assert to_mcp_error(error) == "Field 9 isn't in this table. Use 3, 7."
    assert to_mcp_error(ToolInputError("No hint.")) == "No hint."
