import re
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache

from loguru import logger

from baserow.contrib.integrations.core.exceptions import (
    CoreInboundEmailTriggerServiceDoesNotExist,
    InvalidInboundEmailPayload,
)

INBOUND_EMAIL_DEDUPE_CACHE_PREFIX = "inbound_email_dedupe"
# Mox retries failed webhook deliveries with backoff for up to ~16 hours, so
# the dedupe entries must outlive the retry window comfortably.
INBOUND_EMAIL_DEDUPE_TIMEOUT_SECONDS = 60 * 60 * 48

INBOUND_EMAIL_TOKEN_REGEX = re.compile(r"^[0-9a-f]{32}$")

# Prefixing the token with this in the localpart targets the draft version of
# the workflow instead of the published one, mirroring the HTTP trigger's
# `?test=true` query string: `test-{token}@domain` starts a test run.
INBOUND_EMAIL_TEST_PREFIX = "test-"

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


@dataclass(frozen=True)
class InboundEmailTarget:
    """
    A trigger address found among a message's recipients: which trigger token
    it names, and whether it targets the draft (`test-` prefixed) or the
    published version of the workflow.
    """

    token: str
    simulate: bool = False

    @property
    def localpart(self) -> str:
        return f"{INBOUND_EMAIL_TEST_PREFIX if self.simulate else ''}{self.token}"


def parse_inbound_localpart(localpart: str) -> Optional[InboundEmailTarget]:
    """
    Parses the base localpart of a recipient address (already lowercased and
    stripped of any `+tag`) into a target, or None when it is not a trigger
    address.
    """

    simulate = localpart.startswith(INBOUND_EMAIL_TEST_PREFIX)
    token = localpart[len(INBOUND_EMAIL_TEST_PREFIX) :] if simulate else localpart
    if not INBOUND_EMAIL_TOKEN_REGEX.match(token):
        return None
    return InboundEmailTarget(token=token, simulate=simulate)


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

    def extract_targets(self, email: InboundEmail) -> List[InboundEmailTarget]:
        """
        Extracts the trigger targets from the email's recipients. The envelope
        recipient (RcptTo) is the most reliable source; the To and Cc headers
        are scanned as a fallback. A `test-` prefixed localpart targets the
        draft version of the workflow, a bare token the published one.

        :param email: The normalized inbound email.
        :return: The unique list of targets found.
        """

        candidates = [email.rcpt_to] + [
            address.address for address in email.to + email.cc
        ]

        domain = settings.INBOUND_EMAIL_DOMAIN.lower()
        targets = []
        for candidate in candidates:
            candidate_domain = (candidate or "").rpartition("@")[2].lower()
            if candidate_domain != domain:
                continue
            # Strip any `+tag` sub-address so `token+tag@domain` resolves to the
            # `token` trigger; the tag is surfaced separately in the payload.
            localpart, _ = split_catchall_localpart(candidate)
            target = parse_inbound_localpart(localpart)
            if target is not None and target not in targets:
                targets.append(target)

        return targets

    def get_dedupe_cache_key(
        self, target: InboundEmailTarget, email: InboundEmail
    ) -> Optional[str]:
        message_id = email.message_id or email.internal_message_id
        if not message_id:
            return None

        # The test and published addresses of a trigger are separate targets,
        # so one message sent to both is processed for both.
        digest = sha256(message_id.encode()).hexdigest()
        return f"{INBOUND_EMAIL_DEDUPE_CACHE_PREFIX}:{target.localpart}:{digest}"

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
            return self._log_status(HANDLE_STATUS_DISCARDED, "automated message", email)

        if not settings.INBOUND_EMAIL_DOMAIN:
            return self._log_status(
                HANDLE_STATUS_DISCARDED, "inbound email domain not configured", email
            )

        targets = self.extract_targets(email)
        if not targets:
            return self._log_status(
                HANDLE_STATUS_DISCARDED, "no recipient matches a trigger address", email
            )

        service_type = service_type_registry.get("email_trigger")

        statuses = set()
        for target in targets:
            statuses.add(self._process_target(service_type, target, email))

        for status in (
            HANDLE_STATUS_ACCEPTED,
            HANDLE_STATUS_DUPLICATE,
            HANDLE_STATUS_DISCARDED,
        ):
            if status in statuses:
                return status

        return HANDLE_STATUS_DISCARDED

    def _process_target(
        self, service_type, target: InboundEmailTarget, email: InboundEmail
    ) -> str:
        cache_key = self.get_dedupe_cache_key(target, email)

        # `cache.add` is atomic; it returns False when the key already exists,
        # meaning this message was processed before. Mox delivers webhooks
        # at-least-once, so the endpoint must be idempotent. When the message
        # has no Message-ID at all, deduplication is skipped.
        if cache_key is not None and not cache.add(
            cache_key, True, timeout=INBOUND_EMAIL_DEDUPE_TIMEOUT_SECONDS
        ):
            return self._log_status(
                HANDLE_STATUS_DUPLICATE, "message already processed", email, target
            )

        try:
            service_type.process_inbound_email(
                target.token, email, simulate=target.simulate
            )
        except CoreInboundEmailTriggerServiceDoesNotExist:
            return self._log_status(
                HANDLE_STATUS_DISCARDED, "no trigger for token", email, target
            )
        except Exception:
            # The message was not processed, so remove the dedupe entry to
            # make sure the next retried delivery is not treated as a
            # duplicate.
            if cache_key is not None:
                cache.delete(cache_key)
            raise

        return self._log_status(
            HANDLE_STATUS_ACCEPTED, "dispatched to trigger", email, target
        )

    def _log_status(
        self,
        status: str,
        reason: str,
        email: InboundEmail,
        target: Optional[InboundEmailTarget] = None,
    ) -> str:
        """
        Logs the outcome of handling an inbound message and returns the status
        so callers can `return self._log_status(...)`. Every outcome is answered
        with HTTP 200 (a non-2xx would make mox retry, and a distinct code would
        let an outsider probe which tokens exist), so this log line is the only
        place operators can tell accepted, duplicate and discarded apart.

        Neither the addresses nor the full token are logged: the token is the
        routing secret of a trigger. The `test-` prefix is kept so test runs
        can be told apart from live ones. The message is identified by a short
        prefix of the hashed Message-ID, which is enough to correlate retried
        deliveries of the same message.
        """

        message_id = email.message_id or email.internal_message_id
        message_ref = (
            sha256(message_id.encode()).hexdigest()[:12] if message_id else "-"
        )
        logger.info(
            "Inbound email {status}: {reason} (message={message_ref}, token={token})",
            status=status,
            reason=reason,
            message_ref=message_ref,
            token=(
                f"{INBOUND_EMAIL_TEST_PREFIX if target.simulate else ''}"
                f"{target.token[:8]}…"
                if target
                else "-"
            ),
        )
        return status
