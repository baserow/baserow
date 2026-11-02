import logging
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from loguru import logger

SENTRY_LOG_PREFIX = "[SENTRY]"
_SAFE_EXCEPTION_CONTEXT = "baserow_safe_exception"


def report_exception(
    exc: Exception, message: str, *, context: dict[str, Any] | None = None
) -> None:
    """
    Capture the original exception in Sentry and log a payload-free summary.

    The message must be developer-supplied text without exception messages or private
    values. Context and traceback locals remain available in Sentry, subject to its
    existing scrubbing and size limits. Reporting must not interrupt the caller's
    fallback if Sentry is unavailable.

    :param exc: The original caught exception, with its traceback.
    :param message: A safe console summary without private values.
    :param context: Additional debugging context sent only to Sentry.
    """

    summary = f"{message} ({type(exc).__name__})"
    event_id = None
    if settings.SENTRY_DSN:
        try:
            from sentry_sdk import capture_exception, new_scope

            with new_scope() as scope:
                scope.set_context(_SAFE_EXCEPTION_CONTEXT, {"summary": summary})
                if context is not None:
                    scope.set_context("report_exception", context)
                event_id = capture_exception(exc)
        except Exception:
            # Logging this reporting error or its traceback could disclose the same
            # private values that the safe summary is intended to keep off stdout.
            pass

    if event_id:
        summary += f" [Sentry event: {event_id}]"
    logger.warning(summary)


def _get_sentry_event_message(event: dict[str, Any]) -> str:
    safe_summary = event.get("contexts", {}).get(_SAFE_EXCEPTION_CONTEXT, {})
    if safe_summary.get("summary"):
        return safe_summary["summary"]

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
    log = (
        logger.warning
        if _SAFE_EXCEPTION_CONTEXT in event.get("contexts", {})
        else logger.error
    )
    log(f"{SENTRY_LOG_PREFIX} [{level}] [{event_id}] {message}")


# asyncio logs a benign websocket close as "<ExceptionType> exception in shielded
# future". A clean ConnectionClosedOK is always noise; a ConnectionClosedError is
# only noise for a keepalive timeout. Their rate lives in the
# baserow.websocket_disconnects metric. Anchoring on the exception type keeps real
# errors reportable, including abnormal 1006 closes (which also flag mass
# disconnects from worker restarts) and protocol errors.
_OK_CLOSE_LOG = "ConnectionClosedOK exception in shielded future"
_ERR_CLOSE_LOG = "ConnectionClosedError exception in shielded future"
# Logged since Python 3.14 when a timed-out health probe cancels its request.
_CANCELLED_REQUEST_LOG = "CancelledError exception in shielded future"


def _is_health_check_event(event: dict[str, Any]) -> bool:
    url = (event.get("request") or {}).get("url") or ""
    return urlparse(url).path == reverse("api:health:public_health_check")


def drop_expected_asyncio_disconnect_events(
    event: dict[str, Any], hint: dict[str, Any]
) -> dict[str, Any] | None:
    """Sentry before_send hook that drops expected client-disconnect noise."""

    log_record = hint.get("log_record")
    if not isinstance(log_record, logging.LogRecord):
        return event

    if log_record.name != "asyncio":
        return event

    # This relies on asyncio's exact log format: getMessage() does %-style arg
    # interpolation on the raw record, and the prefixes above match what the
    # current Python/websockets stack emits. The asyncio name guard bounds the
    # blast radius, but if asyncio ever reuses this log path for a different
    # exception sharing the prefix, the suppression would silently expand. The
    # baserow.websocket_disconnects metric is the format-independent source of
    # truth if that ever happens.
    message = log_record.getMessage()
    if message.startswith(_OK_CLOSE_LOG):
        return None
    if message.startswith(_ERR_CLOSE_LOG) and "keepalive ping timeout" in message:
        return None
    if message.startswith(_CANCELLED_REQUEST_LOG) and _is_health_check_event(event):
        return None

    return event


def setup_user_in_sentry(user):
    """
    This function sets the user in the Sentry context. This is useful for debugging
    and error tracking, and ensure no sensitive information is sent to Sentry.

    :param user: The user that needs to be set in the Sentry context.
    """

    if not settings.SENTRY_DSN:
        return

    from sentry_sdk import set_user

    set_user({"id": user.id})


def patch_user_model_str():
    """
    This function patches the user model to return the user id instead of the email, to
    ensure no sensitive user information is sent to Sentry.
    """

    User = get_user_model()
    User.__str__ = lambda self: str(self.id)
