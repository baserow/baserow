import logging
import os
import subprocess
import sys
from io import StringIO
from unittest.mock import patch

import pytest
import sentry_sdk
from loguru import logger
from sentry_sdk.envelope import Envelope
from sentry_sdk.integrations.loguru import LoguruIntegration
from sentry_sdk.scrubber import EventScrubber
from sentry_sdk.transport import Transport

from baserow.core.sentry import (
    drop_expected_asyncio_disconnect_events,
    log_sentry_event_to_console,
    report_exception,
)
from baserow.core.sentry_transport import ConsoleSentryTransport


def test_sentry_sdk_is_not_loaded_when_sentry_is_disabled():
    code = """
import sys
from types import SimpleNamespace

from django.conf import settings

settings.configure(SENTRY_DSN="")

from baserow.core.sentry import report_exception, setup_user_in_sentry

setup_user_in_sentry(SimpleNamespace(id=1))
report_exception(ValueError("private-disabled-canary"), "Safe disabled summary")
assert not any(
    module == "sentry_sdk" or module.startswith("sentry_sdk.")
    for module in sys.modules
)
"""
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}

    result = subprocess.run(  # noqa: S603 - current interpreter runs fixed test code.
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )
    assert "Safe disabled summary (ValueError)" in result.stderr
    assert "private-disabled-canary" not in result.stderr


@pytest.fixture
def sentry_events(settings):
    events = []

    class MemoryTransport(Transport):
        def capture_envelope(self, envelope):
            event = envelope.get_event()
            if event is not None:
                events.append(event)

    settings.SENTRY_DSN = "https://public@example.invalid/1"
    client = sentry_sdk.Client(
        dsn=settings.SENTRY_DSN,
        default_integrations=False,
        integrations=[LoguruIntegration()],
        transport=MemoryTransport(),
        send_default_pii=False,
        event_scrubber=EventScrubber(recursive=True),
    )
    with sentry_sdk.isolation_scope(), sentry_sdk.new_scope() as scope:
        scope.set_client(client)
        yield events
    client.close()


@pytest.fixture
def log_output():
    output = StringIO()
    sink = logger.add(output, format="{level} {message}", diagnose=True)
    yield output
    logger.remove(sink)


def test_report_exception_retains_scrubbed_sentry_details_only(
    sentry_events, log_output
):
    def fail_with_private_data():
        row = {
            "value": "private-row-canary",
            "password": "credential-canary",
            "ip_address": "203.0.113.10",
        }
        raise ValueError(f"private-exception-canary: {row['value']}")

    try:
        fail_with_private_data()
    except ValueError as exc:
        report_exception(
            exc,
            "Safe operation summary",
            context={"tool": "test_tool", "phase": "step_facts"},
        )

    # The warning must not produce another event through Loguru's error sink.
    assert len(sentry_events) == 1
    event = sentry_events[0]
    exception = event["exception"]["values"][0]
    assert exception["type"] == "ValueError"
    assert exception["value"] == "private-exception-canary: private-row-canary"
    frame = exception["stacktrace"]["frames"][-1]
    assert frame["function"] == "fail_with_private_data"
    assert "private-row-canary" in frame["vars"]["row"]["value"]
    assert frame["vars"]["row"]["password"] == "[Filtered]"
    assert frame["vars"]["row"]["ip_address"] == "[Filtered]"
    assert event["contexts"]["report_exception"] == {
        "tool": "test_tool",
        "phase": "step_facts",
    }
    assert log_output.getvalue() == (
        "WARNING Safe operation summary (ValueError) "
        f"[Sentry event: {event['event_id']}]\n"
    )

    logger.error("Later unrelated event")
    assert len(sentry_events) == 2
    assert "report_exception" not in sentry_events[-1].get("contexts", {})
    assert "baserow_safe_exception" not in sentry_events[-1].get("contexts", {})


@pytest.mark.parametrize("capture_method", ["event", "envelope"])
def test_report_exception_fake_transport_keeps_private_details_off_console(
    sentry_events, log_output, capture_method
):
    try:
        raise RuntimeError("private-exception-canary")
    except RuntimeError as exc:
        report_exception(exc, "Safe operation summary", context={"tool": "test_tool"})
    event = sentry_events[0]
    transport = ConsoleSentryTransport()
    if capture_method == "event":
        transport.capture_event(event)
    else:
        envelope = Envelope()
        envelope.add_event(event)
        transport.capture_envelope(envelope)

    assert len(sentry_events) == 1
    output = log_output.getvalue()
    assert "[SENTRY] [ERROR]" in output
    assert "Safe operation summary (RuntimeError)" in output
    assert "private-exception-canary" not in output


@pytest.mark.parametrize("sdk_operation", ["capture_exception", "new_scope"])
def test_report_exception_does_not_disclose_reporting_failures(
    settings, log_output, sdk_operation
):
    settings.SENTRY_DSN = "https://public@example.invalid/1"
    with patch(
        f"sentry_sdk.{sdk_operation}",
        side_effect=RuntimeError("private-reporting-canary"),
    ):
        report_exception(
            ValueError("private-original-canary"), "Safe operation summary"
        )

    assert log_output.getvalue() == "WARNING Safe operation summary (ValueError)\n"


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
    # A cancelled request without request data may be a real user request.
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
def test_drop_expected_asyncio_disconnect_events_drops_expected(message):
    event = {"logger": "asyncio"}

    assert (
        drop_expected_asyncio_disconnect_events(
            event, {"log_record": _asyncio_record(message)}
        )
        is None
    )


@pytest.mark.parametrize("message", KEPT_MESSAGES)
def test_drop_expected_asyncio_disconnect_events_keeps_real_errors(message):
    event = {"logger": "asyncio"}

    assert (
        drop_expected_asyncio_disconnect_events(
            event, {"log_record": _asyncio_record(message)}
        )
        == event
    )


CANCELLED_REQUEST_MESSAGE = (
    "CancelledError exception in shielded future\n"
    "future: <Future finished exception=CancelledError()>"
)


def test_drop_expected_asyncio_disconnect_events_drops_cancelled_health_check() -> None:
    event = {
        "logger": "asyncio",
        "request": {"url": "http://localhost:8000/api/_health/"},
    }

    assert (
        drop_expected_asyncio_disconnect_events(
            event, {"log_record": _asyncio_record(CANCELLED_REQUEST_MESSAGE)}
        )
        is None
    )


@pytest.mark.parametrize(
    "request_data",
    [
        {"url": "http://localhost:8000/api/_health/full/"},
        {"url": "http://localhost:8000/assistant/chat/"},
        {},
    ],
)
def test_drop_expected_asyncio_disconnect_events_keeps_other_cancelled_requests(
    request_data: dict[str, str],
) -> None:
    event = {"logger": "asyncio", "request": request_data}

    assert (
        drop_expected_asyncio_disconnect_events(
            event, {"log_record": _asyncio_record(CANCELLED_REQUEST_MESSAGE)}
        )
        == event
    )


def test_drop_expected_asyncio_disconnect_events_keeps_non_asyncio_loggers():
    event = {"logger": "django"}
    record = _asyncio_record(
        "ConnectionClosedOK exception in shielded future", name="django.request"
    )

    assert (
        drop_expected_asyncio_disconnect_events(event, {"log_record": record}) == event
    )


def test_drop_expected_asyncio_disconnect_events_without_log_record():
    event = {"logger": "asyncio"}

    assert drop_expected_asyncio_disconnect_events(event, {}) == event


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
