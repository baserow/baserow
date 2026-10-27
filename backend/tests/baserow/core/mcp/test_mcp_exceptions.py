from rest_framework.exceptions import APIException

from baserow.contrib.dashboard.data_sources.exceptions import (
    DashboardDataSourceImproperlyConfigured,
)
from baserow.contrib.dashboard.widgets.exceptions import WidgetImproperlyConfigured
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


def test_to_mcp_error_reports_improperly_configured_widget():
    assert to_mcp_error(WidgetImproperlyConfigured("No series.")) == (
        "Invalid value. No series."
    )


def test_to_mcp_error_reports_improperly_configured_data_source():
    assert to_mcp_error(DashboardDataSourceImproperlyConfigured("No field.")) == (
        "Invalid value. No field."
    )
    assert to_mcp_error(ServiceImproperlyConfiguredDispatchException("No field.")) == (
        "Invalid value. No field."
    )
