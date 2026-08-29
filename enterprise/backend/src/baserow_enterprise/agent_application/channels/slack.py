import hashlib
import hmac
import json
import re
import time
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse

from loguru import logger
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.integrations.utils import get_http_request_function

from .registries import AgentChatChannelType

if TYPE_CHECKING:
    from ..models import AgentChat, AgentChatChannel

# Slack rejects requests older than 5 minutes to prevent replay attacks; we
# mirror that window when verifying inbound events.
_SIGNATURE_MAX_AGE_SECONDS = 300
_SLACK_TEXT_LIMIT = 40000
_MENTION_PATTERN = re.compile(r"<@[A-Z0-9]+>")


class SlackAgentChatChannelType(AgentChatChannelType):
    """
    Connects an agent to a Slack app: direct messages to the app's bot user
    and @-mentions in channels are forwarded to the agent, and its answers
    are posted back into the same conversation (threaded for mentions).

    The user creates a Slack app with a bot token (`chat:write`) and
    subscribes its Events API (`message.im`, `app_mention`) to this
    channel's inbound webhook URL.
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

        if not bot_token:
            raise DRFValidationError(
                detail="A Slack bot token is required.", code="invalid_channel_config"
            )
        if not signing_secret:
            raise DRFValidationError(
                detail="A Slack signing secret is required.",
                code="invalid_channel_config",
            )

        return {"bot_token": bot_token, "signing_secret": signing_secret}

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

        if not self._verify_signature(channel, request, body):
            return HttpResponse(status=401)

        try:
            payload = json.loads(body)
        except (ValueError, TypeError):
            return HttpResponse(status=400)

        if payload.get("type") == "url_verification":
            return JsonResponse({"challenge": payload.get("challenge", "")})

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

        if not signing_secret or not timestamp or not signature:
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

        # Slack retries deliveries; the event id deduplicates them.
        event_id = payload.get("event_id")
        if event_id and not cache.add(
            f"agent_application:channel:{channel.id}:event:{event_id}",
            True,
            timeout=300,
        ):
            return

        if self._is_rate_limited(channel):
            return

        text = _MENTION_PATTERN.sub("", event.get("text") or "").strip()
        if not text:
            return

        slack_channel = event.get("channel", "")
        if event_type == "app_mention":
            thread_ts = event.get("thread_ts") or event.get("ts") or ""
            sender_name = f"<@{event['user']}>"
        else:
            # A direct message is one continuous conversation per user.
            thread_ts = ""
            sender_name = ""

        session_key = f"{slack_channel}|{thread_ts}"
        process_agent_channel_message.delay(channel.id, session_key, text, sender_name)

    def _is_rate_limited(self, channel: "AgentChatChannel") -> bool:
        limit = settings.AGENT_APPLICATION_CHANNEL_RATE_LIMIT_PER_MINUTE
        cache_key = f"agent_application:channel:{channel.id}:rate"
        cache.add(cache_key, 0, timeout=60)
        count = cache.incr(cache_key)
        if count > limit:
            logger.warning(
                "Agent chat channel {} exceeded the rate limit of {} messages "
                "per minute",
                channel.id,
                limit,
            )
            return True
        return False

    def send_response(
        self, channel: "AgentChatChannel", chat: "AgentChat", text: str
    ) -> None:
        slack_channel, _, thread_ts = (chat.channel_session_key or "").partition("|")
        if not slack_channel:
            return

        token = channel.config.get("bot_token", "")
        params = {
            "channel": slack_channel,
            "text": text[:_SLACK_TEXT_LIMIT],
        }
        if thread_ts:
            params["thread_ts"] = thread_ts

        response = get_http_request_function()(
            method="POST",
            url="https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=10,
        )
        response_data = response.json()
        if not response_data.get("ok"):
            logger.warning(
                "Failed to post the agent answer to Slack for channel {}: {}",
                channel.id,
                response_data.get("error"),
            )
