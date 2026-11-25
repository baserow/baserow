import secrets

from django.contrib.auth import hashers
from django.db import models

from baserow.contrib.agent.models import AgentChannel
from baserow_enterprise.agent.constants import (
    PUBLIC_CHAT_DEFAULT_FONT,
    PUBLIC_CHAT_FONT_MAX_LENGTH,
    PUBLIC_CHAT_TITLE_MAX_LENGTH,
    PublicChatBackground,
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
    # A `#rrggbb` colour; blank uses Baserow's blue.
    accent_color = models.CharField(max_length=7, blank=True, default="", db_default="")
    # A font type of the frontend; the page falls back to Inter for an unknown one.
    font = models.CharField(
        max_length=PUBLIC_CHAT_FONT_MAX_LENGTH,
        default=PUBLIC_CHAT_DEFAULT_FONT,
        db_default=PUBLIC_CHAT_DEFAULT_FONT,
    )
    background = models.CharField(
        max_length=16,
        choices=PublicChatBackground.choices,
        default=PublicChatBackground.PLAIN,
        db_default=PublicChatBackground.PLAIN,
    )
    # A `#rrggbb` colour for a plain background; blank keeps the page's own.
    background_color = models.CharField(
        max_length=7, blank=True, default="", db_default=""
    )
    show_powered_by = models.BooleanField(default=True, db_default=True)

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
