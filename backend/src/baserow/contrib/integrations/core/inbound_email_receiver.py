"""
Deletes handed-over messages from the bundled inbound mail server (mox).

Mox writes every accepted message to disk before posting the incoming-delivery
webhook and never removes it: it has no retention setting, and its web API can
delete a message by id but cannot list them. Two properties make a sweep
possible anyway. Message ids are sequential per account, and every accepted
message reaches `InboundEmailHandler.handle_webhook_payload`, which records the
highest id it has seen. The sweep then deletes every id between the last swept
one and that high-water mark, treating "not found" as already gone. Deleting a
message whose webhook is still being retried is safe: mox retries from its own
stored copy of the payload, and Baserow never reads a message back. Ids start
over when the receiver's data directory is wiped, which the handler notices
when an id at or below the swept mark arrives and lowers the mark again.
"""

import json
from typing import Dict, Optional

from django.conf import settings

import requests
from loguru import logger

from baserow.contrib.integrations.core.models import CoreInboundEmailReceiverState

# The explicit address the web API authenticates with. Must match the
# destination `generate-mox-config.sh` adds to the inbound account.
INBOUND_EMAIL_WEBAPI_LOCALPART = "webapi"
# Bounds one run after a long backlog (one HTTP call per id); the rest is
# picked up by the next run.
INBOUND_EMAIL_SWEEP_MAX_MESSAGES_PER_RUN = 10_000
INBOUND_EMAIL_RECEIVER_TIMEOUT_SECONDS = 10


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


class InboundEmailReceiverStateHandler:
    @staticmethod
    def get_state() -> CoreInboundEmailReceiverState:
        state, _ = CoreInboundEmailReceiverState.objects.get_or_create(pk=1)
        return state

    @classmethod
    def record_seen_message(cls, message_id: int) -> None:
        """
        Raises the high-water mark to the provided receiver-side message id.
        Lower ids, e.g. from a retried webhook, never move it back.

        An id at or below the swept mark means either that the receiver's
        message store was reset (ids restart at 1 after its data directory is
        wiped) or that this is a retried webhook for an already swept message.
        The mark is lowered to just below the id either way: it is what keeps
        the sweep going after a reset, and in the retry case the next run
        merely re-deletes a few ids that are already gone.
        """

        if message_id <= 0:
            return
        state = cls.get_state()
        CoreInboundEmailReceiverState.objects.filter(
            pk=state.pk, last_seen_message_id__lt=message_id
        ).update(last_seen_message_id=message_id)
        CoreInboundEmailReceiverState.objects.filter(
            pk=state.pk, last_deleted_message_id__gte=message_id
        ).update(last_deleted_message_id=message_id - 1)

    @classmethod
    def record_deleted_up_to(cls, message_id: int) -> None:
        state = cls.get_state()
        CoreInboundEmailReceiverState.objects.filter(
            pk=state.pk, last_deleted_message_id__lt=message_id
        ).update(last_deleted_message_id=message_id)


def sweep_inbound_email_receiver(
    client: Optional[InboundEmailReceiverClient] = None,
    max_messages: int = INBOUND_EMAIL_SWEEP_MAX_MESSAGES_PER_RUN,
) -> Optional[Dict[str, int]]:
    """
    Deletes every message the receiver still holds up to the high-water mark.

    :param client: The receiver client, resolved from the settings by default.
    :param max_messages: The most ids to process in one run.
    :return: Counts of deleted, already gone and remaining ids, or None when
        the sweep is not configured on this instance.
    """

    owns_client = client is None
    client = client or InboundEmailReceiverClient.from_settings()
    if client is None:
        return None

    try:
        return _sweep(client, max_messages)
    finally:
        if owns_client:
            client.close()


def _sweep(client: InboundEmailReceiverClient, max_messages: int) -> Dict[str, int]:
    state = InboundEmailReceiverStateHandler.get_state()
    first = state.last_deleted_message_id + 1
    last = min(state.last_seen_message_id, first + max_messages - 1)
    counts = {"deleted": 0, "already_gone": 0, "remaining": 0}
    progress = state.last_deleted_message_id

    for message_id in range(first, last + 1):
        try:
            deleted = client.delete_message(message_id)
        except InboundEmailReceiverError as exc:
            # Keep what was achieved; the next run resumes from here.
            logger.warning(
                "Inbound email sweep stopped at message {message_id}: {error}",
                message_id=message_id,
                error=exc,
            )
            break
        counts["deleted" if deleted else "already_gone"] += 1
        progress = message_id

    if progress > state.last_deleted_message_id:
        InboundEmailReceiverStateHandler.record_deleted_up_to(progress)
    counts["remaining"] = max(state.last_seen_message_id - progress, 0)

    if counts["deleted"] or counts["remaining"]:
        logger.info(
            "Inbound email sweep deleted {deleted} message(s) from the receiver "
            "({already_gone} already gone, {remaining} remaining).",
            **counts,
        )
    return counts
