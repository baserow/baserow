import re
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache

from baserow.contrib.integrations.core.exceptions import (
    CoreInboundEmailTriggerServiceDoesNotExist,
    InvalidInboundEmailPayload,
)

INBOUND_EMAIL_DEDUPE_CACHE_PREFIX = "inbound_email_dedupe"
# Mox retries failed webhook deliveries with backoff for up to ~16 hours, so
# the dedupe entries must outlive the retry window comfortably.
INBOUND_EMAIL_DEDUPE_TIMEOUT_SECONDS = 60 * 60 * 48

INBOUND_EMAIL_TOKEN_REGEX = re.compile(r"^[0-9a-f]{32}$")

# The catch-all sub-address separator configured on the receiving mail server
# (mox's LocalpartCatchallSeparator). Everything after it in the localpart is an
# optional recipient "tag": `token+tag@domain` still routes to the `token`
# trigger, and `tag` is exposed in the payload so a workflow can branch on it.
INBOUND_EMAIL_CATCHALL_SEPARATOR = "+"


def split_catchall_localpart(address: str) -> "tuple[str, str]":
    """
    Splits an email address into its base localpart and sub-address tag on the
    catch-all separator, e.g. `abc+sales@d` -> `("abc", "sales")`. The base is
    lowercased (trigger tokens are lowercase hex) so it can be matched against a
    token; the tag is returned as received so a router can match it exactly. The
    tag is empty when the address has no separator.

    :param address: The full email address.
    :return: A `(base_localpart, tag)` tuple.
    """

    localpart = (address or "").rpartition("@")[0]
    base, separator, tag = localpart.partition(INBOUND_EMAIL_CATCHALL_SEPARATOR)
    return base.lower(), (tag if separator else "")


HANDLE_STATUS_ACCEPTED = "accepted"
HANDLE_STATUS_DUPLICATE = "duplicate"
HANDLE_STATUS_DISCARDED = "discarded"


@dataclass
class InboundEmailAddress:
    name: str = ""
    address: str = ""

    def to_payload(self) -> Dict[str, str]:
        return {"name": self.name, "address": self.address}


@dataclass
class InboundEmailAttachment:
    filename: str = ""
    content_type: str = ""
    size: int = 0

    def to_payload(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
        }


@dataclass
class InboundEmail:
    """
    The normalized internal representation of an inbound email. The receiving
    mail server's webhook payload is converted into this representation at the
    endpoint boundary so that the rest of the pipeline is independent of the
    receiver implementation.
    """

    from_: InboundEmailAddress = field(default_factory=InboundEmailAddress)
    to: List[InboundEmailAddress] = field(default_factory=list)
    cc: List[InboundEmailAddress] = field(default_factory=list)
    reply_to: List[InboundEmailAddress] = field(default_factory=list)
    subject: str = ""
    body_text: str = ""
    body_html: str = ""
    message_id: str = ""
    in_reply_to: str = ""
    received_at: str = ""
    attachments: List[InboundEmailAttachment] = field(default_factory=list)
    sender_validated: bool = False
    dkim_verified_domains: List[str] = field(default_factory=list)
    remote_ip: str = ""
    rcpt_to: str = ""
    is_automated: bool = False
    # The receiving mail server's internal message id, used as a dedupe
    # fallback when the message has no RFC Message-ID header.
    internal_message_id: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return {
            "from": self.from_.to_payload(),
            "to": [address.to_payload() for address in self.to],
            "cc": [address.to_payload() for address in self.cc],
            "reply_to": [address.to_payload() for address in self.reply_to],
            "rcpt_to": self.rcpt_to,
            "recipient_tag": split_catchall_localpart(self.rcpt_to)[1],
            "subject": self.subject,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "message_id": self.message_id,
            "in_reply_to": self.in_reply_to,
            "received_at": self.received_at,
            "attachments": [attachment.to_payload() for attachment in self.attachments],
            "sender_validated": self.sender_validated,
            "dkim_verified_domains": self.dkim_verified_domains,
            "remote_ip": self.remote_ip,
        }


def _normalize_addresses(values: Any) -> List[InboundEmailAddress]:
    if not isinstance(values, list):
        return []

    return [
        InboundEmailAddress(
            name=value.get("Name") or "", address=value.get("Address") or ""
        )
        for value in values
        if isinstance(value, dict)
    ]


def _collect_attachments(structure: Any) -> List[InboundEmailAttachment]:
    """
    Walks the MIME structure tree of the webhook payload and collects the
    metadata of every part that presents itself as an attachment.
    """

    if not isinstance(structure, dict):
        return []

    attachments = []
    disposition = (structure.get("ContentDisposition") or "").lower()
    filename = structure.get("Filename") or ""

    if disposition == "attachment" or (filename and disposition != "inline"):
        attachments.append(
            InboundEmailAttachment(
                filename=filename,
                content_type=structure.get("ContentType") or "",
                size=int(structure.get("DecodedSize") or 0),
            )
        )

    for part in structure.get("Parts") or []:
        attachments.extend(_collect_attachments(part))

    return attachments


