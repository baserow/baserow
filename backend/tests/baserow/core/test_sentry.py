import json
import logging
import os
import subprocess
import sys
from unittest.mock import patch

import pytest
import sentry_sdk
from asgiref.sync import async_to_sync
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from baserow.core.sentry import (
    before_send,
    drop_expected_asyncio_disconnect_events,
    ignore_sentry_exceptions,
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


def test_sentry_hooks_redact_private_link_tokens():
    token = "0123456789abcdef" * 4
    encoded = "%30%2531" + token[2:]
    link = f"http://localhost:3000/template/slug/private-link/{encoded}"
    event = {
        "request": {
            "url": f"http://localhost:8000/api/private-link/{token}/",
            "query_string": f"original=%2Ftemplate%2Fslug%2Fprivate-link%2F{token}",
            "headers": {
                "Referer": link,
                "X-Link": f"next=%2Flogin%3Foriginal%3D%252Fprivate-link%252F{token}",
            },
        },
        "breadcrumbs": {"values": [{"data": {"url": link}}]},
    }

    redacted = before_send(event, {})
    sent = json.dumps(redacted)

    assert token[2:] not in sent
    assert redacted["request"]["headers"] == {
        "Referer": "http://localhost:3000/template/slug/private-link/[Filtered]",
        "X-Link": "next=%2Flogin%3Foriginal%3D%252Fprivate-link%252F[Filtered]",
    }


class _CollectingTransport(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.events = []

    def capture_envelope(self, envelope):
        self.events.extend(
            item.payload.json for item in envelope.items if item.type == "event"
        )


@pytest.fixture
def sentry_events(settings):
    settings.SENTRY_DSN = "https://public@example.invalid/1"
    transport = _CollectingTransport()
    client = sentry_sdk.Client(
        dsn=settings.SENTRY_DSN, transport=transport, default_integrations=False
    )
    with sentry_sdk.isolation_scope() as scope:
        scope.set_client(client)
        yield transport.events
    client.close()


class _ProviderError(Exception):
    pass


class _ProviderConnectionError(_ProviderError):
    pass


def _sent(events):
    return [
        event.get("message") or event["exception"]["values"][-1]["value"]
        for event in events
    ]


def test_ignore_sentry_exceptions_drops_only_the_given_types_inside_the_block(
    sentry_events,
):
    with ignore_sentry_exceptions((_ProviderError,)):
        sentry_sdk.capture_exception(_ProviderConnectionError("dropped subclass"))
        sentry_sdk.capture_exception(ValueError("kept other type"))
        sentry_sdk.capture_message("kept message")

    sentry_sdk.capture_exception(_ProviderError("kept outside"))

    assert _sent(sentry_events) == ["kept other type", "kept message", "kept outside"]


def test_ignore_sentry_exceptions_drops_logged_exceptions_of_the_given_types(
    settings,
):
    from sentry_sdk.integrations.logging import LoggingIntegration

    settings.SENTRY_DSN = "https://public@example.invalid/1"
    transport = _CollectingTransport()
    client = sentry_sdk.Client(
        dsn=settings.SENTRY_DSN,
        transport=transport,
        default_integrations=False,
        integrations=[LoggingIntegration(event_level=logging.ERROR)],
    )
    log = logging.getLogger("baserow.test_ignore_sentry_exceptions")
    with sentry_sdk.isolation_scope() as scope:
        scope.set_client(client)
        with ignore_sentry_exceptions((_ProviderError,)):
            for error in (_ProviderError("dropped"), ValueError("kept")):
                try:
                    raise error
                except Exception:
                    log.exception("Probe failed")
    client.close()

    assert [
        event["exception"]["values"][-1]["value"] for event in transport.events
    ] == ["kept"]


def test_ignore_sentry_exceptions_reaches_async_to_sync_probes(sentry_events):
    async def probe():
        # The AI provider probes run their client calls through async_to_sync,
        # in another thread.
        sentry_sdk.capture_exception(_ProviderError("dropped"))
        sentry_sdk.capture_exception(ValueError("kept"))

    with ignore_sentry_exceptions((_ProviderError,)):
        async_to_sync(probe)()

    assert _sent(sentry_events) == ["kept"]


def test_ignore_sentry_exceptions_without_sentry(settings):
    settings.SENTRY_DSN = ""

    with ignore_sentry_exceptions((_ProviderError,)):
        pass
