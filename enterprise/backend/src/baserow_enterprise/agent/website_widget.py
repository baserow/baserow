import json
from functools import cache
from pathlib import Path

from baserow.core.utils import get_embedded_share_url
from baserow_enterprise.agent.models import WebsiteWidgetAgentChannel

# The chat page's own button colours when no accent colour is set.
DEFAULT_ACCENT_COLOR = "#202128"
DEFAULT_ACCENT_TEXT_COLOR = "#ffffff"
SCRIPT_TEMPLATE = Path(__file__).with_name("website_widget.js")
CONFIG_PLACEHOLDER = "__WIDGET_CONFIG__"


@cache
def read_script_template() -> str:
    """
    :return: The widget's script, with a placeholder for its settings.
    """

    return SCRIPT_TEMPLATE.read_text()


def readable_text_color(hex_color: str) -> str:
    """
    :param hex_color: A `#rrggbb` colour.
    :return: Black or white, whichever contrasts more with the colour.
    """

    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    luminance = 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue)
    # Above this luminance black contrasts more than white.
    return "#000000" if luminance > 0.179 else "#ffffff"


def get_widget_chat_url(widget: WebsiteWidgetAgentChannel) -> str:
    """
    :param widget: The website widget.
    :return: The address of the chat page the widget opens in its panel.
    """

    return get_embedded_share_url(f"public/agent-chat/{widget.slug}?embedded=true")


def build_widget_script(widget: WebsiteWidgetAgentChannel) -> str:
    """
    The script a website adds with a script tag: a button that opens the chat in a
    panel, with the widget's current settings written into it.

    :param widget: The website widget, with its agent.
    :return: The JavaScript source.
    """

    accent = widget.accent_color
    config = {
        "id": f"baserow-agent-widget-{widget.slug}",
        "chatUrl": get_widget_chat_url(widget),
        "color": accent or DEFAULT_ACCENT_COLOR,
        "textColor": readable_text_color(accent)
        if accent
        else DEFAULT_ACCENT_TEXT_COLOR,
        "position": widget.button_position,
        "text": widget.button_text,
        "title": widget.title or widget.agent.name,
    }
    # A literal `</script>` in a text would end the tag if the script is inlined.
    encoded = json.dumps(config).replace("</", "<\\/")
    return read_script_template().replace(CONFIG_PLACEHOLDER, encoded)
