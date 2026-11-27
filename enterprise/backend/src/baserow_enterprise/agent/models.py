import secrets

from django.contrib.auth import hashers
from django.db import models

from baserow.contrib.agent.models import AgentChannel
from baserow_enterprise.agent.constants import (
    PUBLIC_CHAT_TITLE_MAX_LENGTH,
    WEBSITE_WIDGET_BUTTON_TEXT_MAX_LENGTH,
    WEBSITE_WIDGET_DEFAULT_BUTTON_TEXT,
    PublicChatBackground,
    WebsiteWidgetButtonPosition,
)


class PublicChatAgentChannel(AgentChannel):
    """A page with its own link where anyone who has it talks to the agent."""

    slug = models.SlugField(default=secrets.token_urlsafe, unique=True)
    # A hash; empty lets in anyone with the link.
    password = models.CharField(max_length=128, blank=True, default="", db_default="")
    # Shown to visitors; blank shows the agent's name.
    title = models.CharField(
        max_length=PUBLIC_CHAT_TITLE_MAX_LENGTH, blank=True, default="", db_default=""
    )
    welcome_text = models.TextField(blank=True, default="", db_default="")
    # A `#rrggbb` colour; blank uses the standard chat colours.
    accent_color = models.CharField(max_length=7, blank=True, default="", db_default="")
    background = models.CharField(
        max_length=16,
        choices=PublicChatBackground.choices,
        default=PublicChatBackground.GRADIENT,
        db_default=PublicChatBackground.GRADIENT,
    )
    # A `#rrggbb` colour for the backdrop; blank uses the page default.
    background_color = models.CharField(
        max_length=7, blank=True, default="", db_default=""
    )

    @property
    def has_password(self) -> bool:
        return self.password != ""  # nosec b105

    @staticmethod
    def hash_password(password: str) -> str:
        """
        :param password: A password, or an empty string for none.
        :return: The value to store: its hash, or an empty string for none.
        """

        return hashers.make_password(password) if password else ""

    def check_password(self, password: str) -> bool:
        """
        :param password: The password a visitor typed.
        :return: Whether it opens the chat; always True without a password.
        """

        return not self.has_password or hashers.check_password(password, self.password)


class WebsiteWidgetAgentChannel(PublicChatAgentChannel):
    """
    A public chat that a website opens in a panel from a button, which a script tag
    adds to the site. It never has a password.
    """

    # Blank shows only the button's icon.
    button_text = models.CharField(
        max_length=WEBSITE_WIDGET_BUTTON_TEXT_MAX_LENGTH,
        blank=True,
        default=WEBSITE_WIDGET_DEFAULT_BUTTON_TEXT,
    )
    button_position = models.CharField(
        max_length=16,
        choices=WebsiteWidgetButtonPosition.choices,
        default=WebsiteWidgetButtonPosition.BOTTOM_RIGHT,
    )
