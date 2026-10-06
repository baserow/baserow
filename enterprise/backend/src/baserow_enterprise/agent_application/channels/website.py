"""
The "Website widget" channel: a public chat (see `web.py` for everything a
visitor can learn) that a site owner embeds with one `<script>` tag. The
script draws a floating button that opens the public chat page in a panel.

The widget settings (button colour, position and text) live in the channel
config and are baked into the script when it is served, so changing them in
Baserow updates every site without touching the embed code.
"""

import functools
import json
import re
from pathlib import Path

from django.conf import settings

from rest_framework.exceptions import ValidationError as DRFValidationError

from ..models import AgentChatChannel
from .web import WebAgentChatChannelType

BUTTON_POSITIONS = ("bottom-right", "bottom-left", "top-right", "top-left")
DEFAULT_BUTTON_COLOR = "#5190ef"
DEFAULT_BUTTON_TEXT = "Chat with us"
BUTTON_TEXT_MAX_LENGTH = 60
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_SCRIPT_TEMPLATE = Path(__file__).with_name("website_widget.js")


@functools.lru_cache(maxsize=1)
def _script_source() -> str:
    return _SCRIPT_TEMPLATE.read_text()


def _safe_color(value) -> str:
    """
    The colour is written into CSS text on third-party pages; an imported
    config did not pass the API validation, so it is checked again here.
    """

    if isinstance(value, str) and _HEX_COLOR.match(value):
        return value
    return DEFAULT_BUTTON_COLOR


class WebsiteWidgetAgentChatChannelType(WebAgentChatChannelType):
    type = "website"

    def prepare_config(self, config: dict, existing_config: dict | None = None) -> dict:
        existing = existing_config or {}
        # A password can't be entered inside a widget, so the parent's
        # password handling is bypassed by never passing one through.
        prepared = super().prepare_config(
            {key: value for key, value in config.items() if key != "password"},
            existing,
        )
        prepared["password"] = ""

        color = str(config.get("button_color", existing.get("button_color", "")))
        color = color.strip() or DEFAULT_BUTTON_COLOR
        if not _HEX_COLOR.match(color):
            raise DRFValidationError(
                detail="The button colour must be a hex colour like #5190ef.",
                code="invalid_channel_config",
            )
        position = str(
            config.get("button_position", existing.get("button_position", ""))
        )
        position = position or BUTTON_POSITIONS[0]
        if position not in BUTTON_POSITIONS:
            raise DRFValidationError(
                detail=f"The button position must be one of {BUTTON_POSITIONS}.",
                code="invalid_channel_config",
            )
        text = str(config.get("button_text", existing.get("button_text", "")))
        prepared.update(
            {
                "button_color": color.lower(),
                "button_position": position,
                "button_text": text.strip()[:BUTTON_TEXT_MAX_LENGTH]
                or DEFAULT_BUTTON_TEXT,
            }
        )
        return prepared

    def get_public_config(self, channel: AgentChatChannel) -> dict:
        return {
            **super().get_public_config(channel),
            "button_color": channel.config.get("button_color", DEFAULT_BUTTON_COLOR),
            "button_position": channel.config.get(
                "button_position", BUTTON_POSITIONS[0]
            ),
            "button_text": channel.config.get("button_text", DEFAULT_BUTTON_TEXT),
            "embed_script_url": self.get_script_url(channel),
        }

    def get_script_url(self, channel: AgentChatChannel) -> str:
        return (
            f"{settings.PUBLIC_BACKEND_URL}/api/agent_application/public/widget/"
            f"{channel.config.get('slug', '')}.js"
        )

    def get_chat_url(self, channel: AgentChatChannel) -> str:
        # The embedded share URL is the frontend origin that may be framed.
        return (
            f"{settings.BASEROW_EMBEDDED_SHARE_URL}/agent-chat/"
            f"{channel.config.get('slug', '')}"
        )

    def build_script(self, channel: AgentChatChannel) -> str:
        """
        The JavaScript served to the embedding site, with this channel's
        widget settings baked in.
        """

        widget_config = {
            "slug": channel.config.get("slug", ""),
            "chat_url": self.get_chat_url(channel),
            "color": _safe_color(channel.config.get("button_color")),
            "position": channel.config.get("button_position", BUTTON_POSITIONS[0]),
            "text": channel.config.get("button_text", DEFAULT_BUTTON_TEXT),
            "title": channel.config.get("title", "") or channel.application.name,
        }
        # `</` can't appear in the JSON; it would end a surrounding script
        # tag if the file were ever inlined.
        encoded = json.dumps(widget_config).replace("</", "<\\/")
        return _script_source().replace("__WIDGET_CONFIG__", encoded)
