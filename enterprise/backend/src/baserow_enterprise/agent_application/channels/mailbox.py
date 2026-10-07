import base64
import html
import time
from email.message import EmailMessage
from io import BytesIO
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import quote

from django.core.cache import cache
from django.db import transaction

from loguru import logger
from requests import exceptions as request_exceptions
from rest_framework.exceptions import ValidationError

from advocate.exceptions import UnacceptableAddressException
from baserow.contrib.integrations.google.models import GoogleIntegration
from baserow.contrib.integrations.microsoft.models import MicrosoftIntegration
from baserow.contrib.integrations.oauth2.handler import OAuth2IntegrationHandler
from baserow.contrib.integrations.utils import send_http_request
from baserow.core.integrations.models import Integration
from baserow.core.services.exceptions import DispatchException
from baserow.core.user_files.handler import UserFileHandler

from .email import EmailAgentChatChannelType, EmailReplyNotPossible, ReceivedEmail

if TYPE_CHECKING:
    from ..models import AgentChatChannel

REQUEST_TIMEOUT_SECONDS = 15
# New messages taken per poll; the rest wait for the next tick rather than
# one slow mailbox holding the worker.
MAX_MESSAGES_PER_POLL = 25
MAX_ATTACHMENTS = 10
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
POLL_LOCK_SECONDS = 300

GMAIL_API_URL = "https://gmail.googleapis.com/gmail/v1/users/me"
GRAPH_API_URL = "https://graph.microsoft.com/v1.0"


class MailboxRequestFailed(Exception):
    """The provider refused or could not be reached; the poll retries later."""


def _json_request(
    method: str,
    url: str,
    headers: dict,
    *,
    params: Optional[dict] = None,
    json: Any = None,
) -> tuple[int, Any]:
    deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS
    try:
        response = send_http_request(
            method,
            url,
            deadline=deadline,
            operation_timeout=REQUEST_TIMEOUT_SECONDS,
            headers=headers,
            params=params,
            json=json,
            allow_redirects=False,
        )
    except (UnacceptableAddressException, request_exceptions.RequestException) as e:
        raise MailboxRequestFailed(f"{type(e).__name__}") from e
    body = None
    if response.content:
        try:
            body = response.json()
        except ValueError:
            body = None
    return response.status_code, body


def _address_list(values) -> list[str]:
    return [v.strip().lower() for v in values if isinstance(v, str) and v.strip()]


