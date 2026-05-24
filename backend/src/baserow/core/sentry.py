import json
import logging
from typing import Any

from django.contrib.auth import get_user_model

from loguru import logger
from sentry_sdk.transport import Transport

SENTRY_LOG_PREFIX = "[SENTRY]"


def _get_sentry_event_message(event: dict[str, Any]) -> str:
    exception_values = event.get("exception", {}).get("values", [])
    if exception_values:
        exception = exception_values[-1]
        exception_type = exception.get("type", "UnknownError")
        exception_value = exception.get("value", "")
        if exception_value:
            return f"{exception_type}: {exception_value}"
        return exception_type

    log_entry = event.get("logentry", {})
    if log_entry.get("formatted"):
        return log_entry["formatted"]
    if log_entry.get("message"):
        return log_entry["message"]
    if event.get("message"):
        return str(event["message"])

    return "Sentry event captured without a message."


def log_sentry_event_to_console(event: dict[str, Any]) -> None:
    level = str(event.get("level", "error")).upper()
    event_id = event.get("event_id", "unknown")
    message = _get_sentry_event_message(event)
    logger.error(f"{SENTRY_LOG_PREFIX} [{level}] [{event_id}] {message}")


class ConsoleSentryTransport(Transport):
    """
    A transport that logs Sentry events locally instead of sending them to Sentry.
    """

    def capture_event(self, event):
        log_sentry_event_to_console(event)

    def capture_envelope(self, envelope):
        for item in envelope.items:
            item_type = item.headers.get("type", "unknown")
            payload = item.get_bytes().decode("utf-8", errors="replace")

            if item_type == "event":
                try:
                    log_sentry_event_to_console(json.loads(payload))
                    continue
                except json.JSONDecodeError:
                    pass

            logger.error(
                f"{SENTRY_LOG_PREFIX} [ENVELOPE] [{item_type.upper()}] {payload}"
            )


def drop_expected_asyncio_websocket_ping_timeout_events(
    event: dict[str, Any], hint: dict[str, Any]
) -> dict[str, Any] | None:
    """
    Ignore websocket keepalive timeouts logged by asyncio.

    These are emitted by the websockets stack when a client disappears without a
    clean close handshake. They are noisy, expected in production, and don't
    point to an application error in Baserow itself.
    """

    log_record = hint.get("log_record")
    if not isinstance(log_record, logging.LogRecord):
        return event

    if log_record.name != "asyncio":
        return event

    message = log_record.getMessage()
    if (
        "ConnectionClosedError exception in shielded future" in message
        and "keepalive ping timeout" in message
    ):
        return None

    return event


def setup_user_in_sentry(user):
    """
    This function sets the user in the Sentry context. This is useful for debugging
    and error tracking, and ensure no sensitive information is sent to Sentry.

    :param user: The user that needs to be set in the Sentry context.
    """

    from sentry_sdk import set_user

    set_user({"id": user.id})


def patch_user_model_str():
    """
    This function patches the user model to return the user id instead of the email, to
    ensure no sensitive user information is sent to Sentry.
    """

    User = get_user_model()
    User.__str__ = lambda self: str(self.id)
