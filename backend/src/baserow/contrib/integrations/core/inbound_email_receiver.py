"""
Deletes handed-over messages from the bundled inbound mail server (mox).

Mox writes every accepted message to disk before posting the incoming-delivery
webhook and never removes it: it has no retention setting. Its web API can
delete a message by id, and every webhook carries the id of the message it is
about, so `InboundEmailHandler.handle_webhook_payload` queues the deletion of
each message it is handed, whatever it then does with it. Deleting a message
whose webhook is still being retried is safe: mox retries from its own stored
copy of the payload, and Baserow never reads a message back. The one thing this
does not cover is a message whose webhook never reaches the backend at all,
which happens when the backend stays unreachable for longer than mox retries
(roughly 32 hours).
"""

import json
from typing import Optional

from django.conf import settings

import requests
from loguru import logger

# The explicit address the web API authenticates with. Must match the
# destination `generate-mox-config.sh` adds to the inbound account.
INBOUND_EMAIL_WEBAPI_LOCALPART = "webapi"
INBOUND_EMAIL_RECEIVER_TIMEOUT_SECONDS = 10
# How long after its webhook a message is deleted from the receiver. Not needed
# for correctness (see the module docstring), but it lets the receiver finish
# its own bookkeeping for the delivery before the backend calls back into it.
INBOUND_EMAIL_RECEIVER_DELETE_DELAY_SECONDS = 60


class InboundEmailReceiverError(Exception):
    """Raised when the receiver's web API cannot be used."""


# Mox only serves its internal web services, the web API included, when the
# request's Host header is an IP address, the listener's own hostname or
# "localhost"; anything else gets a 404. The backend reaches the receiver by
# whatever name the deployment gives it (`email-receiver` in compose), so the
# client always presents itself as localhost instead of the URL's hostname.
INBOUND_EMAIL_RECEIVER_HOST_HEADER = "localhost"


class InboundEmailReceiverClient:
    """
    Minimal client for mox's web API: `POST {base}/webapi/v0/<Method>` with a
    form field `request` holding the JSON request, HTTP basic auth with an
    address of the account. One session is kept for the client's lifetime so a
    sweep of many messages reuses its connection instead of opening one per
    call.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: int = INBOUND_EMAIL_RECEIVER_TIMEOUT_SECONDS,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._session = requests.Session()
        self._session.auth = (username, password)
        self._session.headers["Host"] = INBOUND_EMAIL_RECEIVER_HOST_HEADER

    def close(self) -> None:
        self._session.close()

    @classmethod
    def from_settings(cls) -> Optional["InboundEmailReceiverClient"]:
        """
        Returns a client for the configured receiver, or None when inbound email
        or the receiver URL is not configured on this instance.
        """

        if not (
            settings.INBOUND_EMAIL_RECEIVER_URL
            and settings.INBOUND_EMAIL_DOMAIN
            and settings.INBOUND_EMAIL_WEBHOOK_SECRET
        ):
            return None
        return cls(
            settings.INBOUND_EMAIL_RECEIVER_URL,
            f"{INBOUND_EMAIL_WEBAPI_LOCALPART}@{settings.INBOUND_EMAIL_DOMAIN}",
            # The entrypoint applies the same fallback when it sets the
            # account's password on the receiver.
            settings.INBOUND_EMAIL_RECEIVER_PASSWORD
            or settings.INBOUND_EMAIL_WEBHOOK_SECRET,
        )

    def delete_message(self, message_id: int) -> bool:
        """
        Deletes one message and returns True, or returns False when the receiver
        no longer has it. Any other failure raises `InboundEmailReceiverError`.
        """

        try:
            response = self._session.post(
                f"{self.base_url}/webapi/v0/MessageDelete",
                data={"request": json.dumps({"MsgID": message_id})},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise InboundEmailReceiverError(
                f"could not reach the inbound email receiver: {type(exc).__name__}"
            ) from exc

        if response.status_code == 200:
            return True

        if response.status_code == 400:
            # Mox answers 400 for a bad request as well as for an unknown or
            # already removed message; only the latter two mean "gone".
            try:
                error = response.json()
            except ValueError:
                error = {}
            code = error.get("Code")
            message = error.get("Message", "")
            if code == "messageNotFound" or (code == "user" and "removed" in message):
                return False

        raise InboundEmailReceiverError(
            f"MessageDelete for message {message_id} failed with HTTP "
            f"{response.status_code}: {response.text[:200]}"
        )


def delete_receiver_message(message_id: int) -> Optional[bool]:
    """
    Deletes one message from the configured receiver.

    :param message_id: The receiver-side id of the message, as carried by its
        webhook.
    :raises InboundEmailReceiverError: When the receiver cannot be used; the
        calling task retries.
    :return: True when the message was deleted, False when the receiver no
        longer had it, or None when no receiver is configured on this instance.
    """

    client = InboundEmailReceiverClient.from_settings()
    if client is None:
        return None

    try:
        deleted = client.delete_message(message_id)
    finally:
        client.close()

    logger.debug(
        "Inbound email receiver message {message_id} {outcome}.",
        message_id=message_id,
        outcome="deleted" if deleted else "was already gone",
    )
    return deleted
