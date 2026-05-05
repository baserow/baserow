import logging

from baserow.core.sentry import drop_expected_asyncio_websocket_ping_timeout_events


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
