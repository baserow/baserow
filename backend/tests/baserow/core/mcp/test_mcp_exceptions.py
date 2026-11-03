from rest_framework.exceptions import APIException

from baserow.core.mcp.exceptions import to_mcp_error
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


def test_to_mcp_error_returns_message_of_error_code_detail():
    # Like FeaturesNotAvailableError, which the API renders as an error code and
    # a message.
    class PaymentRequired(APIException):
        status_code = 402

        def __init__(self):
            super().__init__(
                {"error": "ERROR_FEATURE_NOT_AVAILABLE", "detail": "Needs a licence."}
            )

    assert to_mcp_error(PaymentRequired()) == "Needs a licence."


def test_to_mcp_error_reports_improperly_configured_service():
    assert to_mcp_error(ServiceImproperlyConfiguredDispatchException("No field.")) == (
        "Invalid value. No field."
    )