class MailboxAgentChatChannelType(EmailAgentChatChannelType):
    """
    A person's own Gmail or Outlook mailbox, reached through the connected
    Google or Microsoft integration. New mail is fetched by polling; a reply
    leaves from the mailbox itself so it lands in the person's Sent folder
    and threads where the conversation already is.
    """

    integration_model = None

    def prepare_config(self, config: dict, existing_config: dict | None = None) -> dict:
        existing_config = existing_config or {}
        prepared = self.prepare_shared_config(config, existing_config)
        integration_id = config.get(
            "integration_id", existing_config.get("integration_id")
        )
        if not integration_id:
            raise ValidationError({"integration_id": "An integration is required."})
        prepared["integration_id"] = int(integration_id)
        alias = config.get("alias", existing_config.get("alias", ""))
        prepared["alias"] = str(alias or "").strip().lower()[:320]
        # The cursor belongs to the mailbox and integration; a new
        # integration starts from now.
        if prepared["integration_id"] == existing_config.get("integration_id"):
            for key in ("cursor", "label_id"):
                if key in existing_config:
                    prepared[key] = existing_config[key]
        return prepared

    def prepare_imported_config(self, config: dict) -> dict:
        config = dict(config or {})
        # Integration ids are remapped by the import; the copy starts fresh.
        config.pop("cursor", None)
        config.pop("label_id", None)
        return config

    def get_public_config(self, channel: "AgentChatChannel") -> dict:
        config = {
            key: value
            for key, value in channel.config.items()
            if key not in ("cursor", "label_id")
        }
        config["polling"] = bool(channel.config.get("cursor"))
        return config

    def get_integration(self, channel: "AgentChatChannel"):
        integration = Integration.objects.filter(
            id=channel.config.get("integration_id"), application=channel.application
        ).first()
        integration = integration.specific if integration else None
        if not isinstance(integration, self.integration_model):
            raise EmailReplyNotPossible(
                "The mailbox integration of this channel no longer exists."
            )
        return integration

    def auth_headers(self, channel: "AgentChatChannel") -> dict:
        integration = self.get_integration(channel)
        try:
            token = OAuth2IntegrationHandler().get_access_token(integration)
        except DispatchException as e:
            raise EmailReplyNotPossible(str(e)) from e
        return {"Authorization": f"Bearer {token}"}

    def own_addresses(self, channel: "AgentChatChannel") -> set[str]:
        try:
            integration = self.get_integration(channel)
        except EmailReplyNotPossible:
            return set()
        return (
            {integration.account_email.lower()} if integration.account_email else set()
        )

    def alias_matches(self, channel: "AgentChatChannel", to_addresses: list) -> bool:
        alias = channel.config.get("alias")
        return not alias or alias in to_addresses

    def save_cursor(self, channel: "AgentChatChannel", **values) -> None:
        # Only the keys given, so a concurrent settings change is kept.
        from ..models import AgentChatChannel

        with transaction.atomic():
            fresh = AgentChatChannel.objects.select_for_update().get(id=channel.id)
            fresh.config = {**fresh.config, **values}
            fresh.save(update_fields=["config", "updated_on"])
        channel.config = {**channel.config, **values}

    def upload_attachment(self, filename: str, content: bytes) -> Optional[dict]:
        if not content or len(content) > MAX_ATTACHMENT_BYTES:
            return None
        try:
            user_file = UserFileHandler().upload_user_file(
                None, filename or "attachment", BytesIO(content)
            )
        except Exception:  # noqa: BLE001
            logger.exception("Could not store an email attachment")
            return None
        return {**user_file.serialize(), "visible_name": user_file.original_name}

    def poll(self, channel: "AgentChatChannel") -> None:
        """Takes the mail that arrived since the last poll."""

        raise NotImplementedError


