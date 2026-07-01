from unittest.mock import MagicMock, patch

from baserow.core.telemetry.telemetry import (
    _set_real_client_ip_on_request_span,
    _setup_django_process_instrumentation,
)


def test_set_real_client_ip_on_request_span_uses_forwarded_for(api_request_factory):
    request = api_request_factory.get(
        "/api/workspaces/",
        REMOTE_ADDR="10.0.0.1",
        HTTP_X_FORWARDED_FOR="203.0.113.50, 70.41.3.18",
    )
    span = MagicMock()
    span.is_recording.return_value = True

    _set_real_client_ip_on_request_span(span, request)

    span.set_attribute.assert_any_call("client.address", "203.0.113.50")
    span.set_attribute.assert_any_call("net.peer.ip", "203.0.113.50")
    assert span.set_attribute.call_count == 2


def test_set_real_client_ip_on_request_span_falls_back_to_real_ip(api_request_factory):
    request = api_request_factory.get(
        "/api/workspaces/",
        REMOTE_ADDR="10.0.0.1",
        HTTP_X_REAL_IP="203.0.113.51",
    )
    span = MagicMock()
    span.is_recording.return_value = True

    _set_real_client_ip_on_request_span(span, request)

    span.set_attribute.assert_any_call("client.address", "203.0.113.51")
    span.set_attribute.assert_any_call("net.peer.ip", "203.0.113.51")
    assert span.set_attribute.call_count == 2


def test_setup_django_process_instrumentation_registers_real_ip_request_hook():
    with patch(
        "opentelemetry.instrumentation.django.DjangoInstrumentor.instrument"
    ) as instrument:
        _setup_django_process_instrumentation()

    instrument.assert_called_once_with(request_hook=_set_real_client_ip_on_request_span)