def normalize_mox_payload(data: Dict[str, Any]) -> InboundEmail:
    """
    Converts a mox `webhook.Incoming` JSON payload into the internal
    `InboundEmail` representation.

    :param data: The parsed JSON body of the webhook request.
    :raises InvalidInboundEmailPayload: When the payload is not shaped like a
        mox incoming delivery webhook.
    :return: The normalized inbound email.
    """

    if not isinstance(data, dict):
        raise InvalidInboundEmailPayload("The payload must be a JSON object.")

    meta = data.get("Meta")
    from_addresses = data.get("From")
    if not isinstance(meta, dict) or not isinstance(from_addresses, list):
        raise InvalidInboundEmailPayload(
            "The payload is missing the required From and Meta fields."
        )

    from_ = _normalize_addresses(from_addresses)

    return InboundEmail(
        from_=from_[0] if from_ else InboundEmailAddress(),
        to=_normalize_addresses(data.get("To")),
        cc=_normalize_addresses(data.get("CC")),
        reply_to=_normalize_addresses(data.get("ReplyTo")),
        subject=data.get("Subject") or "",
        body_text=data.get("Text") or "",
        body_html=data.get("HTML") or "",
        message_id=data.get("MessageID") or "",
        in_reply_to=data.get("InReplyTo") or "",
        received_at=meta.get("Received") or "",
        attachments=_collect_attachments(data.get("Structure")),
        sender_validated=bool(meta.get("MsgFromValidated")),
        dkim_verified_domains=meta.get("DKIMVerifiedDomains") or [],
        remote_ip=meta.get("RemoteIP") or "",
        rcpt_to=meta.get("RcptTo") or "",
        is_automated=bool(meta.get("Automated")),
        internal_message_id=str(meta.get("MsgID") or ""),
    )


class InboundEmailHandler:
    """
    Orchestrates the processing of inbound email webhook payloads: payload
    normalization, loop protection, recipient token extraction, Message-ID
    deduplication and dispatching of the matching email trigger services.
    """

    def extract_tokens(self, email: InboundEmail) -> List[str]:
        """
        Extracts the trigger tokens from the email's recipients. The envelope
        recipient (RcptTo) is the most reliable source; the To and Cc headers
        are scanned as a fallback.

        :param email: The normalized inbound email.
        :return: The unique list of valid tokens found.
        """

        candidates = [email.rcpt_to] + [
            address.address for address in email.to + email.cc
        ]

        domain = settings.INBOUND_EMAIL_DOMAIN.lower()
        tokens = []
        for candidate in candidates:
            candidate_domain = (candidate or "").rpartition("@")[2].lower()
            # Strip any `+tag` sub-address so `token+tag@domain` resolves to the
            # `token` trigger; the tag is surfaced separately in the payload.
            token, _ = split_catchall_localpart(candidate)
            if (
                candidate_domain == domain
                and INBOUND_EMAIL_TOKEN_REGEX.match(token)
                and token not in tokens
            ):
                tokens.append(token)

        return tokens

    def get_dedupe_cache_key(self, token: str, email: InboundEmail) -> Optional[str]:
        message_id = email.message_id or email.internal_message_id
        if not message_id:
            return None

        digest = sha256(message_id.encode()).hexdigest()
        return f"{INBOUND_EMAIL_DEDUPE_CACHE_PREFIX}:{token}:{digest}"

    def handle_webhook_payload(self, data: Dict[str, Any]) -> str:
        """
        Processes a parsed inbound email webhook payload and dispatches the
        matching email trigger services.

        :param data: The parsed JSON body of the webhook request.
        :raises InvalidInboundEmailPayload: When the payload is malformed.
        :return: One of `accepted`, `duplicate` or `discarded`, describing
            what happened to the message.
        """

        from baserow.core.services.registries import service_type_registry

        email = normalize_mox_payload(data)

        # Loop protection: never dispatch automated messages (auto-replies,
        # delivery reports, etc), otherwise a forward rule plus an
        # auto-responder could create an infinite loop.
        if email.is_automated:
            return HANDLE_STATUS_DISCARDED

        if not settings.INBOUND_EMAIL_DOMAIN:
            return HANDLE_STATUS_DISCARDED

        tokens = self.extract_tokens(email)
        if not tokens:
            return HANDLE_STATUS_DISCARDED

        service_type = service_type_registry.get("email_trigger")

        statuses = set()
        for token in tokens:
            statuses.add(self._process_token(service_type, token, email))

        for status in (
            HANDLE_STATUS_ACCEPTED,
            HANDLE_STATUS_DUPLICATE,
            HANDLE_STATUS_DISCARDED,
        ):
            if status in statuses:
                return status

        return HANDLE_STATUS_DISCARDED

    def _process_token(self, service_type, token: str, email: InboundEmail) -> str:
        cache_key = self.get_dedupe_cache_key(token, email)

        # `cache.add` is atomic; it returns False when the key already exists,
        # meaning this message was processed before. Mox delivers webhooks
        # at-least-once, so the endpoint must be idempotent. When the message
        # has no Message-ID at all, deduplication is skipped.
        if cache_key is not None and not cache.add(
            cache_key, True, timeout=INBOUND_EMAIL_DEDUPE_TIMEOUT_SECONDS
        ):
            return HANDLE_STATUS_DUPLICATE

        try:
            service_type.process_inbound_email(token, email)
        except CoreInboundEmailTriggerServiceDoesNotExist:
            return HANDLE_STATUS_DISCARDED
        except Exception:
            # The message was not processed, so remove the dedupe entry to
            # make sure the next retried delivery is not treated as a
            # duplicate.
            if cache_key is not None:
                cache.delete(cache_key)
            raise

        return HANDLE_STATUS_ACCEPTED