class GmailAgentChatChannelType(MailboxAgentChatChannelType):
    type = "gmail"
    integration_model = GoogleIntegration

    def prepare_config(self, config: dict, existing_config: dict | None = None) -> dict:
        existing_config = existing_config or {}
        prepared = super().prepare_config(config, existing_config)
        label = config.get("label", existing_config.get("label", ""))
        prepared["label"] = str(label or "").strip()[:255]
        if prepared["label"] != existing_config.get("label"):
            prepared.pop("label_id", None)
        return prepared

    def poll(self, channel: "AgentChatChannel") -> None:
        headers = self.auth_headers(channel)
        cursor = channel.config.get("cursor")
        if not cursor:
            # Start from now: what is already in the inbox was never meant
            # for the agent.
            status, profile = _json_request("GET", f"{GMAIL_API_URL}/profile", headers)
            if status != 200 or not isinstance(profile, dict):
                raise MailboxRequestFailed(f"profile answered {status}")
            self.save_cursor(channel, cursor=str(profile.get("historyId", "")))
            return

        label_id = self._label_id(channel, headers)
        params = {"startHistoryId": cursor, "historyTypes": "messageAdded"}
        if label_id:
            params["labelId"] = label_id
        message_ids: list[str] = []
        newest_history_id = cursor
        while True:
            status, body = _json_request(
                "GET", f"{GMAIL_API_URL}/history", headers, params=params
            )
            if status == 404:
                # The history is too old to continue from; start over from now.
                self.save_cursor(channel, cursor="")
                return
            if status != 200 or not isinstance(body, dict):
                raise MailboxRequestFailed(f"history answered {status}")
            newest_history_id = str(body.get("historyId") or newest_history_id)
            for entry in body.get("history") or []:
                for added in entry.get("messagesAdded") or []:
                    message = added.get("message") or {}
                    labels = message.get("labelIds") or []
                    if "SENT" in labels or "DRAFT" in labels:
                        continue
                    if message.get("id") and message["id"] not in message_ids:
                        message_ids.append(message["id"])
            if (
                not body.get("nextPageToken")
                or len(message_ids) >= MAX_MESSAGES_PER_POLL
            ):
                break
            params["pageToken"] = body["nextPageToken"]

        for message_id in message_ids[:MAX_MESSAGES_PER_POLL]:
            received = self._fetch_message(channel, headers, message_id)
            if received is not None:
                self.receive_email(channel, received)
        self.save_cursor(channel, cursor=newest_history_id)

    def _label_id(self, channel: "AgentChatChannel", headers: dict) -> str:
        label = channel.config.get("label")
        if not label:
            return ""
        if channel.config.get("label_id"):
            return channel.config["label_id"]
        status, body = _json_request("GET", f"{GMAIL_API_URL}/labels", headers)
        if status != 200 or not isinstance(body, dict):
            raise MailboxRequestFailed(f"labels answered {status}")
        for entry in body.get("labels") or []:
            if (entry.get("name") or "").lower() == label.lower():
                self.save_cursor(channel, label_id=entry["id"])
                return entry["id"]
        raise MailboxRequestFailed(f"label {label!r} does not exist")

    def _fetch_message(
        self, channel: "AgentChatChannel", headers: dict, message_id: str
    ) -> Optional[ReceivedEmail]:
        status, message = _json_request(
            "GET",
            f"{GMAIL_API_URL}/messages/{quote(message_id, safe='')}",
            headers,
            params={"format": "full"},
        )
        if status != 200 or not isinstance(message, dict):
            return None
        payload = message.get("payload") or {}
        header_values = {
            (h.get("name") or "").lower(): h.get("value") or ""
            for h in payload.get("headers") or []
        }
        if header_values.get("auto-submitted", "no").lower() not in ("", "no"):
            return None
        from_name, from_address = _parse_address(header_values.get("from", ""))
        to_addresses = _address_list(
            _split_addresses(header_values.get("to", ""))
            + _split_addresses(header_values.get("cc", ""))
        )
        if not self.alias_matches(channel, to_addresses):
            return None

        text, markup, attachments, names = self._walk_parts(
            headers, message_id, payload
        )
        return ReceivedEmail(
            from_address=from_address,
            from_name=from_name,
            to_addresses=to_addresses,
            subject=header_values.get("subject", ""),
            text=text,
            html=markup,
            message_id=header_values.get("message-id", ""),
            in_reply_to=header_values.get("in-reply-to", ""),
            references=header_values.get("references", "").split(),
            thread_key=message.get("threadId") or "",
            provider_message_id=message_id,
            # Gmail only delivers what passed its own checks; SPF/DKIM
            # results are not exposed per message.
            sender_verified=True,
            attachments=attachments,
            attachment_names=names,
        )

    def _walk_parts(self, headers, message_id, payload):
        text, markup, attachments, names = "", "", [], []
        stack = [payload]
        while stack:
            part = stack.pop(0)
            mime = part.get("mimeType") or ""
            body = part.get("body") or {}
            filename = part.get("filename") or ""
            if filename:
                names.append(filename)
                if len(attachments) < MAX_ATTACHMENTS and body.get("attachmentId"):
                    status, data = _json_request(
                        "GET",
                        f"{GMAIL_API_URL}/messages/{quote(message_id, safe='')}/"
                        f"attachments/{quote(body['attachmentId'], safe='')}",
                        headers,
                    )
                    if status == 200 and isinstance(data, dict) and data.get("data"):
                        stored = self.upload_attachment(
                            filename, _b64url_decode(data["data"])
                        )
                        if stored:
                            attachments.append(stored)
            elif mime == "text/plain" and body.get("data") and not text:
                text = _b64url_decode(body["data"]).decode("utf-8", "replace")
            elif mime == "text/html" and body.get("data") and not markup:
                markup = _b64url_decode(body["data"]).decode("utf-8", "replace")
            stack.extend(part.get("parts") or [])
        return text, markup, attachments, names

    def send_email(self, channel, chat, target, body: str) -> str:
        headers = self.auth_headers(channel)
        message = EmailMessage()
        message["To"] = target.to_address
        message["Subject"] = target.subject
        if target.in_reply_to:
            message["In-Reply-To"] = target.in_reply_to
            message["References"] = " ".join(target.references)
        message.set_content(body)
        payload = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}
        if target.thread_key:
            payload["threadId"] = target.thread_key
        status, answer = _json_request(
            "POST", f"{GMAIL_API_URL}/messages/send", headers, json=payload
        )
        if status >= 400:
            raise EmailReplyNotPossible(f"Gmail refused the reply ({status}).")
        # Gmail assigns the Message-ID; it is read back so the person's
        # answer to it can be matched.
        sent_id = (answer or {}).get("id") if isinstance(answer, dict) else None
        if sent_id:
            status, sent = _json_request(
                "GET",
                f"{GMAIL_API_URL}/messages/{quote(sent_id, safe='')}",
                headers,
                params={"format": "metadata", "metadataHeaders": "Message-ID"},
            )
            if status == 200 and isinstance(sent, dict):
                for header in (sent.get("payload") or {}).get("headers") or []:
                    if (header.get("name") or "").lower() == "message-id":
                        return header.get("value") or ""
        return ""


