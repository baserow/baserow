import hashlib
import hmac
import json
import re
import time
from typing import TYPE_CHECKING

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse

from loguru import logger

from baserow.contrib.integrations.utils import send_http_request

from .registries import AgentChatChannelType
from .slack_format import markdown_to_mrkdwn, slack_text_to_plain

if TYPE_CHECKING:
    from ..models import AgentChat, AgentChatChannel

# Slack rejects requests older than 5 minutes to prevent replay attacks; we
# mirror that window when verifying inbound events.
_SIGNATURE_MAX_AGE_SECONDS = 300
_SLACK_REQUEST_TIMEOUT_SECONDS = 10
_SLACK_TEXT_LIMIT = 40000
_MENTION_PATTERN = re.compile(r"<@[A-Z0-9]+>")
_PLACEHOLDER_TEXT = "_Working on it…_"
_PLACEHOLDER_CACHE_TIMEOUT = 3600
_SCOPES = ["chat:write", "app_mentions:read", "im:history"]
_BOT_EVENTS = ["app_mention", "message.im"]


class SlackAgentChatChannelType(AgentChatChannelType):
    """
    Connects an agent to a Slack app: direct messages to the app's bot user
    and @-mentions in channels are forwarded to the agent, and its answers
    are posted back as replies in the thread of the message. Every Slack
    thread is its own conversation, so unrelated questions stay isolated.

    The channel can be created before the Slack app exists: its events URL
    goes into the app manifest, and the bot token and signing secret are
    filled in once the app is installed. Until both are set, only Slack's
    URL verification handshake is answered.
    """

    type = "slack"

    def prepare_config(self, config: dict, existing_config: dict | None = None) -> dict:
        existing_config = existing_config or {}
        bot_token = (config.get("bot_token") or "").strip() or existing_config.get(
            "bot_token", ""
        )
        signing_secret = (
            config.get("signing_secret") or ""
        ).strip() or existing_config.get("signing_secret", "")
        return {"bot_token": bot_token, "signing_secret": signing_secret}

    def get_manifest(self, channel: "AgentChatChannel", events_url: str) -> dict:
        """
        The Slack app manifest that wires an app to this channel, ready to be
        pasted into "Create New App" > "From a manifest".
        """

        # The app is what people see in Slack, so it carries the agent's name
        # rather than the channel's internal label.
        name = (channel.application.name or channel.name or "Baserow agent")[:35]
        return {
            "display_information": {
                "name": name,
                "description": "Chat with a Baserow agent from Slack.",
            },
            "features": {
                "app_home": {
                    "messages_tab_enabled": True,
                    "messages_tab_read_only_enabled": False,
                },
                "bot_user": {"display_name": name, "always_online": True},
            },
            "oauth_config": {"scopes": {"bot": list(_SCOPES)}},
            "settings": {
                "event_subscriptions": {
                    "request_url": events_url,
                    "bot_events": list(_BOT_EVENTS),
                },
                "org_deploy_enabled": False,
                "socket_mode_enabled": False,
                "token_rotation_enabled": False,
            },
        }

    def get_public_config(self, channel: "AgentChatChannel") -> dict:
        # The secrets never leave the backend once stored.
        return {
            "bot_token_set": bool(channel.config.get("bot_token")),
            "signing_secret_set": bool(channel.config.get("signing_secret")),
        }

    def handle_inbound(
        self, channel: "AgentChatChannel", request: HttpRequest
    ) -> HttpResponse:
        body = request.body
        signing_secret = channel.config.get("signing_secret", "")

        if signing_secret and not self._verify_signature(channel, request, body):
            return HttpResponse(status=401)

        try:
            payload = json.loads(body)
        except (ValueError, TypeError):
            return HttpResponse(status=400)

        if payload.get("type") == "url_verification":
            # Slack verifies the URL when the app is created from the
            # manifest, before the signing secret can be known here. Echoing
            # the challenge reveals nothing, so it is answered regardless.
            return JsonResponse({"challenge": payload.get("challenge", "")})

        if not signing_secret:
            return HttpResponse(status=401)

        if payload.get("type") == "event_callback":
            self._handle_event_callback(channel, payload)

        # Slack retries and eventually disables the endpoint on non-200
        # responses, so unprocessable events are still acknowledged.
        return HttpResponse(status=200)

    def _verify_signature(
        self, channel: "AgentChatChannel", request: HttpRequest, body: bytes
    ) -> bool:
        signing_secret = channel.config.get("signing_secret", "")
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        if not timestamp or not signature:
            return False

        try:
            if abs(time.time() - float(timestamp)) > _SIGNATURE_MAX_AGE_SECONDS:
                return False
        except ValueError:
            return False

        basestring = b"v0:" + timestamp.encode() + b":" + body
        expected = (
            "v0="
            + hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
        )
        return hmac.compare_digest(expected, signature)

    def _handle_event_callback(
        self, channel: "AgentChatChannel", payload: dict
    ) -> None:
        from ..tasks import process_agent_channel_message

        event = payload.get("event") or {}
        event_type = event.get("type")

        # Never react to bots (including this one) or message edits/deletes.
        if event.get("bot_id") or event.get("subtype") or not event.get("user"):
            return
        if event_type not in ("message", "app_mention"):
            return
        # Plain channel messages are only forwarded as mentions; a "message"
        # event is only accepted from a direct message with the bot.
        if event_type == "message" and event.get("channel_type") != "im":
            return

        slack_channel = event.get("channel", "")
        ts = event.get("ts", "")

        # Slack retries deliveries, and a mention inside a direct message
        # arrives both as a "message" and as an "app_mention" event, so the
        # message itself (channel + timestamp) deduplicates rather than the
        # delivery's event id.
        if not cache.add(
            f"agent_application:channel:{channel.id}:message:{slack_channel}:{ts}",
            True,
            timeout=300,
        ):
            return

        if self._is_rate_limited(channel):
            return

        text = slack_text_to_plain(
            _MENTION_PATTERN.sub("", event.get("text") or "")
        ).strip()
        if not text:
            return

        # A thread is a conversation: a reply continues it, a new top-level
        # message starts a fresh one, in direct messages too.
        thread_ts = event.get("thread_ts") or ts
        sender_name = f"<@{event['user']}>" if event_type == "app_mention" else ""

        session_key = f"{slack_channel}|{thread_ts}"
        process_agent_channel_message.delay(channel.id, session_key, text, sender_name)

    def _is_rate_limited(self, channel: "AgentChatChannel") -> bool:
        return self.is_rate_limited(channel)

    def on_run_starting(self, channel: "AgentChatChannel", chat: "AgentChat") -> None:
        # Slack has no typing indicator for bots, so a placeholder reply is
        # posted right away and later replaced by the answer. A retried start
        # keeps the placeholder it already posted.
        if cache.get(self._placeholder_key(chat)):
            return
        response = self._call(channel, chat, "chat.postMessage", _PLACEHOLDER_TEXT)
        ts = (response or {}).get("ts")
        if ts:
            cache.set(self._placeholder_key(chat), ts, _PLACEHOLDER_CACHE_TIMEOUT)

    def send_response(
        self, channel: "AgentChatChannel", chat: "AgentChat", text: str
    ) -> None:
        text = markdown_to_mrkdwn(text)[:_SLACK_TEXT_LIMIT]
        placeholder_key = self._placeholder_key(chat)
        placeholder_ts = cache.get(placeholder_key)
        if placeholder_ts:
            cache.delete(placeholder_key)
            response = self._call(channel, chat, "chat.update", text, ts=placeholder_ts)
            if response and response.get("ok"):
                return
        self._call(channel, chat, "chat.postMessage", text)

    def _placeholder_key(self, chat: "AgentChat") -> str:
        return f"agent_application:slack:placeholder:{chat.id}"

    def _call(
        self,
        channel: "AgentChatChannel",
        chat: "AgentChat",
        method: str,
        text: str,
        **extra,
    ) -> dict | None:
        slack_channel, _, thread_ts = (chat.channel_session_key or "").partition("|")
        if not slack_channel:
            return None

        params = {"channel": slack_channel, "text": text, **extra}
        if thread_ts and method == "chat.postMessage":
            params["thread_ts"] = thread_ts

        response = send_http_request(
            method="POST",
            url=f"https://slack.com/api/{method}",
            deadline=time.monotonic() + _SLACK_REQUEST_TIMEOUT_SECONDS,
            headers={"Authorization": f"Bearer {channel.config.get('bot_token', '')}"},
            params=params,
        )
        response_data = response.json()
        if not response_data.get("ok"):
            logger.warning(
                "Slack {} failed for channel {}: {}",
                method,
                channel.id,
                response_data.get("error"),
            )
        return response_data
