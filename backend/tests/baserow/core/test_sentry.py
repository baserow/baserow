import logging
from unittest.mock import patch

from sentry_sdk.envelope import Envelope

from baserow.core.sentry import (
    ConsoleSentryTransport,
    drop_expected_asyncio_websocket_ping_timeout_events,
    log_sentry_event_to_console,
)


def test_drop_expected_asyncio_websocket_ping_timeout_events():
    event = {"logger": "asyncio"}
    record = logging.makeLogRecord(
        {
            "name": "asyncio",
            "levelno": logging.ERROR,
            "levelname": "ERROR",
            "msg": (
                "ConnectionClosedError exception in shielded future future: "
                "<Future finished exception=ConnectionClosedError(None, "
                "Close(code=<CloseCode.INTERNAL_ERROR: 1011>, reason='keepalive "
                "ping timeout'), None)>"
            ),
        }
    )

    assert (
        drop_expected_asyncio_websocket_ping_timeout_events(
            event, {"log_record": record}
        )
        is None
    )


def test_drop_expected_asyncio_websocket_ping_timeout_events_keeps_other_errors():
    event = {"logger": "asyncio"}
    record = logging.makeLogRecord(
        {
            "name": "asyncio",
            "levelno": logging.ERROR,
            "levelname": "ERROR",
            "msg": "Task exception was never retrieved",
        }
    )

    assert (
        drop_expected_asyncio_websocket_ping_timeout_events(
            event, {"log_record": record}
        )
        == event
    )


@patch("baserow.core.sentry.logger")
def test_log_sentry_event_to_console_logs_exception_with_prefix(mock_logger):
    log_sentry_event_to_console(
        {
            "event_id": "event-123",
            "level": "error",
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": "broken",
                    }
                ]
            },
        }
    )

    mock_logger.error.assert_called_once_with(
        "[SENTRY] [ERROR] [event-123] ValueError: broken"
    )


@patch("baserow.core.sentry.logger")
def test_console_sentry_transport_logs_envelope_payload(mock_logger):
    envelope = Envelope(headers={"event_id": "event-123"})
    envelope.add_event({"event_id": "event-123", "message": "Envelope event"})

    ConsoleSentryTransport().capture_envelope(envelope)

    mock_logger.error.assert_called_once_with(
        "[SENTRY] [ERROR] [event-123] Envelope event"
    )