class OutlookAgentChatChannelType(MailboxAgentChatChannelType):
    type = "outlook"
    integration_model = MicrosoftIntegration

    def prepare_config(self, config: dict, existing_config: dict | None = None) -> dict:
        existing_config = existing_config or {}
        prepared = super().prepare_config(config, existing_config)
        folder = config.get("folder", existing_config.get("folder", "inbox"))
        prepared["folder"] = str(folder or "inbox").strip()[:255]
        if prepared["folder"] != existing_config.get("folder"):
            prepared.pop("cursor", None)
        return prepared

    def _folder_url(self, channel: "AgentChatChannel") -> str:
        folder = channel.config.get("folder") or "inbox"
        return f"{GRAPH_API_URL}/me/mailFolders/{quote(folder, safe='')}/messages/delta"

    def poll(self, channel: "AgentChatChannel") -> None:
        headers = {**self.auth_headers(channel), "Prefer": "odata.maxpagesize=50"}
        cursor = channel.config.get("cursor")
        if not cursor:
            # The first delta round lists the whole folder; it is walked
            # without reading anything so only mail from now on counts.
            url = self._folder_url(channel)
            params = {"$select": "id"}
            while True:
                status, body = _json_request("GET", url, headers, params=params)
                if status != 200 or not isinstance(body, dict):
                    raise MailboxRequestFailed(f"delta answered {status}")
                if body.get("@odata.deltaLink"):
                    self.save_cursor(channel, cursor=body["@odata.deltaLink"])
                    return
                url, params = body.get("@odata.nextLink"), None
                if not url:
                    raise MailboxRequestFailed("delta ended without a delta link")

        url, params = cursor, None
        message_ids: list[str] = []
        while True:
            status, body = _json_request("GET", url, headers, params=params)
            if status == 410:
                # The delta token expired; start over from now.
                self.save_cursor(channel, cursor="")
                return
            if status != 200 or not isinstance(body, dict):
                raise MailboxRequestFailed(f"delta answered {status}")
            for entry in body.get("value") or []:
                if "@removed" in entry or not entry.get("id"):
                    continue
                if entry["id"] not in message_ids:
                    message_ids.append(entry["id"])
            if body.get("@odata.deltaLink"):
                new_cursor = body["@odata.deltaLink"]
                break
            url, params = body.get("@odata.nextLink"), None
            if not url:
                raise MailboxRequestFailed("delta ended without a delta link")

        for message_id in message_ids[:MAX_MESSAGES_PER_POLL]:
            received = self._fetch_message(channel, headers, message_id)
            if received is not None:
                self.receive_email(channel, received)
        self.save_cursor(channel, cursor=new_cursor)

    def _fetch_message(
        self, channel: "AgentChatChannel", headers: dict, message_id: str
    ) -> Optional[ReceivedEmail]:
        status, message = _json_request(
            "GET",
            f"{GRAPH_API_URL}/me/messages/{quote(message_id, safe='')}",
            headers,
            params={
                "$select": "id,subject,from,toRecipients,ccRecipients,"
                "internetMessageId,conversationId,body,isDraft,hasAttachments,"
                "internetMessageHeaders"
            },
        )
        if status != 200 or not isinstance(message, dict) or message.get("isDraft"):
            return None
        header_values = {
            (h.get("name") or "").lower(): h.get("value") or ""
            for h in message.get("internetMessageHeaders") or []
        }
        if header_values.get("auto-submitted", "no").lower() not in ("", "no"):
            return None
        sender = (message.get("from") or {}).get("emailAddress") or {}
        recipients = [
            ((r.get("emailAddress") or {}).get("address") or "")
            for r in (message.get("toRecipients") or [])
            + (message.get("ccRecipients") or [])
        ]
        to_addresses = _address_list(recipients)
        if not self.alias_matches(channel, to_addresses):
            return None
        body = message.get("body") or {}
        content = body.get("content") or ""
        is_html = (body.get("contentType") or "").lower() == "html"

        attachments, names = [], []
        if message.get("hasAttachments"):
            attachments, names = self._fetch_attachments(headers, message_id)
        return ReceivedEmail(
            from_address=sender.get("address") or "",
            from_name=sender.get("name") or "",
            to_addresses=to_addresses,
            subject=message.get("subject") or "",
            text="" if is_html else content,
            html=content if is_html else "",
            message_id=message.get("internetMessageId") or "",
            in_reply_to=header_values.get("in-reply-to", ""),
            references=header_values.get("references", "").split(),
            thread_key=message.get("conversationId") or "",
            provider_message_id=message_id,
            sender_verified=True,
            attachments=attachments,
            attachment_names=names,
        )

    def _fetch_attachments(self, headers: dict, message_id: str):
        status, body = _json_request(
            "GET",
            f"{GRAPH_API_URL}/me/messages/{quote(message_id, safe='')}/attachments",
            headers,
        )
        attachments, names = [], []
        if status != 200 or not isinstance(body, dict):
            return attachments, names
        for entry in body.get("value") or []:
            name = entry.get("name") or ""
            if not name:
                continue
            names.append(name)
            if len(attachments) < MAX_ATTACHMENTS and entry.get("contentBytes"):
                stored = self.upload_attachment(
                    name, base64.b64decode(entry["contentBytes"])
                )
                if stored:
                    attachments.append(stored)
        return attachments, names

    def send_email(self, channel, chat, target, body: str) -> str:
        headers = self.auth_headers(channel)
        if not target.provider_message_id:
            raise EmailReplyNotPossible("The message to reply to is unknown.")
        # Graph builds the reply itself, threading headers included; the
        # comment is HTML, so the text is escaped with its line breaks kept.
        comment = html.escape(body).replace("\n", "<br>")
        status, _ = _json_request(
            "POST",
            f"{GRAPH_API_URL}/me/messages/"
            f"{quote(target.provider_message_id, safe='')}/reply",
            headers,
            json={"comment": comment},
        )
        if status >= 400:
            raise EmailReplyNotPossible(f"Outlook refused the reply ({status}).")
        return ""


