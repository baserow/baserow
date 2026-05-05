import logging
from typing import Any

from django.contrib.auth import get_user_model


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
