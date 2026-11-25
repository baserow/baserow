from django.db import models

from baserow.core.formula.field import FormulaField
from baserow.core.services.models import Service


class MicrosoftTeamsDestinationType(models.TextChoices):
    CHANNEL = "channel", "Channel"
    CHAT = "chat", "Chat"


class MicrosoftTeamsWriteMessageService(Service):
    """
    Sends a message to a Teams channel or chat, as the account of a Microsoft
    integration.
    """

    destination_type = models.CharField(
        max_length=16,
        choices=MicrosoftTeamsDestinationType.choices,
        default=MicrosoftTeamsDestinationType.CHANNEL,
        db_default=MicrosoftTeamsDestinationType.CHANNEL,
        help_text="Whether the message goes to a channel of a team, or to a chat.",
    )
    team_id = FormulaField(
        blank=True,
        help_text="The id of the team the channel belongs to.",
    )
    channel_id = FormulaField(
        blank=True,
        help_text="The id of the channel to send the message to.",
    )
    chat_id = FormulaField(
        blank=True,
        help_text="The id of the chat to send the message to.",
    )
    destination_label = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_default="",
        help_text="The name of the picked channel or chat, to show without asking "
        "Microsoft.",
    )
    message = FormulaField(
        blank=True,
        help_text="The text of the message.",
    )