def poll_mailbox_channels() -> None:
    from ..models import AgentChatChannel
    from .registries import agent_chat_channel_type_registry

    channels = AgentChatChannel.objects.filter(
        type__in=(GmailAgentChatChannelType.type, OutlookAgentChatChannelType.type),
        enabled=True,
        application__active=True,
        application__trashed=False,
        application__workspace__trashed=False,
    ).select_related("application__workspace")
    for channel in channels:
        lock_key = f"agent_application:mailbox:{channel.id}:poll"
        if not cache.add(lock_key, True, timeout=POLL_LOCK_SECONDS):
            continue
        try:
            channel_type = agent_chat_channel_type_registry.get(channel.type)
            channel_type.poll(channel)
        except (MailboxRequestFailed, EmailReplyNotPossible) as e:
            logger.warning("Mailbox channel {} could not be polled: {}", channel.id, e)
        except Exception:
            logger.exception("Mailbox channel {} failed to poll", channel.id)
        finally:
            cache.delete(lock_key)


def _b64url_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded)


def _parse_address(value: str) -> tuple[str, str]:
    from email.utils import parseaddr

    name, address = parseaddr(value or "")
    return name, address.lower()


def _split_addresses(value: str) -> list[str]:
    from email.utils import getaddresses

    return [address for _, address in getaddresses([value or ""]) if address]
