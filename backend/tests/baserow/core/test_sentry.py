import logging
import os
import subprocess
import sys
from unittest.mock import patch

import pytest
from sentry_sdk.envelope import Envelope

from baserow.core.sentry import (
    drop_expected_asyncio_websocket_disconnect_events,
    log_sentry_event_to_console,
)
from baserow.core.sentry_transport import ConsoleSentryTransport


def test_sentry_sdk_is_not_loaded_when_sentry_is_disabled():
    code = """
import sys
from types import SimpleNamespace

from django.conf import settings

settings.configure(SENTRY_DSN="")

from baserow.core.sentry import setup_user_in_sentry

setup_user_in_sentry(SimpleNamespace(id=1))
assert not any(
    module == "sentry_sdk" or module.startswith("sentry_sdk.")
    for module in sys.modules
)
"""
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}

    subprocess.run(  # noqa: S603 - only the current interpreter runs fixed test code.
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )


def _asyncio_record(msg: str, name: str = "asyncio") -> logging.LogRecord:
    return logging.makeLogRecord(
        {"name": name, "levelno": logging.ERROR, "levelname": "ERROR", "msg": msg}
    )


# Benign websocket-close log records whose rate is tracked by the
# baserow.websocket_disconnects metric, so they are dropped.
DROPPED_MESSAGES = [
    # 1011 keepalive ping timeout (idle/slow client or starved event loop).
    (
        "ConnectionClosedError exception in shielded future future: "
        "<Future finished exception=ConnectionClosedError(None, "
        "Close(code=<CloseCode.INTERNAL_ERROR: 1011>, reason='keepalive ping "
        "timeout'), None)>"
    ),
    # 1001 going away with a reason (e.g. a proxy restarting).
    (
        "ConnectionClosedOK exception in shielded future future: <Future "
        "finished exception=ConnectionClosedOK(Close(code=1001, reason="
        "'proxy restarting'), Close(code=1001, reason='proxy restarting'), True)>"
    ),
    # 1005 no status received.
    (
        "ConnectionClosedOK exception in shielded future future: <Future "
        "finished exception=ConnectionClosedOK(Close(code=1005, reason=''), "
        "Close(code=1005, reason=''), True)>"
    ),
]

# Messages that must still be reported because they can signal real problems.
KEPT_MESSAGES = [
    # 1006 abnormal closure also flags mass disconnects (OOM/restart), so keep it.
    (
        "ConnectionClosedError exception in shielded future future: <Future "
        "finished exception=ConnectionClosedError(Close(code=1006, reason=''), "
        "None, None)>"
    ),
    # 1002 protocol error is a genuinely unexpected close.
    (
        "ConnectionClosedError exception in shielded future future: <Future "
        "finished exception=ConnectionClosedError(Close(code=1002, reason="
        "'WebSocket Protocol Error'), None, None)>"
    ),
    # A cancelled in-flight request is not a websocket close, so no metric covers it.
    (
        "CancelledError exception in shielded future future: "
        "<Future finished exception=CancelledError()>"
    ),
    # A non-close error whose text merely mentions a close type must not be dropped:
    # the match is anchored to the exception type, not any substring.
    (
        "RuntimeError exception in shielded future future: <Future finished "
        "exception=RuntimeError('cleanup failed while handling ConnectionClosedOK')>"
    ),
    # Unrelated asyncio errors.
    "Task exception was never retrieved",
]


@pytest.mark.parametrize("message", DROPPED_MESSAGES)
def test_drop_expected_asyncio_websocket_disconnect_events_drops_expected(message):
    event = {"logger": "asyncio"}

    assert (
        drop_expected_asyncio_websocket_disconnect_events(
            event, {"log_record": _asyncio_record(message)}
        )
        is None
    )


@pytest.mark.parametrize("message", KEPT_MESSAGES)
def test_drop_expected_asyncio_websocket_disconnect_events_keeps_real_errors(message):
    event = {"logger": "asyncio"}

    assert (
        drop_expected_asyncio_websocket_disconnect_events(
            event, {"log_record": _asyncio_record(message)}
        )
        == event
    )


def test_drop_expected_asyncio_websocket_disconnect_events_keeps_non_asyncio_loggers():
    event = {"logger": "django"}
    record = _asyncio_record(
        "ConnectionClosedOK exception in shielded future", name="django.request"
    )

    assert (
        drop_expected_asyncio_websocket_disconnect_events(event, {"log_record": record})
        == event
    )


def test_drop_expected_asyncio_websocket_disconnect_events_without_log_record():
    event = {"logger": "asyncio"}

    assert drop_expected_asyncio_websocket_disconnect_events(event, {}) == event


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
